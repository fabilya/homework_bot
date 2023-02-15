import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import HTTPRequestError

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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    token_list = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
    ]
    return all(token_list)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logging.debug(f'Отправляем сообщение {message}')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение {message}')
    except Exception as error:
        logging.error(error)


def get_api_answer(current_timestamp):
    """Создает и отправляет запрос к эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {
        'from_date': timestamp
    }
    logging.info(f'Отправка запроса на {ENDPOINT} с параметрами {params}')
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        logging.error(error) # Тут надо рейзить ошибку.
    if response.status_code != HTTPStatus.OK:
        raise HTTPRequestError(response)
    return response.json()11


def check_response(response):
    """Проверка полученного ответа от эндпоинта."""
    if isinstance(response, dict):
        homeworks = response.get('homeworks')
        if 'homeworks' not in response:
            raise TypeError('Нет ключа "homeworks" в response')
        if 'current_date' not in response:
            raise TypeError('Нет ключа "current_date" в response')
        if not isinstance(homeworks, list):
            raise TypeError('"homeworks" не является списком')
        return homeworks
    else:
        raise TypeError('response не является словарем')


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус работы."""
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if not homework.get('homework_name'):
        homework_name = 'Undefined name'
        logging.warning('Отсутствует имя домашней работы.')
    else:
        homework_name = homework.get('homework_name')
    if 'status' not in homework:
        msg = 'Отсутствует ключ "status" в ответе API'
        logging.error(msg)
        raise KeyError(msg)
    if 'homework_name' not in homework:
        msg = 'Отсутствует ключ "homework_name" в ответе API'
        raise KeyError(msg)
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Недокументированный статус домашней работы'
        logging.error(message)
        raise KeyError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    last_send = {
        'error': None,
    }
    if not check_tokens():
        logging.critical('Отсутствуют одна или несколько переменных окружения')
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                logging.debug('Ответ API пуст: нет домашних работ.')
                break
            for homework in homeworks:
                message = parse_status(homework)
                if last_send.get(homework['homework_name']) != message:
                    send_message(bot, message)
                    last_send[homework['homework_name']] = message
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_send['error'] != message:
                send_message(bot, message)
                last_send['error'] = message
        else:
            last_send['error'] = None
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        stream=sys.stdout
    )
    main()
