class APIResponseError(Exception):
    """Класс для обработки ошибок в ответе API-сервиса Яндекс.Практикум."""


class ApiAnswerException(APIResponseError):
    """Исключение для ошибок при получении ответа от API-сервиса."""