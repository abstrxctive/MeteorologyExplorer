from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine

engine = create_async_engine(url='sqlite+aiosqlite:///db.sqlite3',
                             echo=True)

async_session = async_sessionmaker(engine)


class Base(AsyncAttrs, DeclarativeBase):
    pass

# Таблица пользователей
class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id = mapped_column(BigInteger)

# Таблица заблокированных пользователей
class BannedUser(Base):
    __tablename__ = "banned_users"
    user_id = mapped_column(BigInteger, primary_key=True)
    ban_end = mapped_column(DateTime)

# Запуск
async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
