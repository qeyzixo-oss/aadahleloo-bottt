import datetime
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import database as db
import keyboards as kb
from config import (
    ADMIN_ID, TON_WALLET, RATE_1000_USDT_IN_TON, MIN_ORDER_USDT
)

# Состояния FSM
(
    MAIN,
    BUY_CHOOSE_ASSET,
    BUY_ENTER_AMOUNT,
    BUY_CONFIRM_ORDER,
    BUY_WAIT_SENT,
    ADDR_CHOOSE_TYPE,
    ADDR_ENTER_ADDRESS,
    ADDR_CONFIRM,
) = range(8)


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def calc_ton(usdt_amount: float) -> float:
    """Рассчитать стоимость в TON."""
    return round((usdt_amount / 1000) * RATE_1000_USDT_IN_TON, 4)


def make_memo(username: str) -> str:
    now = datetime.datetime.now().strftime("%H:%M")
    tag = f"@{username}" if username else "user"
    return f"{tag} {now}"


def fmt_status(status: str) -> str:
    return {"approved": "✅ Успешно", "rejected": "❌ Отклонено", "pending": "⏳ Ожидание"}.get(status, status)


# ─────────────────────────────────────────
# START
# ─────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.create_user(user.id, user.username)
    await update.message.reply_text(
        "Добрый! Как у вас дела? Выберите нужную кнопку снизу 👇",
        reply_markup=kb.main_menu()
    )
    return MAIN


# ─────────────────────────────────────────
# ГЛАВНОЕ МЕНЮ — роутер
# ─────────────────────────────────────────

async def main_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Купить":
        return await buy_start(update, ctx)
    elif text == "Адреса":
        return await addr_start(update, ctx)
    elif text == "Профиль":
        return await profile(update, ctx)
    elif text == "История":
        return await history(update, ctx)
    elif text == "Уведомления":
        return await notifications(update, ctx)
    else:
        await update.message.reply_text("Используйте кнопки меню.", reply_markup=kb.main_menu())
        return MAIN


async def go_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Универсальная кнопка Назад — возврат в главное меню."""
    ctx.user_data.clear()
    await update.message.reply_text("Главное меню:", reply_markup=kb.main_menu())
    return MAIN


# ─────────────────────────────────────────
# КУПИТЬ
# ─────────────────────────────────────────

async def buy_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallet = db.get_wallet(user_id)

    if not wallet:
        await update.message.reply_text(
            "❌ Действие отклонено! Ваш кошелёк TrustWallet не привязан!\n\n"
            "Перейдите в раздел «Адреса» и привяжите кошелёк.",
            reply_markup=kb.main_menu()
        )
        return MAIN

    await update.message.reply_text(
        "🛍️ Вы выбрали категорию «Купить».\nЧто желаете приобрести?",
        reply_markup=kb.buy_menu()
    )
    return BUY_CHOOSE_ASSET


async def buy_choose_asset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "← Назад":
        return await go_main(update, ctx)

    if text == "💎 TON":
        user = update.effective_user
        memo = make_memo(user.username)

        # Создать заявку в БД
        tx_id = db.create_transaction(user.id, "TON", 0, 0, memo)

        await update.message.reply_text(
            "🕰️ TON создаётся! Ждите уведомление от бота!",
            reply_markup=kb.back_only()
        )

        # Уведомить владельца
        await ctx.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🆕 Новая заявка на TON!\n"
                f"👤 @{user.username or 'без ника'} (ID: {user.id})\n"
                f"🗒 Memo: {memo}\n"
                f"📌 Транзакция #{tx_id}"
            ),
            reply_markup=kb.admin_approve_kb(tx_id)
        )
        return BUY_CHOOSE_ASSET

    if text == "💲 USDT":
        await update.message.reply_text(
            f"✅ Отлично! Вы выбрали USDT.\nВведите количество (от {int(MIN_ORDER_USDT)}):",
            reply_markup=kb.back_only()
        )
        return BUY_ENTER_AMOUNT

    await update.message.reply_text("Нажмите на одну из кнопок.", reply_markup=kb.buy_menu())
    return BUY_CHOOSE_ASSET


async def buy_enter_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "← Назад":
        await update.message.reply_text("Что желаете приобрести?", reply_markup=kb.buy_menu())
        return BUY_CHOOSE_ASSET

    try:
        amount = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text(
            f"Введите число. Минимум {int(MIN_ORDER_USDT)} USDT.",
            reply_markup=kb.back_only()
        )
        return BUY_ENTER_AMOUNT

    if amount < MIN_ORDER_USDT:
        await update.message.reply_text(
            f"❌ Минимальная сумма — {int(MIN_ORDER_USDT)} USDT. Введите заново:",
            reply_markup=kb.back_only()
        )
        return BUY_ENTER_AMOUNT

    ton = calc_ton(amount)
    ctx.user_data["usdt_amount"] = amount
    ctx.user_data["ton_price"] = ton

    await update.message.reply_text(
        f"🎉 Супер! Вы выбрали «{int(amount)} USDT».\nОсталось только оплатить! 💸",
        reply_markup=kb.pay_or_back()
    )
    return BUY_CONFIRM_ORDER


async def buy_confirm_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "← Назад":
        await update.message.reply_text(
            f"✅ Введите количество (от {int(MIN_ORDER_USDT)}):",
            reply_markup=kb.back_only()
        )
        return BUY_ENTER_AMOUNT

    if update.message.text != "Оплатить":
        await update.message.reply_text("Нажмите «Оплатить» или «← Назад».", reply_markup=kb.pay_or_back())
        return BUY_CONFIRM_ORDER

    user = update.effective_user
    amount = ctx.user_data.get("usdt_amount", 0)
    ton = ctx.user_data.get("ton_price", 0)
    memo = make_memo(user.username)

    ctx.user_data["memo"] = memo
    ctx.user_data["pending_amount"] = amount
    ctx.user_data["pending_ton"] = ton

    await update.message.reply_text(
        f"📦 Детали заказа:\n"
        f"─────────────────\n"
        f"🔗 Товар: {int(amount)} USDT\n"
        f"💰 Цена: {ton} TON\n"
        f"─────────────────\n"
        f"🏦 Кошелёк для оплаты:\n"
        f"`{TON_WALLET}`\n"
        f"─────────────────\n"
        f"🆔 Memo / Комментарий:\n"
        f"`{memo}`\n"
        f"─────────────────\n"
        f"📢 ОБЯЗАТЕЛЬНО укажите этот комментарий при переводе!\n"
        f"Без комментария деньги не будут зачислены.\n"
        f"Пример: @username 12:30",
        parse_mode="Markdown",
        reply_markup=kb.sent_or_back()
    )
    return BUY_WAIT_SENT


async def buy_wait_sent(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "← Назад":
        await update.message.reply_text("Оплатить или отменить?", reply_markup=kb.pay_or_back())
        return BUY_CONFIRM_ORDER

    if update.message.text != "Отправил!":
        await update.message.reply_text("Нажмите «Отправил!» после оплаты.", reply_markup=kb.sent_or_back())
        return BUY_WAIT_SENT

    user = update.effective_user
    amount = ctx.user_data.get("pending_amount", 0)
    ton = ctx.user_data.get("pending_ton", 0)
    memo = ctx.user_data.get("memo", "")

    # Сохранить транзакцию
    tx_id = db.create_transaction(user.id, "USDT", amount, ton, memo)
    ctx.user_data["tx_id"] = tx_id

    await update.message.reply_text(
        f"⏳ Отправка {int(amount)} USDT займёт от 10 секунд до 5 минут.\n"
        f"Ожидайте подтверждения от администратора.",
        reply_markup=kb.back_only()
    )

    # Уведомить владельца
    await ctx.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"🆕 Новая заявка!\n"
            f"👤 @{user.username or 'без ника'} (ID: {user.id})\n"
            f"💰 Актив: {int(amount)} USDT\n"
            f"📤 К оплате: {ton} TON\n"
            f"🗒 Memo: {memo}\n"
            f"📌 Транзакция #{tx_id}"
        ),
        reply_markup=kb.admin_approve_kb(tx_id)
    )
    return BUY_WAIT_SENT


# ─────────────────────────────────────────
# АДРЕСА
# ─────────────────────────────────────────

async def addr_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallet = db.get_wallet(user_id)

    extra = f"\n\nТекущий кошелёк: `{wallet}`" if wallet else ""
    await update.message.reply_text(
        f"✅ Вы выбрали «Адреса». Выберите тип кошелька 👇{extra}",
        parse_mode="Markdown",
        reply_markup=kb.address_type_menu()
    )
    return ADDR_CHOOSE_TYPE


async def addr_choose_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "← Назад":
        return await go_main(update, ctx)

    if update.message.text == "TrustWallet":
        await update.message.reply_text(
            "🔘 Выбран TrustWallet 🛡️\n\n📝 Введите адрес BNB SmartChain (BSC) в чат:",
            reply_markup=kb.back_only()
        )
        return ADDR_ENTER_ADDRESS

    await update.message.reply_text("Нажмите на кнопку.", reply_markup=kb.address_type_menu())
    return ADDR_CHOOSE_TYPE


async def addr_enter_address(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "← Назад":
        await update.message.reply_text("Выберите тип кошелька:", reply_markup=kb.address_type_menu())
        return ADDR_CHOOSE_TYPE

    address = update.message.text.strip()

    # Валидация BSC-адреса
    if not (address.startswith("0x") and len(address) == 42 and all(c in "0123456789abcdefABCDEF" for c in address[2:])):
        await update.message.reply_text(
            "❌ Неверный формат адреса.\n"
            "Адрес BSC должен начинаться с 0x и содержать 42 символа.\n\n"
            "Введите адрес заново:",
            reply_markup=kb.back_only()
        )
        return ADDR_ENTER_ADDRESS

    ctx.user_data["new_wallet"] = address

    await update.message.reply_text(
        f"⚠️ Вы уверены, что ввели правильно?\n\n`{address}`",
        parse_mode="Markdown",
        reply_markup=kb.confirm_address_menu()
    )
    return ADDR_CONFIRM


async def addr_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "← Назад":
        return await go_main(update, ctx)

    if text == "Изменить":
        await update.message.reply_text(
            "📝 Введите адрес BNB SmartChain (BSC) заново:",
            reply_markup=kb.back_only()
        )
        return ADDR_ENTER_ADDRESS

    if text == "Да!":
        wallet = ctx.user_data.get("new_wallet")
        db.set_wallet(update.effective_user.id, wallet)
        await update.message.reply_text(
            "🎉 Отлично! Кошелёк успешно привязан ✅",
            reply_markup=kb.back_only()
        )
        return ADDR_CONFIRM

    await update.message.reply_text("Нажмите одну из кнопок.", reply_markup=kb.confirm_address_menu())
    return ADDR_CONFIRM


# ─────────────────────────────────────────
# ПРОФИЛЬ
# ─────────────────────────────────────────

async def profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = db.get_user(user.id)

    username_display = f"@{user.username}" if user.username else f"Пользователь #{user.id}"
    spent = row["spent_usdt"] if row else 0
    received = row["received_usdt"] if row else 0
    balance = received - spent

    await update.message.reply_text(
        f"👤 Ваш профиль\n"
        f"───────────────\n"
        f"🌳 Никнейм: {username_display}\n"
        f"🆔 ID: `{user.id}`\n"
        f"───────────────\n"
        f"💸 Потрачено: `{spent} USDT`\n"
        f"📦 Получено: `{received} USDT`\n"
        f"───────────────\n"
        f"📊 Баланс: `{balance:+.2f} USDT`\n"
        f"───────────────",
        parse_mode="Markdown",
        reply_markup=kb.back_only()
    )
    return MAIN


# ─────────────────────────────────────────
# ИСТОРИЯ
# ─────────────────────────────────────────

async def history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    txs = db.get_user_history(user_id)

    if not txs:
        await update.message.reply_text(
            "📭 У вас пока нет транзакций.",
            reply_markup=kb.back_only()
        )
        return MAIN

    lines = ["✅ Вы выбрали «История».\n\n📜 История транзакций"]
    for tx in txs:
        dt = tx["created_at"][:16].replace("T", " ")
        lines.append(
            f"─────────────────\n"
            f"🕒 {dt}  💰 +{tx['amount']} {tx['asset']}"
            f"  📤 {tx['paid_ton']} TON  {fmt_status(tx['status'])}"
        )
    lines.append("─────────────────")

    await update.message.reply_text("\n".join(lines), reply_markup=kb.back_only())
    return MAIN


# ─────────────────────────────────────────
# УВЕДОМЛЕНИЯ
# ─────────────────────────────────────────

async def notifications(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    notifs = db.get_notifications()

    if not notifs:
        await update.message.reply_text(
            "🔔 Уведомлений пока нет.",
            reply_markup=kb.back_only()
        )
        return MAIN

    lines = ["🔔 Центр уведомлений\n"]
    for n in notifs:
        dt = n["created_at"][:10]
        lines.append(f"📢 {dt} — {n['text']}")

    await update.message.reply_text("\n".join(lines), reply_markup=kb.back_only())
    return MAIN


# ─────────────────────────────────────────
# ADMIN: подтверждение / отклонение заявки
# ─────────────────────────────────────────

async def admin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("Нет доступа.", show_alert=True)
        return

    action, tx_id = query.data.split(":")
    tx_id = int(tx_id)

    if action == "approve":
        tx = db.approve_transaction(tx_id)
        if tx:
            await ctx.bot.send_message(
                chat_id=tx["user_id"],
                text="✅ Готово! Ваша заявка одобрена! Оплата получена.",
                reply_markup=kb.main_menu()
            )
            await query.edit_message_text(
                query.message.text + f"\n\n✅ ОДОБРЕНО (транзакция #{tx_id})"
            )

    elif action == "reject":
        tx = db.reject_transaction(tx_id)
        if tx:
            await ctx.bot.send_message(
                chat_id=tx["user_id"],
                text="❌ Ошибка! Ваша заявка была отклонена. Оплата не обнаружена.",
                reply_markup=kb.main_menu()
            )
            await query.edit_message_text(
                query.message.text + f"\n\n❌ ОТКЛОНЕНО (транзакция #{tx_id})"
            )


# ─────────────────────────────────────────
# ADMIN: рассылка уведомления всем юзерам
# Команда: /notify Текст уведомления
# ─────────────────────────────────────────

async def admin_notify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not ctx.args:
        await update.message.reply_text("Использование: /notify Текст уведомления")
        return

    text = " ".join(ctx.args)
    db.add_notification(text)

    user_ids = db.get_all_user_ids()
    sent = 0
    for uid in user_ids:
        try:
            await ctx.bot.send_message(chat_id=uid, text=f"📢 {text}")
            sent += 1
        except Exception:
            pass

    await update.message.reply_text(f"✅ Рассылка отправлена {sent} пользователям.")
