class TelegramException(Exception):
    """Сбой при отправке сообщения в телеграм."""

    pass


class PracException(Exception):
    """Сбой при получении данных статуса по API"""

    pass
