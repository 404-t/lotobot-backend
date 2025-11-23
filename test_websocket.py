#!/usr/bin/env python3
"""
Простой скрипт для тестирования WebSocket соединения с AI ботом.

Установка зависимостей:
    pip install websockets

Использование:
    python test_websocket.py                    # Интерактивный режим
    python test_websocket.py --scenario 1       # Запуск сценария 1
    python test_websocket.py --url ws://...     # С кастомным URL
"""

import asyncio
import json
import sys

import websockets
from websockets.exceptions import ConnectionClosed


class WebSocketTester:
    """Простой тестер WebSocket соединения."""

    def __init__(self, url: str = 'ws://localhost:8000/api/ai/chat'):
        self.url = url
        self.websocket = None

    async def connect(self):
        """Подключается к WebSocket серверу."""
        try:
            print(f'🔌 Подключение к {self.url}...')
            self.websocket = await websockets.connect(self.url)
            print('✅ Подключение установлено!\n')
            return True
        except Exception as e:
            print(f'❌ Ошибка подключения: {e}')
            return False

    async def send(self, code: str, data=None):
        """Отправляет сообщение с кодом."""
        message = {'code': code, 'data': data}
        await self.websocket.send(json.dumps(message, ensure_ascii=False))
        print(f'📤 Отправлено: {code}')

    async def receive(self):
        """Получает и выводит сообщение от сервера."""
        try:
            response = await self.websocket.recv()
            data = json.loads(response)
            code = data.get('code', 'UNKNOWN')
            data_content = data.get('data')

            # Красиво выводим в зависимости от кода
            if code == 'CONNECTION_ESTABLISHED':
                print('✅ Соединение установлено')
            elif code == 'REQUEST_CHAT_CONTEXT':
                print('📋 Сервер запрашивает контекст чата')
            elif code == 'CHAT_CONTEXT_RECEIVED':
                count = data_content.get('count', 0) if isinstance(data_content, dict) else 0
                print(f'✅ Контекст получен ({count} сообщений)')
            elif code == 'STATUS_RAG_PROCESSING':
                msg = data_content.get('message', '') if isinstance(data_content, dict) else ''
                print(f'  🔄 {msg}')
            elif code == 'STATUS_GROK_PROCESSING':
                msg = data_content.get('message', '') if isinstance(data_content, dict) else ''
                print(f'  🤖 {msg}')
            elif code == 'STATUS_STOLOTO_FETCHING':
                msg = data_content.get('message', '') if isinstance(data_content, dict) else ''
                print(f'  📡 {msg}')
            elif code == 'RESPONSE_MESSAGE':
                print('\n💬 Ответ бота:')
                if isinstance(data_content, dict):
                    formatted = data_content.get('formatted_text', '')
                    if formatted:
                        print(f'   {formatted}')
                    else:
                        print(f'   {json.dumps(data_content, ensure_ascii=False, indent=2)}')
            elif code == 'ERROR':
                msg = data_content.get('message', '') if isinstance(data_content, dict) else ''
                print(f'❌ Ошибка: {msg}')
            else:
                print(f'📥 Получено: {code}')

            return data
        except ConnectionClosed:
            print('❌ Соединение закрыто')
            return None
        except Exception as e:
            print(f'❌ Ошибка получения: {e}')
            return None

    async def initialize(self):
        """Инициализирует соединение: получает запрос контекста и отправляет его."""
        print('\n' + '=' * 60)
        print('🔄 ИНИЦИАЛИЗАЦИЯ СОЕДИНЕНИЯ')
        print('=' * 60)

        # Ждём CONNECTION_ESTABLISHED
        await self.receive()

        # Ждём REQUEST_CHAT_CONTEXT
        await self.receive()

        # Отправляем контекст (пустой для нового чата)
        print('📤 Отправка контекста чата...')
        await self.send('CHAT_CONTEXT', [])

        # Ждём подтверждения
        await self.receive()

        print('\n✅ Готово к работе!\n')

    async def send_message(self, message: str):
        """Отправляет сообщение и получает ответ с обработкой статусов."""
        print(f'\n📝 Сообщение: "{message}"')
        print('─' * 60)

        # Отправляем сообщение
        await self.send('SEND_MESSAGE', {'message': message})

        # Ожидаем ответ, обрабатывая промежуточные статусы
        while True:
            response = await self.receive()
            if not response:
                return None

            code = response.get('code')
            if code == 'RESPONSE_MESSAGE':
                return response.get('data')
            elif code == 'ERROR':
                return response

    async def run_scenario(self, scenario_num: int):
        """Запускает один из предопределённых сценариев."""
        scenarios = {
            1: {
                'name': 'Простое приветствие',
                'messages': ['Привет! Как тебя зовут?'],
            },
            2: {
                'name': 'Поиск быстрой лотереи',
                'messages': ['Подбери мне быструю лотерею с небольшим призом'],
            },
            3: {
                'name': 'Поиск лотереи с большим призом',
                'messages': ['Какие лотереи с самым большим призом?'],
            },
            4: {
                'name': 'Диалог с контекстом',
                'messages': [
                    'Привет!',
                    'Подбери мне лотерею',
                    'А какие ещё есть варианты?',
                ],
            },
            5: {
                'name': 'Общий вопрос',
                'messages': ['Расскажи о СтоЛото'],
            },
        }

        if scenario_num not in scenarios:
            print(f'❌ Сценарий {scenario_num} не найден. Доступны: {list(scenarios.keys())}')
            return

        scenario = scenarios[scenario_num]
        print('\n' + '=' * 60)
        print(f'🎬 СЦЕНАРИЙ {scenario_num}: {scenario["name"]}')
        print('=' * 60)

        for i, message in enumerate(scenario['messages'], 1):
            print(f'\n--- Шаг {i}/{len(scenario["messages"])} ---')
            await self.send_message(message)
            await asyncio.sleep(1)  # Небольшая пауза между сообщениями

        print('\n' + '=' * 60)
        print('✅ Сценарий завершён!')
        print('=' * 60)

    async def interactive_mode(self):
        """Интерактивный режим."""
        print('\n' + '=' * 60)
        print('🤖 ИНТЕРАКТИВНЫЙ РЕЖИМ')
        print('=' * 60)
        print('Введите сообщение (или "exit" для выхода, "help" для справки)\n')

        while True:
            try:
                user_input = input('Вы: ').strip()

                if not user_input:
                    continue

                if user_input.lower() == 'exit':
                    print('\n👋 До свидания!')
                    break

                if user_input.lower() == 'help':
                    print('\n📖 Справка:')
                    print('  - Введите сообщение для общения с ботом')
                    print('  - "exit" - выход')
                    print('  - "help" - эта справка\n')
                    continue

                await self.send_message(user_input)

            except KeyboardInterrupt:
                print('\n\n👋 Прерывание пользователем')
                break
            except Exception as e:
                print(f'\n❌ Ошибка: {e}\n')

    async def close(self):
        """Закрывает соединение."""
        if self.websocket:
            await self.websocket.close()
            print('\n🔌 Соединение закрыто')


async def main():
    """Главная функция."""
    import argparse

    parser = argparse.ArgumentParser(description='Тестирование WebSocket соединения с AI ботом')
    parser.add_argument(
        '--url',
        type=str,
        default='ws://localhost:8000/api/ai/chat',
        help='URL WebSocket endpoint',
    )
    parser.add_argument(
        '--scenario',
        type=int,
        choices=[1, 2, 3, 4, 5],
        help='Запустить предопределённый сценарий (1-5)',
    )

    args = parser.parse_args()

    tester = WebSocketTester(url=args.url)

    try:
        # Подключаемся
        if not await tester.connect():
            sys.exit(1)

        # Инициализируем соединение
        await tester.initialize()

        # Выбираем режим
        if args.scenario:
            await tester.run_scenario(args.scenario)
        else:
            await tester.interactive_mode()

    except KeyboardInterrupt:
        print('\n\n👋 Прерывание пользователем')
    except Exception as e:
        print(f'\n❌ Критическая ошибка: {e}')
        import traceback

        traceback.print_exc()
    finally:
        await tester.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n👋 До свидания!')
