"""
Коды для WebSocket сообщений между клиентом и сервером.
"""

from enum import Enum


class WebSocketCode(str, Enum):
    """Коды для WebSocket сообщений."""

    # Запросы от сервера к клиенту
    REQUEST_CHAT_CONTEXT = 'REQUEST_CHAT_CONTEXT'  # Сервер запрашивает полный контекст чата

    # Запросы от клиента к серверу
    CHAT_CONTEXT = 'CHAT_CONTEXT'  # Клиент отправляет контекст чата
    SEND_MESSAGE = 'SEND_MESSAGE'  # Клиент отправляет сообщение

    # Статусы обработки от сервера к клиенту
    STATUS_RAG_PROCESSING = 'STATUS_RAG_PROCESSING'  # Запрос обрабатывается RAG системой
    STATUS_GROK_PROCESSING = 'STATUS_GROK_PROCESSING'  # Запрос обрабатывается Grok
    STATUS_STOLOTO_FETCHING = 'STATUS_STOLOTO_FETCHING'  # Получаю данные от СтоЛото

    # Ответы от сервера к клиенту
    RESPONSE_MESSAGE = 'RESPONSE_MESSAGE'  # Ответ на сообщение пользователя

    # Ошибки
    ERROR = 'ERROR'  # Ошибка при обработке

    # Системные
    CONNECTION_ESTABLISHED = 'CONNECTION_ESTABLISHED'  # Соединение установлено
    CHAT_CONTEXT_RECEIVED = 'CHAT_CONTEXT_RECEIVED'  # Контекст чата получен и сохранён

