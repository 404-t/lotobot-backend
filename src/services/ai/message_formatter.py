"""Форматирование сообщений для пользователя."""


class MessageFormatter:
    """Класс для форматирования ответов агента в человекочитаемый текст."""

    @staticmethod
    def format_response(result: dict) -> str:
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

