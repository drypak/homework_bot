class APIResponseError(Exception):
    """Класс для обработки ошибок в ответе API-сервиса Яндекс.Практикум."""


class ApiRequestException(APIResponseError):
    """Исключение для ошибок при получении ответа от API-сервиса."""


class SendMessageError(APIResponseError):
    """Исключение для ошибок при отправке сообщения."""


class UnknownHomeworkStatusError(APIResponseError):
    """Исключение для неизвестного статуса домашней работы."""