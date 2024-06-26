import logging
import os
import time
from http import HTTPStatus
from logging import StreamHandler
from typing import Dict

import requests
import telegram
from dotenv import load_dotenv

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
            logging.critical("Отсутствие обязательных переменных "
                             f"{variable} окружения во время запуска бота ")
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        logging.debug(f"Отправка сообщения {message}")
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logging.error(f"Ошибка отправки статуса в telegram: {error}")
        raise exceptions.SendmessageError(f"Ошибка отправки сообщения{error}")
    else:
        logging.info("Успешная отправка сообщения!")


def get_api_answer(timestamp):
    """Делает запрос к API."""
    logging.debug("Отправка запроса к API.")
    params = {"from_date": timestamp}
    try:
        response = requests.get(ENDPOINT, params, headers=HEADERS)
    except Exception as error:
        raise exceptions.PracticumAPIError(f"API недоступен. {error}")
    if response.status_code != HTTPStatus.OK:
        raise exceptions.PracticumAPIError(
            f"API недоступен, код ответа сервера {response.status_code}"
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API, и возвращает список домашних работ."""
    logging.info("Начало проверки ответа сервера")
    try:
        homeworks = response["homeworks"]
    except KeyError:
        raise KeyError("Нет ключа в словаре")
    if not isinstance(homeworks, list):
        raise TypeError("Не список")
    return homeworks


def parse_status(homework):
    """Возвращает текст сообщения о статусе проверки работы homework."""
    logger.debug("Получаем статус домашней работы")
    if not isinstance(homework, Dict):
        raise TypeError("homework не является словарем")
    if "homework_name" not in homework or "status" not in homework:
        raise KeyError("No homework_status_name or status in homework")
    homework_name = homework["homework_name"]
    homework_status = homework["status"]
    try:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError:
        logging.error("Статус не определен")
        raise KeyError("Статус домашней работы получен")


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        errormessage = 'Отсутствует обязательная переменная окружения!'
        logging.critical(errormessage)
        raise exceptions.TokenError(errormessage)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_error = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            home_works = check_response(response)
            if len(home_works) > 0:
                message = parse_status(home_works[0])
                send_message(bot, message)
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            errormessage = f'Сбой в работе программы: {error}'
            logging.critical(errormessage)
            if current_error != errormessage:
                current_error = errormessage
                send_message(bot, errormessage)
        else:
            current_error = None
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
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Заверешние работы")
