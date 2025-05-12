import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv

from exceptions import (
    SendMessageError,
    ApiRequestException,
    UnknownHomeworkStatusError,
    APIResponseError
)


load_dotenv()

LOG_FILE_PATH = os.path.join(os.path.expanduser('~'), 'bot.log')


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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

file_handler = RotatingFileHandler(
    LOG_FILE_PATH,
    maxBytes=50000000,
    backupCount=5,
    encoding='utf-8'
)

file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


def check_tokens():
    """Проверяет наличие переменных окружения."""
    missing_tokens = [name for name, value in [
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID)
    ] if not value]

    if missing_tokens:
        logger.critical(
            f'Отсутствуют переменные окружения: {", ".join(missing_tokens)}'
        )
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        logging.debug(f'Бот отправляет сообщение: {message}')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except (telebot.apihelper.ApiException, requests.RequestException) as e:
        logger.error(f'Бот не смог отправить сообщение: {e}')
        raise SendMessageError(f'Бот не смог отправить сообщение: {e}')


def get_api_answer(timestamp):
    """Делает запрос к API-сервиса Яндекс.Практикум."""
    request_kwargs = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }

    logger.debug(
        f'Бот делает запрос к API-сервису Яндекс.Практикум: {ENDPOINT}'
    )

    try:
        response = requests.get(**request_kwargs)
    except requests.RequestException as e:
        raise ApiRequestException(
            f'Ошибка при запросе к API: {e}'
        )
    if response .status_code != HTTPStatus.OK:
        raise APIResponseError(
            f'API вернул код ответа: {response.status_code}'
        )
    logger.info('Бот получил ответ от API')
    return response.json()


def check_response(response):
    """Проверяет корректность ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')

    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homeworks" в ответе API')

    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение ключа "homeworks" не является списком')

    return response['homeworks']


def parse_status(homework):
    """Излекает информацию о конкретной домашней работе."""
    """Статусы этой домашки."""
    logging.debug(
        f'Бот извлекает информацию о конкретной домашней работе: {homework}'
    )
    if 'homework_name' not in homework:
        raise ValueError('Отсутствует название домашней работы')

    if 'status' not in homework:
        raise ValueError('Отсутствует статус домашней работы')

    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_VERDICTS:
        raise UnknownHomeworkStatusError(
            f'Неизвестный статус домашней работы: {homework_status}'
        )

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют переменные окружения')
        sys.exit(1)
    # Создаем объект класса бота
    bot = telebot.TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''  # Переменная для хранения последнего сообщения

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = 'Домашних работ нет'
                logging.debug(message)

            if message != last_message:
                send_message(bot, message)
                last_message = message
                logger.info(f'Бот отправил сообщение: {message}')

            timestamp = response.get('current_date', timestamp)

        except SendMessageError as send_err:
            logger.error(f'Ошибка отправки сообщения: {send_err}')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_message:
                send_message(bot, message)
                last_message = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
