"""Роутер для AI endpoints."""

import json
import uuid

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from src.integrations.ai import Agent
from src.integrations.ai.websocket_codes import WebSocketCode
from src.core.config import env_config
from src.core.logger import get_logger
from src.presentation.routers import stoloto
from src.services.ai import ChatService

logger = get_logger(__name__)

router = APIRouter(prefix='/api/ai', tags=['ai'])

_agent: Agent | None = None
_chat_service: ChatService | None = None


def get_agent() -> Agent:
    """Dependency для получения Agent."""
    global _agent # noqa
    if _agent is None:
        stoloto_client = stoloto.get_stoloto_client()
        redis_client = stoloto.get_redis_client()
        _agent = Agent(
            stoloto_client=stoloto_client,
            redis_client=redis_client,
            api_key=env_config.OPENAI_API_KEY,
            base_url=env_config.OPENAI_BASE_URL,
        )
        logger.info('Agent инициализирован')
    return _agent


def get_chat_service() -> ChatService:
    """Dependency для получения ChatService."""
    global _chat_service # noqa
    if _chat_service is None:
        agent = get_agent()
        redis_client = stoloto.get_redis_client()
        _chat_service = ChatService(agent=agent, redis_client=redis_client)
        logger.debug('ChatService инициализирован')
    return _chat_service


def _send_websocket_message(websocket: WebSocket, code: WebSocketCode, data: dict | list | None = None):
    """
    Отправляет структурированное сообщение клиенту через WebSocket.

    Args:
        websocket: WebSocket соединение
        code: Код сообщения
        data: Данные сообщения
    """
    message = {'code': code.value, 'data': data}
    return websocket.send_text(json.dumps(message, ensure_ascii=False))


@router.websocket('/chat')
async def websocket_chat(websocket: WebSocket): # noqa
    """
    WebSocket endpoint для чата с AI ботом.

    Протокол обмена JSON сообщениями с кодами:

    **1. Установка соединения:**
    - Сервер отправляет: {"code": "CONNECTION_ESTABLISHED", "data": null}
    - Сервер запрашивает контекст: {"code": "REQUEST_CHAT_CONTEXT", "data": null}

    **2. Клиент отправляет контекст:**
    ```json
    {
      "code": "CHAT_CONTEXT",
      "data": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
      ]
    }
    ```

    **3. Клиент отправляет сообщение:**
    ```json
    {
      "code": "SEND_MESSAGE",
      "data": {"message": "Текст сообщения"}
    }
    ```

    **4. Сервер отправляет статусы обработки:**
    ```json
    {"code": "STATUS_RAG_PROCESSING", "data": {"message": "Поиск в базе знаний..."}}
    {"code": "STATUS_GROK_PROCESSING", "data": {"message": "Обработка запроса..."}}
    {"code": "STATUS_STOLOTO_FETCHING", "data": {"message": "Получение данных..."}}
    ```

    **5. Сервер отправляет ответ:**
    ```json
    {
      "code": "RESPONSE_MESSAGE",
      "data": {
        "action": "search" | "answer",
        "content": "...",
        "formatted_text": "..."
      }
    }
    ```
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    logger.info(f'WebSocket: Подключение установлено с {websocket.client}, session_id: {session_id}')

    chat_service = get_chat_service()

    # Обёртки для работы с WebSocket
    async def receive_message():
        """Получает сообщение от клиента."""
        return await websocket.receive()

    async def send_message(code: WebSocketCode, data: dict | list | None = None):
        """Отправляет сообщение клиенту."""
        return await _send_websocket_message(websocket, code, data)

    try:
        # Инициализируем контекст чата
        chat_context = await chat_service.initialize_chat_context(
            session_id=session_id,
            receive_message=receive_message,
            send_message=send_message,
        )

        # Основной цикл обработки сообщений
        while True:
            try:
                logger.debug('Ожидание сообщения от клиента...')
                message = await websocket.receive()

                if message.get('type') == 'websocket.disconnect':
                    logger.info('Получен сигнал отключения от клиента')
                    break

                if 'text' not in message:
                    logger.debug(f'Получено сообщение без текста: {message}')
                    continue

                raw_message = message['text']
                logger.debug(f'Получено сообщение (длина: {len(raw_message)})')

                # Парсим JSON сообщение
                try:
                    message_data = json.loads(raw_message)
                    code = message_data.get('code')
                    data = message_data.get('data')

                    logger.debug(f'Получено сообщение с кодом: {code}')

                    if code == 'SEND_MESSAGE':
                        if not isinstance(data, dict) or 'message' not in data:
                            await send_message(
                                WebSocketCode.ERROR,
                                {'message': 'Неверный формат данных для SEND_MESSAGE'},
                            )
                            continue

                        user_message = data['message']
                        if not user_message.strip():
                            await send_message(
                                WebSocketCode.ERROR,
                                {'message': 'Сообщение не может быть пустым'},
                            )
                            continue

                        # Обрабатываем сообщение через сервис
                        await chat_service.process_user_message(
                            user_message=user_message,
                            chat_context=chat_context,
                            session_id=session_id,
                            send_message=send_message,
                        )
                    else:
                        logger.debug(f'Неизвестный код сообщения: {code}')
                        await send_message(
                            WebSocketCode.ERROR,
                            {'message': f'Неизвестный код сообщения: {code}'},
                        )

                except json.JSONDecodeError as e:
                    logger.debug(f'Ошибка парсинга JSON: {e}')
                    await send_message(
                        WebSocketCode.ERROR,
                        {'message': 'Ошибка: неверный формат JSON'},
                    )

            except WebSocketDisconnect:
                logger.info('Клиент отключился')
                break
            except Exception as e:
                logger.error(f'Неожиданная ошибка: {e}', exc_info=True)
                try:
                    await send_message(
                        WebSocketCode.ERROR,
                        {'message': 'Произошла неожиданная ошибка'},
                    )
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f'Клиент отключился {websocket.client}')
    except Exception as e:
        logger.error(f'Критическая ошибка: {e}', exc_info=True)
    finally:
        # Очищаем контекст при отключении
        await chat_service.cleanup_context(session_id)
        logger.info(f'Завершение работы с клиентом {websocket.client}, session_id: {session_id}')


@router.post('/analyze-archive')
async def analyze_archive(archive_data: dict | list):
    """
    Анализирует архивные данные лотерей.

    - **archive_data**: Архивные данные для анализа
    """
    try:
        agent = get_agent()
        analysis = await agent.analyze_archive(archive_data)
        return {'analysis': analysis}
    except Exception as e:
        logger.error(f'Ошибка при анализе архива: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=f'Ошибка при анализе: {e!s}') from e


@router.post('/refresh-rag')
async def refresh_rag():
    """
    Принудительно обновляет данные в RAG системе.

    Загружает свежие данные из СтоЛото и пересоздаёт эмбеддинги.
    """
    try:
        agent = get_agent()
        await agent._load_rag_data() # noqa
        return {'status': 'success', 'message': 'RAG система обновлена'}
    except Exception as e:
        logger.error(f'Ошибка при обновлении RAG: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=f'Ошибка при обновлении RAG: {e!s}') from e
