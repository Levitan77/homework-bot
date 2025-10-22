class PracException(Exception):
    """Сбой при получении данных статуса по API"""


class NoTokensException(Exception):
    """Отсутствуют необходимые токены в файле .env"""
