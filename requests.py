from sqlalchemy import select
from app.db.models import User
from app.db.models import async_session

# Функция подключения к базе данных
def connection(func):
    async def inner(*args, **kwargs):
        async with async_session() as session:
            return await func(session, *args, **kwargs)

    return inner

# Добавление пользователя в базу данных
@connection
async def set_user(session, tg_id):
    user = await session.scalar(select(User).where(User.tg_id == tg_id))

    if not user:
        session.add(User(tg_id=tg_id))
        await session.commit()

@connection
async def get_users(session):
    return await session.scalars(select(User))