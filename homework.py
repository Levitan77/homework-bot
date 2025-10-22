import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv

from exceptions import NoTokensException, PracException

load_dotenv()


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
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    tokens_not_exist = []
    for tok in tokens:
        if tokens[tok] is None:
            tokens_not_exist.append(tok)
            logging.critical(f'Отсутствует токен {tok}')
    if tokens_not_exist:
        message = f'Отсутствуют токены: {", ".join(tokens_not_exist)}'
        raise NoTokensException(message)


def send_message(bot, message):
    """Отправка сообщения в тегерам."""
    logging.debug('Попытка отправить сообщение')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение отправлено')
    except (telebot.apihelper.ApiException,
            requests.RequestException) as error:
        logging.error(
            f'Не удалось отправить сообщение в телеграм {error}'
        )


def get_api_answer(timestamp):
    """Запрос на получение статусов домашки."""
    params = {'from_date': timestamp}
    request_data = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': params,
    }
    logging.debug('Попытка отправить запрос к API')
    try:
        response = requests.get(**request_data)
    except requests.RequestException as error:
        message = (
            'Не удалось получить статус домашки {error}. '
            'Параметры запроса: url={url} headers={headers} '
            'params={params}'.format(error=error, **request_data)
        )
        raise PracException(message)

    if response.status_code != HTTPStatus.OK:
        message = (
            'Запрос выполнился со статусом {status}. '
            'Параметры запроса: url={url} headers={headers} '
            'params={params}'.format(
                status=response.status_code, **request_data)
        )

        raise PracException(message)
    return response.json()


def check_response(response):
    """Провека структуры ответа API."""
    if not isinstance(response, dict):
        message = f'В ответе API пришел не словарь, а тип {type(response)}'
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'Отсутствует ключ homeworks в ответе'
        raise KeyError(message)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        message = 'По ключу homeworks отсутствует список'
        raise TypeError(message)
    return homeworks


def parse_status(homework):
    """Поиск статуса домашки."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_status:
        raise ValueError('Отсутствует ключ homework_status в словаре домашки')
    if not homework_name:
        raise ValueError('Отсутствует ключ homework_name в словаре домашки')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Неизвестный статус')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telebot.TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks_data = check_response(response)
            if homeworks_data:
                homework_data = homeworks_data[0]
                message = parse_status(homework_data)
                if send_message(bot, message):
                    timestamp = response.get('current_date', timestamp)
                else:
                    logging.error('Ошибка работы телеграма')
            else:
                logging.debug('Новых проверок не поступало')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_error_message:
                logging.error(message)
                send_message(bot, message)
                message = last_error_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        stream=sys.stdout,
        format='%(asctime)s %(levelname)s %(message)s'
    )
    logger = logging.getLogger(__name__)

    logger.addHandler(
        logging.StreamHandler()
    )

    main()
