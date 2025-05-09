import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv

from exceptions import APIResponseError, ApiAnswerException


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
        raise ValueError(
            f'Отсутствуют переменные окружения: {", ".join(missing_tokens)}')
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        logging.debug(f'Бот отправляет сообщение: {message}')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except (telebot.apihelper.ApiException, requests.RequestException) as e:
        logger.error(f'Бот не смог отправить сообщение: {e}')
        raise


def get_api_answer(timestamp):
    """Делает запрос к API-сервиса Яндекс.Практикум."""
    request_kwargs = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }

    try:
        logger.debug(
            f'Бот делает запрос к API-сервису Яндекс.Практикум: {ENDPOINT}'
        )
        response = requests.get(**request_kwargs)
        if response.status_code != HTTPStatus.OK:
            raise APIResponseError(
                f'Ошибка при запросе к API-сервису '
                f'URL: {ENDPOINT}'
                f'Параметры: {request_kwargs}',
                f'Код ошкибки: {response.status_code}'
            )
        logger.info(
            'Бот получил ответ от API-сервиса Яндекс.Практикум'
        )
        return response.json()

    except requests.RequestException as e:
        logger.error(f'Бот не смог получить ответ от API-сервиса: {e}')
        raise ApiAnswerException(f'Ошибка при запросе к API-сервису: {e}')


def check_response(response):
    """Проверяет корректность ответа API."""
    if not isinstance(response, dict):
        logger.error('Ответ API не является словарем')
        raise TypeError('Ответ API не является словарем')

    if 'homeworks' not in response:
        logger.error('Ответ API не содержит ключа "homeworks"')
        raise KeyError('Ответ API не содержит ключа "homeworks"')

    if not isinstance(response['homeworks'], list):
        logger.error('Значение ключа "homeworks" не является списком')
        raise TypeError('Значение ключа "homeworks" не является списком')

    return response['homeworks']


def parse_status(homework):
    """Излекает информацию о конкретной домашней работе."""
    """Статусы этой домашки."""
    logging.debug(
        f'Бот извлекает информацию о конкретной домашней работе: {homework}'
    )
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if not homework_name:
        logger.error('Отсутствует название домашней работы')
        raise KeyError('homework_name отсутствует')

    if not homework_status:
        logger.error('Отсутствует статус домашней работы')
        raise KeyError('status отсутствует')

    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if not verdict:
        logger.error('Вердикт отсутствует')
        raise ValueError('Вердикт отсутствует')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message_safe(bot, message):
    """Попытка отправки сообщения и логирует ошибки."""
    try:
        send_message(bot, message)
    except Exception as send_err:
        logging.error(
            f'Ошибка при попытке отправить сообщение: {send_err}'
        )


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
    except ValueError as e:
        logger.critical(f'Отсутствуют переменные окружения: {e}')
        sys.exit()
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
                send_message_safe(bot, message)
                last_message = message

            timestamp = response.get('current_date', timestamp)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_message:
                send_message_safe(bot, message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
