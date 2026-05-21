import datetime
import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from config import BOT_TOKEN, WORK_START, WORK_END
import database as db
from handlers import (
    MAIN, BUY_CHOOSE_ASSET, BUY_ENTER_AMOUNT, BUY_CONFIRM_ORDER, BUY_WAIT_SENT,
    ADDR_CHOOSE_TYPE, ADDR_ENTER_ADDRESS, ADDR_CONFIRM,
    start, main_router, go_main,
    buy_start, buy_choose_asset, buy_enter_amount, buy_confirm_order, buy_wait_sent,
    addr_start, addr_choose_type, addr_enter_address, addr_confirm,
    profile, history, notifications,
    admin_callback, admin_notify,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)


# ─────────────────────────────────────────
# MIDDLEWARE: проверка рабочего времени
# ─────────────────────────────────────────

async def check_work_hours(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Возвращает True если бот открыт, иначе отвечает и возвращает False."""
    now = datetime.datetime.now().hour
    if now < WORK_START:
        if update.message:
            await update.message.reply_text(
                f"🔒 Бот закрыт! Откроется в {WORK_START}:00."
            )
        return False
    return True


# Обёртка для ConversationHandler — проверяет время перед каждым хэндлером
def time_guard(handler_func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await check_work_hours(update, ctx):
            return None
        return await handler_func(update, ctx)
    return wrapper


def main():
    db.init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ── Conversation Handler (главный FSM) ──
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", time_guard(start))],
        states={
            MAIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_guard(main_router))
            ],
            BUY_CHOOSE_ASSET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_guard(buy_choose_asset))
            ],
            BUY_ENTER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_guard(buy_enter_amount))
            ],
            BUY_CONFIRM_ORDER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_guard(buy_confirm_order))
            ],
            BUY_WAIT_SENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_guard(buy_wait_sent))
            ],
            ADDR_CHOOSE_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_guard(addr_choose_type))
            ],
            ADDR_ENTER_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_guard(addr_enter_address))
            ],
            ADDR_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_guard(addr_confirm))
            ],
        },
        fallbacks=[
            CommandHandler("start", time_guard(start)),
            MessageHandler(filters.Regex("^← Назад$"), time_guard(go_main)),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)

    # ── Admin handlers ──
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^(approve|reject):\d+$"))
    app.add_handler(CommandHandler("notify", admin_notify))

    logging.info("Бот запущен.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
