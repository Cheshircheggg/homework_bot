import logging
import os
import time
from logging import StreamHandler
from typing import Dict

import requests
import telegram
from dotenv import load_dotenv
from http import HTTPStatus

import exceptions


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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    variables = [TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, ENDPOINT]
    for variable in variables:
        if not variable:
            logging.critical('Отсутствие обязательных переменных '
                             f'{variable} окружения во время запуска бота ')
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Отправлено сообщение: "{message}"')
    except Exception as error:
        logging.error(f'Cбой отправки сообщения, ошибка: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API."""
    logger.debug("Отправляем запрос к эндпоинту API-сервиса")
    request_params = {
        "url": ENDPOINT,
        "params": {'from_date': timestamp},
        "headers": HEADERS
    }
    try:
        homework = requests.get(**request_params)
        if homework.status_code != HTTPStatus.OK:
            raise exceptions.StatusCodeError("Ожидаемый код ответа не получен")
    except Exception:
        raise exceptions.PracticumAPIError("Ошибка при запросе к серверу")
    else:
        logger.info("Запрос к API выполнен успешно")
    return homework.json()


def check_response(response):
    """Проверяет ответ API, и возвращает список домашних работ."""
    logger.debug("Проверяем ответ API на корректность")
    try:
        homework = response["homeworks"]
    except KeyError as error:
        message = f"Нет ответа API по ключу 'homeworks'. Ошибка {error}"
        raise exceptions.PracticumAPIError(message)
    if not isinstance(homework, list):
        message = "В ответе API домашки не в виде списков"
        logger.error(message)
        raise TypeError(message)
    else:
        logger.info("Ответ API корректен")
    return homework


def parse_status(homework):
    """Возвращает текст сообщения о статусе проверки работы homework."""
    if homework is None:
        logger.error("Данные с домашней работой не найдены")
        raise KeyError("Домашняя работа отсутствует")
    logger.debug("Получаем статус домашней работы")
    if "homework_name" not in homework or "status" not in homework:
        raise KeyError("No homework_status_name or status in homework")
    if not isinstance(homework, Dict):
        raise TypeError("homework не является словарем")
    homework_name = homework["homework_name"]
    homework_status = homework["status"]
    try:
        verdict = HOMEWORK_VERDICTS[homework_status]
    except Exception:
        logger.error("Статус не определен")
    else:
        logger.info("Статус домашней работы получен")
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    try:
        if check_tokens() is not True:
            raise exceptions.TokenError
    except exceptions.TokenError:
        logger.critical("Отсутствие обязательных переменных окружения")
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    old_message = ""
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                if message != old_message:
                    send_message(bot, message)
                    old_message = message
                else:
                    logger.debug("Статус проверки не изменился")

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            send_message(
                bot,
                message
            )
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='main.log',
        format='%(asctime)s, %(levelname)s, %(message)s'
    )
    logger = logging.getLogger(__name__)
    handler = StreamHandler()
    logger.addHandler(handler)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s'
    )
    handler.setFormatter(formatter)
    main()
