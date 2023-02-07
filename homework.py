import logging
import os
import sys
import time
from http import HTTPStatus

import requests
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


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения,
    которые необходимы для работы программы."""
    token_list = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
    ]
    return all(token_list)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.info(f'Бот отправил сообщение {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(error)


def get_api_answer(current_timestamp):
    """Создает и отправляет запрос к эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    logging.info(f'Отправка запроса на {ENDPOINT} с параметрами {params}')
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != HTTPStatus.OK:
        raise Exception
    return response.json()


def check_response(response):
    """Проверка полученного ответа от эндпоинта."""
    if not response:
        message = 'содержит пустой словарь.'
        logging.error(message)
        raise KeyError(message)

    if not isinstance(response, dict):
        message = 'имеет некорректный тип.'
        logging.error(message)
        raise TypeError(message)

    if 'homeworks' not in response:
        message = 'отсутствие ожидаемых ключей в ответе.'
        logging.error(message)
        raise KeyError(message)

    if not isinstance(response.get('homeworks'), list):
        message = 'формат ответа не соответствует.'
        logging.error(message)
        raise Exception(message)
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой
    работы. В качестве параметра функция получает только один элемент из
    списка домашних работ. В случае успеха, функция возвращает
    подготовленную для отправки в Telegram строку, содержащую один из
    вердиктов словаря HOMEWORK_VERDICTS."""
    homework_name = homework['homework_name']
    homework_status = homework['homework_status']
    verdict = HOMEWORK_VERDICTS[homework_status]
    if 'homework_name' not in homework:
        msg = 'Отсутствует ключ "homework_name" в ответе API'
        logging.error(msg)
        raise KeyError(msg)
    if 'status' not in homework:
        msg = 'Отсутствует ключ "status" в ответе API'
        logging.error(msg)
        raise KeyError(msg)
    if homework_status not in HOMEWORK_VERDICTS:
        msg = 'Неизвестный статус работы'
        logging.error(msg)
        raise Exception(f'{msg}: {homework_status}')
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
