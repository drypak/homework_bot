import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv


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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверяет наличие переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return all(tokens)


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение: {message}')
    except Exception as e:
        logger.error(f'Ошибка при отправке сообщения: {e}')


def get_api_answer(timestamp):
    """Делает запрос к API-сервиса Яндекс.Практикум."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if response.status_code != HTTPStatus.OK:
            raise Exception(
                f'Код ответа API: {response.status_code}'
            )
        return response.json()
    except Exception as e:
        raise ConnectionError(f'Ошибка при запросе к API: {e}')


def check_response(response):
    """Проверяет корректность ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response or 'current_date' not in response:
        raise KeyError('В ответе API нет ключей homeworks или current_date')
    if not isinstance(response['homeworks'], list):
        raise TypeError('homeworks не список!')
    return response['homeworks']


def parse_status(homework):
    """Извлекает из ответа API нужную информацию."""
    if 'homework_name' not in homework or 'status' not in homework:
        raise KeyError('homework_name или status отсутствуют в ответе API')
    name = homework['homework_name']
    status = homework['status']
    verdict = HOMEWORK_VERDICTS.get(status)
    if verdict is None:
        raise KeyError('Неизвестный статус домашней работы')
    return f'Изменился статус проверки работы "{name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют переменные окружения')
        sys.exit()

    # Создаем объект класса бота
    bot = telebot.TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''  # Переменная для хранения последнего сообщения

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message != last_message:
                    send_message(bot, message)
                    last_message = message
            else:
                logger.debug('Нет новых статусов')
            timestamp = response.get('current_date', timestamp)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_message:
                send_message(message)
                last_message = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
