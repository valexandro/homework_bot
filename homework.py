import logging
import os
import time
from http import HTTPStatus
from typing import Any, Dict, List, Mapping, Optional

import requests
from dotenv import load_dotenv
from requests import Response
from telegram import Bot

from exceptions import EndpointUnavailableError

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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
        logging.exception(f'При отправке сообщения произошла ошибка {e}')


def get_api_answer(current_timestamp: int) -> Dict:
    """Делает запрос к апи домашек яндекс практикума."""
    timestamp: int = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homeworks_response: Response = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
    except Exception as e:
        message_request_error = f'Ошибка при попытке доступа к апи: {e}'
        logging.error(message_request_error)
        raise Exception(message_request_error) from e

    if homeworks_response.status_code != HTTPStatus.OK:
        error_message_api_unavailable = (
            f'Эндпоинт недоступен.'
            f'Статус ошибки: {homeworks_response.status_code}')
        logging.error(error_message_api_unavailable)
        raise EndpointUnavailableError(error_message_api_unavailable)
    return homeworks_response.json()


def check_response(response: Dict) -> List[Mapping]:
    """Проверяет правильность ответа апи."""
    if not isinstance(response, dict):
        error_message_dict = 'Ответ апи пришел не в виде словаря.'
        logging.error(error_message_dict)
        raise TypeError(error_message_dict)

    homeworks_list: List[Mapping] = response.get('homeworks')

    if not isinstance(homeworks_list, list):
        error_message_list = 'Под ключом homeworks находится не список.'
        logging.error(error_message_list)
        raise TypeError(error_message_list)

    return homeworks_list


def parse_status(homework: Mapping[str, Any]) -> str:
    """Получает статус домашки и формирует сообщение для отправки."""
    homework_name: Optional[str] = homework.get('homework_name')
    homework_status: Optional[str] = homework.get('status')

    if not homework_name or homework_status not in HOMEWORK_STATUSES.keys():
        error_message = (
            f'Неожиданные входные данные: '
            f'название: {homework_name}, статус: {homework_status}')
        logging.error(error_message)
        raise KeyError(error_message)

    verdict: str = HOMEWORK_STATUSES[homework_status]
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

    bot: Bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp: int = int(time.time())

    while True:
        try:
            homeworks_data = get_api_answer(current_timestamp)

            homeworks = check_response(homeworks_data)
            if homeworks:
                for homework in homeworks:
                    send_message(bot, parse_status(homework))
            else:
                logging.debug('Нет новых изменений статуса домашних работ.')
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.exception(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
