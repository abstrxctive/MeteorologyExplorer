import os

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, TelegramObject

from datetime import datetime, timedelta
from typing import Callable, Dict, Any, Awaitable

from sqlalchemy import select
from app.db.models import BannedUser, async_session

# Анти-спам middleware
class AntiSpamMiddleware(BaseMiddleware):
    def __init__(
        self,
        bot: Bot,
        limit_interval: int = 5,
        max_requests: int = 3,
        max_violations: int = 3,
        ban_time: int = 300
    ):
        self.bot = bot
        self.limit_interval = limit_interval
        self.max_requests = max_requests
        self.max_violations = max_violations
        self.ban_time = ban_time
        self.user_requests: Dict[int, list] = {}
        self.violations: Dict[int, int] = {}
        self.admin_chat_id = int(os.getenv("ADMIN_CHAT_ID"))
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id
        now = datetime.now()

        # Проверка блокировки в базе данных
        async with async_session() as session:
            banned = await session.scalar(
                select(BannedUser).where(BannedUser.user_id == user_id)
            )
            if banned and banned.ban_end > now:
                await event.answer(
                    f"🚫 Вы заблокированы до {banned.ban_end.strftime('%Y-%m-%d %H:%M')}!"
                )
                return
            elif banned:
                await session.delete(banned)
                await session.commit()

        # Логика антиспама
        if user_id in self.user_requests:
            self.user_requests[user_id] = [
                t for t in self.user_requests[user_id]
                if now - t < timedelta(seconds=self.limit_interval)
            ]

        if len(self.user_requests.get(user_id, [])) >= self.max_requests:
            self.violations[user_id] = self.violations.get(user_id, 0) + 1

            if self.violations[user_id] >= self.max_violations:
                ban_end = now + timedelta(seconds=self.ban_time)
                async with async_session() as session:
                    session.add(BannedUser(user_id=user_id, ban_end=ban_end))
                    await session.commit()

                try:
                    await self.bot.send_message(
                        chat_id=self.admin_chat_id,
                        text=f"🚨 Пользователь {user_id} заблокирован до {ban_end.strftime('%Y-%m-%d %H:%M')}"
                    )
                except Exception as e:
                    print(f"Ошибка отправки уведомления: {e}")

                await event.answer(f"⛔ Вы заблокированы на {self.ban_time//60} минут!")
                return

            await event.answer(
                f"⚠️ Нарушение {self.violations[user_id]}/{self.max_violations}. "
                f"Далее последует блокировка."
            )
            return

        if user_id in self.violations:
            del self.violations[user_id]

        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        self.user_requests[user_id].append(now)


        return await handler(event, data)
