from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

import os
import asyncio
import logging

from app.handlers import router
from app.db.models import async_main
from app.admin import admin as admin_router
from app.middlewares.antispam import AntiSpamMiddleware

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Загрузка переменных из .env файла
load_dotenv('../other/.env')

token = os.getenv('TOKEN')
bot = Bot(token=token)

antispam_middleware = AntiSpamMiddleware(
    limit_interval=10,  # Предельный интервал
    max_requests=5,     # Количество запросов
    max_violations=3,   # Количество нарушений для блокировки
    ban_time=300,       # Время блокировки 300с = 5мин
    bot=bot             # Добавление бота в конструктор
)

# Функция запуска всех зависимостей
async def main():
    try:

        await async_main()
        # Инициализация диспетчера
        dp = Dispatcher()
        dp.message.middleware(antispam_middleware)

        # Подключение роутеров
        dp.include_routers(router, admin_router)

        logger.info("Starting bot...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот выключен")
    except Exception as e:
        logger.critical(f"Неожиданная ошибка: {e}", exc_info=True)
