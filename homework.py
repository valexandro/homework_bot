import logging
import os
import time
from http import HTTPStatus
from typing import Dict

import requests
from dotenv import load_dotenv
from requests import Response
from telegram import Bot

from exceptions import EndpointUnavailableError

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)

stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def send_message(bot: Bot, message: str):
    """Отправляет сообщение в указанный чат телеграмма."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.info('Сообщение отправлено успешно!')
    except Exception as e:
        logging.error(f'При отправке сообщения произошла ошибка {e}')


def get_api_answer(current_timestamp: int) -> Response:
    """Делает запрос к апи домашек яндекс практикума."""
    timestamp: int = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homeworks_response: Response = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
    except Exception as e:
        message_request_error = f'Ошибка при попытке доступа к апи: {e}'
        logging.error(message_request_error)
    if homeworks_response.status_code != HTTPStatus.OK:
        error_message_api_unavailable = (
            f'Эндпоинт недоступен.'
            f'Статус ошибки: {homeworks_response.status_code}')
        logging.error(error_message_api_unavailable)
        raise EndpointUnavailableError(error_message_api_unavailable)
    return homeworks_response.json()


def check_response(response):
    """Проверяет правильность ответа апи."""
    if not isinstance(response, dict):
        error_message_dict = 'Ответ апи пришел в виде словаря.'
        logging.error(error_message_dict)
        raise TypeError(error_message_dict)

    homeworks_list = response.get('homeworks')

    if not isinstance(homeworks_list, list):
        error_message_list = 'Под ключом homeworks находится не список.'
        logging.error(error_message_list)
        raise TypeError(error_message_list)

    return homeworks_list


def parse_status(homework: Dict) -> str:
    """Получает статус домашки и формирует сообщение для отправки."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_STATUSES.keys():
        error_message = (
            f'Неожиданный статус домашней работы: {homework_status}')
        logging.error(error_message)

    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверяет что все нужные переменные окружения доступны."""
    if not (PRACTICUM_TOKEN
            and TELEGRAM_TOKEN
            and TELEGRAM_CHAT_ID):
        logging.critical(
            'Отсутствуют обязательные переменные окружения!')
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            logging.debug(response)

            homeworks = check_response(response)
            if homeworks:
                for homework in homeworks:
                    send_message(bot, parse_status(homework))
            else:
                logging.debug('Нет новых изменений статуса домашних работ.')
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
