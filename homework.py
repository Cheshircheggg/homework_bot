import logging
import os
import time
from logging import StreamHandler

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
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s'
)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    massive = [TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, ENDPOINT]
    for i in massive:
        if not i:
            logging.critical('Отсутствие обязательных переменных '
                             f'{i} окружения во время запуска бота ')
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    chat_id = TELEGRAM_CHAT_ID
    text = message
    try:
        logging.debug(f'Отправка сообщения {text}')
        bot.send_message(chat_id, text)
    except Exception as error:
        logging.error(f'Сбой в работе программы: {error}')
        raise exceptions.SendmessageError(f'Ошибка отправки сообщения{error}')


def get_api_answer(timestamp):
    """Делает запрос к API."""
    """Запрос к Api."""
    current_timestamp = timestamp
    payload = {'from_date': current_timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT, headers=HEADERS,
                                         params=payload)
    except requests.exceptions.RequestException as error:
        raise exceptions.PracticumAPIError(f'Ошибка запроса {error}')
    if homework_statuses.status_code == 400:
        logging.error('Недоступность эндпоинта')
        raise exceptions.PracticumAPIError('Api Yandex не работает')
    if homework_statuses.status_code != 200:
        logging.error('сбои при запросе к эндпоинту ',
                      f'{homework_statuses.status_code}')
        raise exceptions.PracticumAPIError('Api запрос Yandex не проходит')
    try:
        return homework_statuses.json()
    except Exception as error:
        raise exceptions.FormatError(f'Формат не json {error}')


def check_response(response):
    """Проверяет ответ API, и возвращает список домашних работ."""
    logging.info('Начало проверки ответа сервера')
    try:
        value = response['homeworks']
    except KeyError:
        raise KeyError('Нет ключа в словаре')
    if type(response['homeworks']) != list:
        raise TypeError('Не список')
    if 'code' in response:
        raise exceptions.PracticumAPIError('Ошибка ответа API сервера')
    if value:
        return response['homeworks'][0]
    else:
        raise IndexError('Пустой список')


def parse_status(homework):
    """Возвращает текст сообщения о статусе проверки работы homework."""
    WRONG_DTYPE = 'Неверный тип данных {type}, вместо "dict"'
    if not isinstance(homework, dict):
        raise exceptions.DataTypeError(WRONG_DTYPE.format(type(homework)))
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    if 'homework_name' not in homework:
        raise Exception('Ошибка наименования домашки')

    if homework_status not in HOMEWORK_VERDICTS:
        logging.error('Неверный статус домашки')
        raise NameError('Неверный статус домашки')

    verdict = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    prev_message = ''
    if not check_tokens():
        raise exceptions.TokenError('Ошибка токена')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            if prev_message != message:
                send_message(bot, message)
            logging.info(homework)
            current_timestamp = response.get('current_date')
        except IndexError:
            message = 'Статус работы не изменился'
            if prev_message != message:
                send_message(bot, message)
            logging.debug('В ответе нет новых статусов.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.error(message)
        finally:
            prev_message = message
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
