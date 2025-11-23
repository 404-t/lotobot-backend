import asyncio
import time
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from src.core.logger import get_logger

logger = get_logger(__name__)


class RAGSystem:
    """RAG система для семантического поиска лотерей на основе данных СтоЛото."""

    def __init__(self, model_name: str = 'intfloat/multilingual-e5-small'):
        """
        Инициализация RAG системы.

        Args:
            model_name: Название модели для эмбеддингов
        """
        self.model = SentenceTransformer(model_name)
        self.data: list[dict[str, Any]] = []
        self.embeddings: np.ndarray | None = None
        self._lock = asyncio.Lock()

    def _dict_to_string(self, obj: Any) -> str:
        """Преобразует словарь или список в строку для индексации."""
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

    async def load_from_stoloto_data(self, stoloto_data: dict[str, Any]):
        """
        Загружает данные из СтоЛото и создаёт эмбеддинги.

        Args:
            stoloto_data: Словарь с данными от клиентов СтоЛото
        """
        start_time = time.time()
        async with self._lock:
            self.data = []
            texts = []
            stats = {'main': 0, 'packets': 0, 'tabs': 0}

            logger.debug('Начало загрузки данных в RAG систему')
            logger.debug(f'Источники данных: {list(stoloto_data.keys())}')

            # Обрабатываем данные из разных источников
            # Main categories
            if 'main' in stoloto_data and stoloto_data['main']:
                main_data = stoloto_data['main']
                if main_data and isinstance(main_data, dict) and 'data' in main_data:
                    data_list = main_data.get('data') or []
                    logger.debug(f'Обработка main categories: {len(data_list)} категорий')
                    for datum in data_list:
                        if not isinstance(datum, dict):
                            continue
                        contents_list = datum.get('contents') or []
                        for content in contents_list:
                            if not isinstance(content, dict):
                                continue
                            item = content.get('item', {})
                            if not isinstance(item, dict):
                                continue
                            # Обрабатываем различные типы контента
                            if 'contents' in item:
                                item_contents = item.get('contents') or []
                                for content_item in item_contents:
                                    if not isinstance(content_item, dict):
                                        continue
                                    lottery_data = self._extract_lottery_info(content_item)
                                    if lottery_data:
                                        text = self._dict_to_string(lottery_data)
                                        texts.append(text)
                                        self.data.append(lottery_data)
                                        stats['main'] += 1
                    logger.debug(f'Извлечено лотерей из main: {stats["main"]}')

            # Packets (list)
            if 'list' in stoloto_data and stoloto_data['list']:
                list_data = stoloto_data['list']
                if list_data and isinstance(list_data, dict):
                    packets_list = list_data.get('packets') or []
                    logger.debug(f'Обработка packets: {len(packets_list)} пакетов')
                    for packet in packets_list:
                        if not isinstance(packet, dict):
                            continue
                        packet_data = {
                            'type': 'packet',
                            'name': packet.get('name', ''),
                            'price': packet.get('price', 0),
                            'description': packet.get('description', ''),
                            'bets_count': len(packet.get('bets') or []),
                        }
                        text = self._dict_to_string(packet_data)
                        texts.append(text)
                        self.data.append(packet_data)
                        stats['packets'] += 1
                    logger.debug(f'Извлечено пакетов: {stats["packets"]}')

            # Tabs (active draws)
            if 'tabs' in stoloto_data and stoloto_data['tabs']:
                tabs_data = stoloto_data['tabs']
                if tabs_data and isinstance(tabs_data, dict):
                    tabs_list = tabs_data.get('data') or []
                    logger.debug(f'Обработка tabs: {len(tabs_list)} табов')
                    for tab in tabs_list:
                        if not isinstance(tab, dict):
                            continue
                        tab_data = {
                            'type': 'active_draw',
                            'lottery_code': tab.get('lotteryCode', '').upper(),
                            'draw': tab.get('draw', 0),
                            'prize_title': tab.get('prizeTitle', ''),
                            'value': tab.get('value', ''),
                        }
                        text = self._dict_to_string(tab_data)
                        texts.append(text)
                        self.data.append(tab_data)
                        stats['tabs'] += 1
                    logger.debug(f'Извлечено табов: {stats["tabs"]}')

            # Подсчитываем общий размер данных
            total_text_length = sum(len(text) for text in texts)
            avg_text_length = total_text_length / len(texts) if texts else 0

            logger.info(
                f'RAG: Обработано элементов - main: {stats["main"]}, packets: {stats["packets"]}, tabs: {stats["tabs"]}, '
                f'всего: {len(texts)}'
            )
            logger.info(
                f'RAG: Размер данных - всего символов: {total_text_length}, средний размер текста: {avg_text_length:.1f}'
            )

            if texts:
                logger.info(f'RAG: Создание эмбеддингов для {len(texts)} элементов...')
                embed_start = time.time()
                # Выполняем в отдельном потоке, чтобы не блокировать event loop
                self.embeddings = await asyncio.to_thread(
                    self.model.encode,
                    texts,
                )
                embed_time = time.time() - embed_start
                embedding_shape = self.embeddings.shape if self.embeddings is not None else None
                logger.info(
                    f'RAG: Эмбеддинги созданы успешно за {embed_time:.2f}с. '
                    f'Размерность: {embedding_shape}, размер в памяти: ~{self.embeddings.nbytes / 1024 / 1024:.2f} MB'
                )
            else:
                logger.warning('RAG: Нет данных для создания эмбеддингов')
                self.embeddings = None

            total_time = time.time() - start_time
            logger.info(f'RAG: Загрузка данных завершена за {total_time:.2f}с')

    def _extract_lottery_info(self, content_item: dict[str, Any]) -> dict[str, Any] | None:
        """Извлекает информацию о лотерее из элемента контента."""
        if not isinstance(content_item, dict):
            return None

        lottery = content_item.get('lottery')
        if not lottery or not isinstance(lottery, dict):
            return None

        lottery_data = {
            'type': 'lottery',
            'code': lottery.get('code', ''),
            'name': lottery.get('name', ''),
            'lottery_type': lottery.get('lotteryType', ''),
        }

        # Добавляем информацию о призах
        if content_item.get('prizeTitle'):
            lottery_data['prize_title'] = content_item['prizeTitle']
        if content_item.get('prizeSum'):
            lottery_data['prize_sum'] = content_item['prizeSum']
        if content_item.get('superPrize'):
            lottery_data['super_prize'] = content_item['superPrize']

        return lottery_data

    async def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """
        Выполняет семантический поиск.

        Args:
            query: Поисковый запрос
            top_k: Количество результатов

        Returns:
            Список результатов с данными и оценкой схожести
        """
        start_time = time.time()
        logger.debug(f'RAG Search: Запрос "{query[:50]}..." (длина: {len(query)}), top_k: {top_k}')

        if self.embeddings is None or len(self.data) == 0:
            logger.warning('RAG Search: Эмбеддинги не загружены, возвращаю пустой список')
            return []

        logger.debug(f'RAG Search: База данных содержит {len(self.data)} элементов')

        # Выполняем в отдельном потоке
        encode_start = time.time()
        query_embedding = await asyncio.to_thread(
            self.model.encode,
            [query],
        )
        encode_time = time.time() - encode_start
        logger.debug(f'RAG Search: Создание эмбеддинга запроса заняло {encode_time:.3f}с')

        similarity_start = time.time()
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        top_indices = np.argsort(similarities)[::-1][:top_k]
        similarity_time = time.time() - similarity_start
        logger.debug(f'RAG Search: Вычисление схожести заняло {similarity_time:.3f}с')

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            results.append({
                'data': self.data[idx],
                'score': score,
            })
            logger.debug(f'RAG Search: Результат #{len(results)} - тип: {self.data[idx].get("type")}, score: {score:.4f}')

        total_time = time.time() - start_time
        logger.info(
            f'RAG Search: Найдено {len(results)} результатов за {total_time:.3f}с '
            f'(encode: {encode_time:.3f}с, similarity: {similarity_time:.3f}с)'
        )

        return results

