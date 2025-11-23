import json
import time
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from src.core.config import env_config
from src.core.logger import get_logger
from src.integrations.ai.rag import RAGSystem
from src.integrations.stoloto import (
    StolotoClient,
    MainStolotoClient,
    NewsStolotoClient,
    TabsStolotoClient,
    ListStolotoClient,
)
from src.integrations.redis import RedisClient

logger = get_logger(__name__)


class Agent:
    """AI агент для работы с пользователями и поиска лотерей."""

    def __init__(
        self,
        stoloto_client: StolotoClient,
        redis_client: RedisClient,
        api_key: str | None = None,
        base_url: str = 'https://openrouter.ai/api/v1',
    ):
        """
        Инициализация агента.

        Args:
            stoloto_client: Клиент для работы с API СтоЛото
            redis_client: Клиент для работы с Redis
            api_key: API ключ для OpenRouter (если не указан, берётся из env)
            base_url: Базовый URL для OpenAI API
        """
        self.stoloto_client = stoloto_client
        self.redis_client = redis_client
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key or env_config.OPENAI_API_KEY,
        )

        # Загружаем промпты
        prompts_dir = Path(__file__).parent / 'prompts'
        self.system_prompt = (prompts_dir / 'system_prompt.txt').read_text(encoding='utf-8')
        self.analysis_prompt = (prompts_dir / 'analysis_prompt.txt').read_text(encoding='utf-8')
        self.archive_analysis_prompt = (prompts_dir / 'archive_analysis_prompt.txt').read_text(encoding='utf-8')
        self.intent_prompt = (prompts_dir / 'intent_prompt.txt').read_text(encoding='utf-8')
        self.conversation_prompt = (prompts_dir / 'conversation_prompt.txt').read_text(encoding='utf-8')

        # Инициализируем RAG систему
        self.rag = RAGSystem()

        # Клиенты СтоЛото для получения данных
        self.main_client = MainStolotoClient(stoloto_client, redis_client)
        self.tabs_client = TabsStolotoClient(stoloto_client, redis_client)
        self.list_client = ListStolotoClient(stoloto_client, redis_client)

    def _dict_to_string(self, obj: Any) -> str:
        """Преобразует словарь или список в строку."""
        if isinstance(obj, dict):
            parts = []
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    parts.append(f'{key}: {self._dict_to_string(value)}')
                else:
                    parts.append(f'{key}: {value}')
            return ', '.join(parts)
        if isinstance(obj, list):
            return ', '.join(str(self._dict_to_string(item)) for item in obj)
        return str(obj)

    async def _load_rag_data(self):
        """Загружает данные из СтоЛото в RAG систему."""
        start_time = time.time()
        try:
            logger.debug('Agent: Начало загрузки данных из СтоЛото в RAG')
            # Получаем данные от всех клиентов
            fetch_start = time.time()
            main_data = await self.main_client.get()
            tabs_data = await self.tabs_client.get()
            list_data = await self.list_client.get()
            fetch_time = time.time() - fetch_start
            logger.debug(f'Agent: Данные получены от клиентов за {fetch_time:.2f}с')

            # Подсчитываем размеры данных
            main_size = len(str(main_data.model_dump())) if main_data else 0
            tabs_size = len(str(tabs_data.model_dump())) if tabs_data else 0
            list_size = len(str(list_data.model_dump())) if list_data else 0
            total_size = main_size + tabs_size + list_size

            logger.debug(
                f'Agent: Размеры данных - main: {main_size / 1024:.1f} KB, '
                f'tabs: {tabs_size / 1024:.1f} KB, list: {list_size / 1024:.1f} KB, '
                f'всего: {total_size / 1024:.1f} KB'
            )

            # Преобразуем в словарь для RAG
            stoloto_data = {
                'main': main_data.model_dump() if main_data else None,
                'tabs': tabs_data.model_dump() if tabs_data else None,
                'list': list_data.model_dump() if list_data else None,
            }

            # Загружаем в RAG систему
            await self.rag.load_from_stoloto_data(stoloto_data)
            total_time = time.time() - start_time
            logger.debug(
                f'Agent: Данные СтоЛото загружены в RAG систему за {total_time:.2f}с. '
                f'Элементов в RAG: {len(self.rag.data)}'
            )
        except Exception as e:
            logger.error(f'Agent: Ошибка при загрузке данных в RAG: {e}', exc_info=True)

    async def extract_keywords(self, text: str, chat_context: list[dict[str, str]] | None = None) -> str:
        """
        Извлекает ключевые слова из текста пользователя.

        Args:
            text: Текст пользователя
            chat_context: Контекст чата (опционально)

        Returns:
            Строка с ключевыми словами
        """
        start_time = time.time()
        logger.debug(f'Agent: Извлечение ключевых слов из текста (длина: {len(text)})')

        messages = [{'role': 'system', 'content': self.system_prompt}]
        if chat_context:
            messages.extend(chat_context)
            logger.debug(f'Agent: Добавлен контекст чата ({len(chat_context)} сообщений)')
        messages.append({'role': 'user', 'content': text})

        total_chars = sum(len(msg.get('content', '')) for msg in messages)
        logger.debug(f'Agent: Отправка в LLM - сообщений: {len(messages)}, символов: {total_chars}')

        llm_start = time.time()
        response = await self.client.chat.completions.create(
            model='x-ai/grok-4.1-fast:free',
            messages=messages,
        )
        llm_time = time.time() - llm_start

        keywords = response.choices[0].message.content
        total_time = time.time() - start_time
        logger.debug(
            f'Agent: Ключевые слова извлечены за {total_time:.2f}с (LLM: {llm_time:.2f}с). '
            f'Результат: "{keywords[:100]}..."'
        )
        return keywords

    async def _detect_intent(self, user_query: str, chat_context: list[dict[str, str]] | None = None) -> str:
        """
        Определяет намерение пользователя.

        Args:
            user_query: Запрос пользователя
            chat_context: Контекст чата (опционально)

        Returns:
            "search" или "answer"
        """
        start_time = time.time()
        logger.debug(f'Agent: Определение намерения для запроса (длина: {len(user_query)})')

        messages = [{'role': 'system', 'content': self.intent_prompt}]
        if chat_context:
            messages.extend(chat_context)
            logger.debug(f'Agent: Добавлен контекст чата ({len(chat_context)} сообщений)')
        messages.append({'role': 'user', 'content': user_query})

        llm_start = time.time()
        response = await self.client.chat.completions.create(
            model='x-ai/grok-4.1-fast:free',
            messages=messages,
        )
        llm_time = time.time() - llm_start

        intent_raw = response.choices[0].message.content.strip().lower()
        intent = 'search' if 'search' in intent_raw else 'answer'
        total_time = time.time() - start_time
        logger.debug(
            f'Agent: Намерение определено за {total_time:.2f}с (LLM: {llm_time:.2f}с). '
            f'Результат: "{intent}" (raw: "{intent_raw}")'
        )
        return intent

    async def process_query(
        self,
        user_query: str,
        chat_context: list[dict[str, str]] | None = None,
        force_refresh_rag: bool = False,
    ) -> dict[str, Any]:
        """
        Обрабатывает запрос пользователя.

        Args:
            user_query: Запрос пользователя
            chat_context: Контекст чата (опционально)
            force_refresh_rag: Принудительно обновить данные в RAG

        Returns:
            Словарь с action и content
        """
        process_start = time.time()
        logger.debug(f'Agent: Начало обработки запроса (длина: {len(user_query)}, контекст: {len(chat_context) if chat_context else 0} сообщений)')

        # Загружаем данные в RAG при первом использовании или при необходимости обновления
        if not self.rag.data or force_refresh_rag:
            logger.debug(f'Agent: Загрузка данных в RAG (force_refresh: {force_refresh_rag}, текущий размер: {len(self.rag.data)})')
            await self._load_rag_data()
        else:
            logger.debug(f'Agent: Используются существующие данные RAG (размер: {len(self.rag.data)})')

        intent = await self._detect_intent(user_query, chat_context)

        if intent == 'search':
            logger.debug('Agent: Обработка запроса как поиск')
            # Извлекаем ключевые слова
            keywords = await self.extract_keywords(user_query, chat_context)

            # Ищем в RAG системе
            rag_results = await self.rag.search(keywords, top_k=3)

            if not rag_results:
                logger.warning('Agent: RAG не нашёл результатов, возвращаю общий ответ')
                messages = [{'role': 'system', 'content': self.conversation_prompt}]
                if chat_context:
                    messages.extend(chat_context)
                messages.append({
                    'role': 'user',
                    'content': f'{user_query}\n\nК сожалению, не удалось найти подходящие лотереи. Можете уточнить запрос?',
                })

                llm_start = time.time()
                response = await self.client.chat.completions.create(
                    model='x-ai/grok-4.1-fast:free',
                    messages=messages,
                )
                llm_time = time.time() - llm_start
                content = response.choices[0].message.content
                logger.debug(f'Agent: LLM ответ получен за {llm_time:.2f}с (общий ответ, результатов не найдено)')
            else:
                logger.debug(f'Agent: RAG нашёл {len(rag_results)} результатов, отправка в LLM для анализа')
                # Форматируем результаты для анализа
                lotteries_text = []
                for i, r in enumerate(rag_results, 1):
                    lottery = r['data']
                    text = self._dict_to_string(lottery)
                    lotteries_text.append(text)
                    logger.debug(f'Agent: Результат #{i} - тип: {lottery.get("type")}, score: {r["score"]:.4f}')

                lotteries_data = '\n'.join(lotteries_text)
                data_size = len(lotteries_data)
                logger.debug(f'Agent: Подготовлено данных для анализа: {data_size} символов')

                messages = [{'role': 'system', 'content': self.analysis_prompt}]
                if chat_context:
                    messages.extend(chat_context)
                messages.append({'role': 'user', 'content': f'Лотереи:\n{lotteries_data}'})

                total_chars = sum(len(msg.get('content', '')) for msg in messages)
                logger.debug(f'Agent: Отправка в LLM для анализа - сообщений: {len(messages)}, символов: {total_chars}')

                llm_start = time.time()
                response = await self.client.chat.completions.create(
                    model='x-ai/grok-4.1-fast:free',
                    messages=messages,
                )
                llm_time = time.time() - llm_start
                content = response.choices[0].message.content
                logger.debug(f'Agent: LLM анализ выполнен за {llm_time:.2f}с, размер ответа: {len(content)} символов')

                # Пытаемся распарсить JSON
                try:
                    parsed_content = json.loads(content)
                    content = parsed_content
                    logger.debug('Agent: Ответ успешно распарсен как JSON')
                except json.JSONDecodeError:
                    logger.warning('Agent: Не удалось распарсить ответ как JSON, возвращаю как строку')
        else:
            logger.debug('Agent: Обработка запроса как общий вопрос')
            messages = [{'role': 'system', 'content': self.conversation_prompt}]
            if chat_context:
                messages.extend(chat_context)
            messages.append({'role': 'user', 'content': user_query})

            total_chars = sum(len(msg.get('content', '')) for msg in messages)
            logger.debug(f'Agent: Отправка в LLM для общего ответа - сообщений: {len(messages)}, символов: {total_chars}')

            llm_start = time.time()
            response = await self.client.chat.completions.create(
                model='x-ai/grok-4.1-fast:free',
                messages=messages,
            )
            llm_time = time.time() - llm_start
            content = response.choices[0].message.content
            logger.debug(f'Agent: LLM общий ответ получен за {llm_time:.2f}с, размер ответа: {len(content)} символов')

        total_time = time.time() - process_start
        logger.info(
            f'Agent: Запрос обработан за {total_time:.2f}с. '
            f'Действие: {intent}, размер ответа: {len(str(content))} символов'
        )

        return {'action': intent, 'content': content}

    async def analyze_archive(self, archive_data: Any) -> str:
        """
        Анализирует архивные данные лотерей.

        Args:
            archive_data: Архивные данные

        Returns:
            Текст анализа
        """
        data_text = (
            self._dict_to_string(archive_data) if isinstance(archive_data, (dict, list)) else str(archive_data)
        )

        response = await self.client.chat.completions.create(
            model='x-ai/grok-4.1-fast:free',
            messages=[
                {'role': 'system', 'content': self.archive_analysis_prompt},
                {'role': 'user', 'content': f'Архивные данные:\n{data_text}'},
            ],
        )
        return response.choices[0].message.content

