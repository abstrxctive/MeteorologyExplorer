import asyncio

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Filter, Command
from aiogram.fsm.context import FSMContext

from app.states import Newsletter
from app.db.requests import get_users

admin = Router()


class Admin(Filter):
    async def __call__(self, message: Message):
        return message.from_user.id in [id1, id2]

# Обработчик ввода сообщения рассылки
@admin.message(Admin(), Command('newsletter'))
async def newsletter(message: Message, state: FSMContext):
    await state.set_state(Newsletter.message)
    await message.answer('Введите сообщение для рассылки.')

# Рассылка сообщения
@admin.message(Newsletter.message)
async def newsletter_message(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('Рассылка началась.')
    users = await get_users()
    for user in users:
        try:
            await message.send_copy(chat_id=user.tg_id)
            await asyncio.sleep(0.05)
        except Exception as e:
            print(e)
    await message.answer('Рассылка завершена')
