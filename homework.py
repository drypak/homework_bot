import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv


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


def check_tokens(tokens):
    """Проверяет наличие переменных окружения."""
    missing_tokens = []
    for token in tokens:
        if not token:
            missing_tokens.append(token)

    if missing_tokens:
        logging.warning(
            f'Отсутствуют токены: {missing_tokens}'
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


class APIResponseError(Exception):
    """Класс для обработки ошибок в ответе API-сервиса Яндекс.Практикум."""

    pass


def get_api_answer(timestamp):
    """Делает запрос к API-сервиса Яндекс.Практикум."""
    try:
        logger.debug(
            f'Бот делает запрос к API-сервису Яндекс.Практикум: {ENDPOINT}'
        )
        request_kwargs = {
            'url': ENDPOINT,
            'headers': HEADERS,
            'params': {'from_date': timestamp}
        }
        response = requests.get(**request_kwargs)

        if response.status_code == HTTPStatus.OK:
            logger.info('Бот получил ответ от API-сервиса Яндекс.Практикум')
            return response.json()

        if response.status_code != HTTPStatus.OK:
            logger.error(
                f'При запросе к API возникла ошибка: {response.status_code}'
            )
            raise APIResponseError(
                f'Ошибка при запросе к API-сервису Яндекс.Практикум '
                f'URL: {ENDPOINT}',
                f'Параметры: {request_kwargs["params"]}',
                f'Код ошибки: {response.status_code}'
            )

    except requests.RequestException as e:
        logger.error(
            f'Бот не смог получить ответ от API-сервиса Яндекс.Практикум: {e}'
        )
        return None


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

    if homework_name and homework_status:
        verdict = HOMEWORK_VERDICTS.get(homework_status)
        if not verdict:
            logger.error('Вердикт не определен')
            raise ValueError(
                f'Вердикт не определен '
                f'статус домашки: {homework_status}'
            )
    else:
        logger.error('Отсутствует имя или статус домашки')
        raise KeyError(
            'Отсутствует имя или статус домашки'
        )

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical('Отсутствуют переменные окружения')
        sys.exit()

    # Создаем объект класса бота
    bot = telebot.TeleBot(token=TELEGRAM_TOKEN)
    timestamp1 = int(time.time())
    last_message = ''  # Переменная для хранения последнего сообщения

    while True:
        try:
            response = get_api_answer(timestamp1)
            homeworks = check_response(response)
            timestamp2 = response.get('current_date')
            if homeworks and timestamp1 != timestamp2:
                timestamp1 = timestamp2
                message = parse_status(homeworks[0])
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_message:
                try:
                    send_message(bot, message)
                    last_message = message
                except Exception as send_err:
                    logger.error(
                        f'Ошибка при попытке отправить сообщение: {send_err}'
                    )
            logger.error(message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
