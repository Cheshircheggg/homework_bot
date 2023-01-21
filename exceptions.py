class PracticumAPIError(Exception):
    """Ошибка API Практикума."""
    pass


class TokenError(Exception):
    """Ошибка в переменных окружения."""
    pass


class SendmessageError(Exception):
    """Ошибка отправки сообщения."""
    pass


class ListError(Exception):
    """Ошибка проверки списка jason."""
    pass


class FormatError(Exception):
    """Ошибка формата Json."""
    pass


class DataTypeError(Exception):
    """Неправильный тип данных"""
    pass
