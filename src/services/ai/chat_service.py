"""Сервис для обработки чата через WebSocket."""

import asyncio
import json
import time
from collections.abc import Callable

from src.integrations.ai import Agent
from src.integrations.ai.websocket_codes import WebSocketCode
from src.integrations.redis import RedisClient
from src.core.logger import get_logger
from src.services.ai.message_formatter import MessageFormatter

logger = get_logger(__name__)

# Время жизни контекста чата в Redis (30 минут)
CHAT_CONTEXT_TTL = 30 * 60


class ChatService:
    """Сервис для обработки чата через WebSocket."""

    def __init__(self, agent: Agent, redis_client: RedisClient):
        """
        Инициализация сервиса.

        Args:
            agent: Экземпляр AI агента
            redis_client: Клиент Redis для сохранения контекста
        """
        self.agent = agent
        self.redis_client = redis_client
        self.formatter = MessageFormatter()

    async def initialize_chat_context(
        self,
        session_id: str,
        receive_message: Callable,
        send_message: Callable,
    ) -> list[dict[str, str]]:
        """
        Инициализирует контекст чата: запрашивает у клиента и сохраняет в Redis.

        Args:
            session_id: ID сессии
            receive_message: Функция для получения сообщения от клиента
            send_message: Функция для отправки сообщения клиенту

        Returns:
            Контекст чата (список сообщений)
        """
        chat_context_key = f'websocket:chat_context:{session_id}'

        # Отправляем подтверждение подключения
        await send_message(WebSocketCode.CONNECTION_ESTABLISHED, None)

        # Запрашиваем контекст чата у клиента
        logger.debug('Запрос контекста чата у клиента')
        await send_message(WebSocketCode.REQUEST_CHAT_CONTEXT, None)

        chat_context: list[dict[str, str]] = []

        try:
            # Пытаемся получить контекст с таймаутом
            message = await asyncio.wait_for(receive_message(), timeout=10.0)

            if message.get('type') == 'websocket.disconnect':
                logger.debug('Клиент отключился до отправки контекста')
                return chat_context

            if 'text' in message:
                raw_message = message['text']
                try:
                    message_data = json.loads(raw_message)
                    code = message_data.get('code')
                    data = message_data.get('data')

                    if code == 'CHAT_CONTEXT':
                        if isinstance(data, list):
                            chat_context = data
                            logger.debug(f'Получен контекст чата от клиента ({len(chat_context)} сообщений)')

                            # Сохраняем в Redis
                            await self.redis_client.set_json(chat_context_key, chat_context, CHAT_CONTEXT_TTL)
                            logger.debug(f'Контекст сохранён в Redis с ключом {chat_context_key}')

                            await send_message(WebSocketCode.CHAT_CONTEXT_RECEIVED, {'count': len(chat_context)})
                        else:
                            logger.debug('Контекст чата не в формате списка, используем пустой')
                            chat_context = []
                    else:
                        logger.debug(f'Неожиданный код при ожидании контекста: {code}, используем пустой')
                        chat_context = []
                except json.JSONDecodeError:
                    logger.debug('Не удалось распарсить сообщение с контекстом, используем пустой')
                    chat_context = []
            else:
                logger.debug('Получено сообщение без текста при ожидании контекста')
                chat_context = []
        except TimeoutError:
            logger.debug('Таймаут ожидания контекста чата, продолжаем с пустым контекстом')
            chat_context = []

        return chat_context

    async def process_user_message(
        self,
        user_message: str,
        chat_context: list[dict[str, str]],
        session_id: str,
        send_message: Callable,
    ) -> None:
        """
        Обрабатывает сообщение пользователя.

        Args:
            user_message: Сообщение пользователя
            chat_context: Текущий контекст чата
            session_id: ID сессии
            send_message: Функция для отправки сообщения клиенту
        """
        logger.debug(f'Обработка сообщения: "{user_message[:50]}..."')
        request_start = time.time()
        chat_context_key = f'websocket:chat_context:{session_id}'

        try:
            # Определяем намерение (может потребоваться Grok)
            await send_message(
                WebSocketCode.STATUS_GROK_PROCESSING,
                {'message': 'Анализирую запрос...'},
            )

            intent = await self.agent._detect_intent(user_message, chat_context) # noqa

            if intent == 'search':
                # Отправляем статус RAG
                await send_message(
                    WebSocketCode.STATUS_RAG_PROCESSING,
                    {'message': 'Ищу подходящие лотереи в базе знаний...'},
                )

                # Может потребоваться получение данных от СтоЛото
                if not self.agent.rag.data:
                    await send_message(
                        WebSocketCode.STATUS_STOLOTO_FETCHING,
                        {'message': 'Загружаю актуальные данные о лотереях...'},
                    )

            # Обрабатываем запрос
            result = await self.agent.process_query(
                user_query=user_message,
                chat_context=chat_context,
                force_refresh_rag=False,
            )

            # Форматируем ответ
            formatted_text = self.formatter.format_response(result)

            # Формируем ответ
            response_data = {
                'action': result.get('action', 'answer'),
                'content': result.get('content', ''),
                'formatted_text': formatted_text,
            }

            # Отправляем ответ
            await send_message(WebSocketCode.RESPONSE_MESSAGE, response_data)

            # Обновляем контекст
            chat_context.append({'role': 'user', 'content': user_message})
            chat_context.append({'role': 'assistant', 'content': formatted_text})

            # Ограничиваем размер контекста
            if len(chat_context) > 20: # noqa
                chat_context = chat_context[-20:]
                logger.debug(f'Контекст обрезан до {len(chat_context)} сообщений')

            # Обновляем контекст в Redis
            await self.redis_client.set_json(chat_context_key, chat_context, CHAT_CONTEXT_TTL)

            request_time = time.time() - request_start
            logger.debug(
                f'Запрос обработан за {request_time:.2f}с. '
                f'Действие: {result["action"]}, контекст: {len(chat_context)} сообщений'
            )
        except Exception as e:
            logger.error(f'Ошибка при обработке сообщения: {e}', exc_info=True)
            await send_message(
                WebSocketCode.ERROR,
                {'message': 'Произошла ошибка при обработке запроса. Попробуйте ещё раз.', 'error': str(e)},
            )
            raise

    async def cleanup_context(self, session_id: str) -> None:
        """
        Удаляет контекст чата из Redis при отключении.

        Args:
            session_id: ID сессии
        """
        chat_context_key = f'websocket:chat_context:{session_id}'
        try:
            await self.redis_client.client.delete(chat_context_key)
            logger.debug(f'Контекст удалён из Redis (ключ: {chat_context_key})')
        except Exception as e:
            logger.warning(f'Не удалось удалить контекст из Redis: {e}')

