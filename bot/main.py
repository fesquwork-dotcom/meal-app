import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MINI_APP_URL = os.getenv("MINI_APP_URL", "")
BOT_ENVIRONMENT = os.getenv("BOT_ENVIRONMENT", "development").strip().lower()

router = Router()


def validate_bot_configuration() -> None:
    errors: list[str] = []

    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is required")

    if not MINI_APP_URL:
        errors.append("MINI_APP_URL is required")
    elif BOT_ENVIRONMENT == "production":
        if not MINI_APP_URL.startswith("https://"):
            errors.append("MINI_APP_URL must use HTTPS in production")
        if "localhost" in MINI_APP_URL or "127.0.0.1" in MINI_APP_URL:
            errors.append("MINI_APP_URL must not use localhost in production")

    if errors:
        for error in errors:
            logger.error("Bot configuration error: %s", error)
        raise SystemExit(1)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть приложение",
                    web_app=WebAppInfo(url=MINI_APP_URL),
                )
            ]
        ]
    )

    await message.answer(
        "Meal Planner помогает собрать меню, рецепты и список покупок на неделю.\n\n"
        "Нажмите кнопку ниже, чтобы открыть Mini App.",
        reply_markup=keyboard,
    )


async def main() -> None:
    validate_bot_configuration()

    bot = Bot(token=BOT_TOKEN)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    logger.info("Bot started")
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
