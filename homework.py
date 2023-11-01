import requests
import os
import sys
import time
import logging
from http import HTTPStatus

import telegram
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

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s',
    stream=sys.stdout,
    encoding='utf-8'
)

logger = logging.getLogger(__name__)


def check_tokens() -> bool:
    """Проверка доступности переменных окружения."""
    if (TELEGRAM_CHAT_ID is None
            and PRACTICUM_TOKEN is None
            and TELEGRAM_TOKEN is None):
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения о статусе домашки."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except Exception as error:
        logger.error(f'Сообщение не отправлено: {error}')


def get_api_answer(timestamp) -> dict:
    """Запрос к API домашки."""
    try:
        response = requests.get(
            url=ENDPOINT, headers=HEADERS,
            params={'from_date': timestamp}
        )
        logger.info('Запрос выполнен успешно')
    except requests.RequestException as error:
        raise ConnectionError(error)

    if response.status_code != HTTPStatus.OK:
        raise requests.HTTPError('Неверный статус запроса')
    return response.json()


def check_response(response) -> dict:
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ не в виде JSON')
    if response.get('homeworks') is None:
        raise KeyError('В ответе отстутствует ключ \'homeworks\'')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Перечень заданий не в виде списка')
    return response['homeworks'][0]


def parse_status(homework) -> str:
    """Получаем статус домашки."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_name is None:
        raise KeyError('Параметр \'homework_name\' отсутствует в ответе')
    if homework_status is None:
        raise KeyError('Параметр \'homework_status\' отсутствует в ответе')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'В ответе несуществующий статус: {homework_status}')

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Переменные окружения не инициализированы')
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0  # int(time.time())
    status = ''
    message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check = check_response(response)
            if check:
                new_status = parse_status(check)

                if new_status != status:
                    send_message(bot, new_status)
                    status = new_status
                else:
                    logger.debug('Статус домашки не обновился')

        except Exception as error:
            new_message = f'Сбой в работе программы: {error}'
            if new_message != message:
                message = new_message
                logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
