import asyncio
import json
import time
import uuid

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from src.integrations.ai import Agent
from src.integrations.ai.websocket_codes import WebSocketCode
from src.integrations.redis import RedisClient
from src.integrations.stoloto import StolotoClient
from src.core.config import env_config
from src.core.logger import get_logger
from src.presentation.routers import stoloto

logger = get_logger(__name__)

router = APIRouter(prefix='/api/ai', tags=['ai'])

_agent: Agent | None = None

# Время жизни контекста чата в Redis (30 минут)
CHAT_CONTEXT_TTL = 30 * 60


def get_agent() -> Agent:
    """Dependency для получения Agent."""
    global _agent
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


def _send_message(websocket: WebSocket, code: WebSocketCode, data: dict | list | None = None):
    """
    Отправляет структурированное сообщение клиенту.

    Args:
        websocket: WebSocket соединение
        code: Код сообщения
        data: Данные сообщения
    """
    message = {'code': code.value, 'data': data}
    return websocket.send_text(json.dumps(message, ensure_ascii=False))


def _format_response_for_user(result: dict) -> str:
    """
    Форматирует ответ агента в человекочитаемый текст.

    Args:
        result: Результат от agent.process_query с полями action и content

    Returns:
        Человекочитаемый текст ответа
    """
    action = result.get('action', 'answer')
    content = result.get('content', '')

    # Если content уже строка, возвращаем как есть (самый частый случай)
    if isinstance(content, str):
        return content

    # Если action == 'search' и content - список лотерей
    if action == 'search' and isinstance(content, list):
        if not content:
            return 'К сожалению, не удалось найти подходящие лотереи. Попробуйте уточнить запрос.'

        response_parts = ['Вот подходящие лотереи:\n']
        for i, lottery in enumerate(content, 1):
            if not isinstance(lottery, dict):
                continue

            name = lottery.get('name', 'Неизвестная лотерея')
            response_parts.append(f'\n{i}. {name}')

            if lottery.get('price'):
                response_parts.append(f'   💰 Цена: {lottery["price"]} ₽')
            if lottery.get('prize'):
                prize = lottery['prize']
                if isinstance(prize, (int, float)):
                    if prize >= 1_000_000:
                        prize_str = f'{prize / 1_000_000:.1f} млн ₽'
                    else:
                        prize_str = f'{prize:,} ₽'.replace(',', ' ')
                else:
                    prize_str = str(prize)
                response_parts.append(f'   🎁 Приз: {prize_str}')
            if lottery.get('frequency'):
                response_parts.append(f'   ⏰ Частота: {lottery["frequency"]}')
            if lottery.get('speed'):
                response_parts.append(f'   ⚡ Скорость: {lottery["speed"]}')
            if lottery.get('description'):
                response_parts.append(f'   📝 {lottery["description"]}')

        return '\n'.join(response_parts)

    # Если content - словарь, пытаемся извлечь полезную информацию
    if isinstance(content, dict):
        # Пытаемся найти описание или текст
        return content.get('description') or content.get('text') or content.get('message') or str(content)

    # Для всех остальных случаев просто преобразуем в строку
    return str(content)


@router.websocket('/chat')
async def websocket_chat(websocket: WebSocket):
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

    # Инициализируем агента заранее
    logger.info('WebSocket: Инициализация агента...')
    agent = get_agent()
    redis_client = stoloto.get_redis_client()
    logger.info('WebSocket: Агент готов к работе')

    # Отправляем подтверждение подключения
    await _send_message(websocket, WebSocketCode.CONNECTION_ESTABLISHED, None)

    # Запрашиваем контекст чата у клиента
    logger.info('WebSocket: Запрос контекста чата у клиента')
    await _send_message(websocket, WebSocketCode.REQUEST_CHAT_CONTEXT, None)

    chat_context: list[dict[str, str]] = []
    chat_context_key = f'websocket:chat_context:{session_id}'

    try:
        # Получаем контекст от клиента (с таймаутом 10 секунд)
        context_received = False
        try:
            # Пытаемся получить контекст с таймаутом
            message = await asyncio.wait_for(websocket.receive(), timeout=10.0)
            
            if message.get('type') == 'websocket.disconnect':
                logger.info('WebSocket: Клиент отключился до отправки контекста')
                return
            
            if 'text' in message:
                raw_message = message['text']
                try:
                    message_data = json.loads(raw_message)
                    code = message_data.get('code')
                    data = message_data.get('data')
                    
                    if code == 'CHAT_CONTEXT':
                        if isinstance(data, list):
                            chat_context = data
                            logger.info(f'WebSocket: Получен контекст чата от клиента ({len(chat_context)} сообщений)')
                            
                            # Сохраняем в Redis
                            await redis_client.set_json(chat_context_key, chat_context, CHAT_CONTEXT_TTL)
                            logger.info(f'WebSocket: Контекст сохранён в Redis с ключом {chat_context_key}')
                            
                            await _send_message(websocket, WebSocketCode.CHAT_CONTEXT_RECEIVED, {'count': len(chat_context)})
                            context_received = True
                        else:
                            logger.warning('WebSocket: Контекст чата не в формате списка, используем пустой')
                            chat_context = []
                            context_received = True
                    else:
                        logger.warning(f'WebSocket: Неожиданный код при ожидании контекста: {code}, используем пустой')
                        chat_context = []
                        context_received = True
                except json.JSONDecodeError:
                    logger.warning('WebSocket: Не удалось распарсить сообщение с контекстом, используем пустой')
                    chat_context = []
                    context_received = True
            else:
                logger.warning('WebSocket: Получено сообщение без текста при ожидании контекста')
                chat_context = []
                context_received = True
        except asyncio.TimeoutError:
            logger.warning('WebSocket: Таймаут ожидания контекста чата, продолжаем с пустым контекстом')
            chat_context = []
            context_received = True

        # Основной цикл обработки сообщений
        while True:
            try:
                logger.debug('WebSocket: Ожидание сообщения от клиента...')
                message = await websocket.receive()
                
                if message.get('type') == 'websocket.disconnect':
                    logger.info('WebSocket: Получен сигнал отключения от клиента')
                    break
                
                if 'text' not in message:
                    logger.warning(f'WebSocket: Получено сообщение без текста: {message}')
                    continue
                
                raw_message = message['text']
                logger.debug(f'WebSocket: Получено сообщение (длина: {len(raw_message)})')

                # Парсим JSON сообщение
                try:
                    message_data = json.loads(raw_message)
                    code = message_data.get('code')
                    data = message_data.get('data')
                    
                    logger.info(f'WebSocket: Получено сообщение с кодом: {code}')
                    
                    if code == 'SEND_MESSAGE':
                        if not isinstance(data, dict) or 'message' not in data:
                            await _send_message(
                                websocket,
                                WebSocketCode.ERROR,
                                {'message': 'Неверный формат данных для SEND_MESSAGE'}
                            )
                            continue
                        
                        user_message = data['message']
                        if not user_message.strip():
                            await _send_message(
                                websocket,
                                WebSocketCode.ERROR,
                                {'message': 'Сообщение не может быть пустым'}
                            )
                            continue
                        
                        logger.info(f'WebSocket: Обработка сообщения: "{user_message[:50]}..."')
                        request_start = time.time()
                        
                        # Отправляем статусы обработки
                        try:
                            # Определяем намерение (может потребоваться Grok)
                            await _send_message(
                                websocket,
                                WebSocketCode.STATUS_GROK_PROCESSING,
                                {'message': 'Анализирую запрос...'}
                            )
                            
                            intent = await agent._detect_intent(user_message, chat_context)
                            
                            if intent == 'search':
                                # Отправляем статус RAG
                                await _send_message(
                                    websocket,
                                    WebSocketCode.STATUS_RAG_PROCESSING,
                                    {'message': 'Ищу подходящие лотереи в базе знаний...'}
                                )
                                
                                # Может потребоваться получение данных от СтоЛото
                                if not agent.rag.data:
                                    await _send_message(
                                        websocket,
                                        WebSocketCode.STATUS_STOLOTO_FETCHING,
                                        {'message': 'Загружаю актуальные данные о лотереях...'}
                                    )
                            
                            # Обрабатываем запрос
                            result = await agent.process_query(
                                user_query=user_message,
                                chat_context=chat_context,
                                force_refresh_rag=False,
                            )
                            
                            # Форматируем ответ
                            formatted_text = _format_response_for_user(result)
                            
                            # Формируем ответ
                            response_data = {
                                'action': result.get('action', 'answer'),
                                'content': result.get('content', ''),
                                'formatted_text': formatted_text,
                            }
                            
                            # Отправляем ответ
                            await _send_message(websocket, WebSocketCode.RESPONSE_MESSAGE, response_data)
                            
                            # Обновляем контекст
                            chat_context.append({'role': 'user', 'content': user_message})
                            chat_context.append({'role': 'assistant', 'content': formatted_text})
                            
                            # Ограничиваем размер контекста
                            if len(chat_context) > 20:
                                chat_context = chat_context[-20:]
                            
                            # Обновляем контекст в Redis
                            await redis_client.set_json(chat_context_key, chat_context, CHAT_CONTEXT_TTL)
                            
                            request_time = time.time() - request_start
                            logger.info(
                                f'WebSocket: Запрос обработан за {request_time:.2f}с. '
                                f'Действие: {result["action"]}, контекст: {len(chat_context)} сообщений'
                            )
                        except Exception as e:
                            logger.error(f'WebSocket: Ошибка при обработке сообщения: {e}', exc_info=True)
                            await _send_message(
                                websocket,
                                WebSocketCode.ERROR,
                                {'message': 'Произошла ошибка при обработке запроса. Попробуйте ещё раз.', 'error': str(e)}
                            )
                    else:
                        logger.warning(f'WebSocket: Неизвестный код сообщения: {code}')
                        await _send_message(
                            websocket,
                            WebSocketCode.ERROR,
                            {'message': f'Неизвестный код сообщения: {code}'}
                        )
                        
                except json.JSONDecodeError as e:
                    logger.error(f'WebSocket: Ошибка парсинга JSON: {e}')
                    await _send_message(
                        websocket,
                        WebSocketCode.ERROR,
                        {'message': 'Ошибка: неверный формат JSON'}
                    )

            except WebSocketDisconnect:
                logger.info('WebSocket: Клиент отключился')
                break
            except Exception as e:
                logger.error(f'WebSocket: Неожиданная ошибка: {e}', exc_info=True)
                try:
                    await _send_message(
                        websocket,
                        WebSocketCode.ERROR,
                        {'message': 'Произошла неожиданная ошибка'}
                    )
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f'WebSocket: Клиент отключился {websocket.client}')
    except Exception as e:
        logger.error(f'WebSocket: Критическая ошибка: {e}', exc_info=True)
    finally:
        # Удаляем контекст из Redis при отключении
        try:
            await redis_client.client.delete(chat_context_key)
            logger.info(f'WebSocket: Контекст удалён из Redis (ключ: {chat_context_key})')
        except Exception as e:
            logger.warning(f'WebSocket: Не удалось удалить контекст из Redis: {e}')
        
        logger.info(f'WebSocket: Завершение работы с клиентом {websocket.client}, session_id: {session_id}')


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
        raise HTTPException(status_code=500, detail=f'Ошибка при анализе: {str(e)}') from e


@router.post('/refresh-rag')
async def refresh_rag():
    """
    Принудительно обновляет данные в RAG системе.

    Загружает свежие данные из СтоЛото и пересоздаёт эмбеддинги.
    """
    try:
        agent = get_agent()
        await agent._load_rag_data()
        return {'status': 'success', 'message': 'RAG система обновлена'}
    except Exception as e:
        logger.error(f'Ошибка при обновлении RAG: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=f'Ошибка при обновлении RAG: {str(e)}') from e

