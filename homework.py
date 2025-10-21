import logging
import os
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import PracException, TelegramException

load_dotenv()


logging.basicConfig(
    level=logging.DEBUG,
    filename='homework.log',
    filemode='w',
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

logger.addHandler(
    logging.StreamHandler()
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка наличия токенов в .env."""
    if not PRACTICUM_TOKEN:
        logger.critical('Отсутствует токен Практикума')
        return False
    if not TELEGRAM_CHAT_ID:
        logger.critical('Отсутствует id чата')
        return False
    if not TELEGRAM_TOKEN:
        logger.critical('Отсутствует токен Телеграма')
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения в тегерам."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение отправлено')
    except Exception as error:
        raise TelegramException(
            f'Не удалось отправить сообщение в телеграм {error}'
        )


def get_api_answer(timestamp):
    """Запрос на получение статусов домашки."""
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=headers, params=params)
        if response.status_code != HTTPStatus.OK:
            message = f'Эндпоинт практикума {ENDPOINT} недоступен.'
            logger.error(message)
            raise PracException(message)
        return response.json()
    except Exception as error:
        message = f'Не удалось получить статус домашки {error}'
        logger.error(message)
        raise PracException(message)


def check_response(response):
    """Провека структуры ответа API."""
    if not isinstance(response, dict):
        message = 'В ответе API пришел не словарь'
        logger.error(message)
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'Отсутствует ключ homeworks в ответе'
        logger.error(message)
        raise KeyError(message)
    if 'current_date' not in response:
        message = 'Отсутствует ключ current_date в ответе'
        logger.error(message)
        raise KeyError(message)
    if not isinstance(response['homeworks'], list):
        message = 'По ключу homeworks отсутствует список'
        logger.error(message)
        raise TypeError(message)
    return response['homeworks']


def parse_status(homework):
    """Поиск статуса домашки."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_status or not homework_name:
        raise ValueError('Отсутствуют нужные ключи в словаре домашки')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Неизвестный статус')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit('Нет необходимых переменных в .env')

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_status_message = ''
    last_error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks_data = check_response(response)
            if homeworks_data:
                homework_data = homeworks_data[0]
                message = parse_status(homework_data)
                if last_status_message != message:
                    last_status_message = message
                    send_message(bot, message)
                    timestamp = response.get('current_date')
                    logger.debug('Сообщение успешно отправлено')
            else:
                logger.debug('Новых проверок не поступало')
        except TelegramException as error:
            logging.error(f'Ошибка работы телеграма {error}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_error_message:
                logging.error(message)
                send_message(bot, message)
                message = last_error_message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
