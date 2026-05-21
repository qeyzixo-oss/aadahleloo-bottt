from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu():
    return ReplyKeyboardMarkup(
        [["Купить", "Адреса"], ["Профиль", "История"], ["Уведомления"]],
        resize_keyboard=True
    )


def buy_menu():
    return ReplyKeyboardMarkup(
        [["💲 USDT", "💎 TON"], ["← Назад"]],
        resize_keyboard=True
    )


def back_only():
    return ReplyKeyboardMarkup([["← Назад"]], resize_keyboard=True)


def pay_or_back():
    return ReplyKeyboardMarkup([["Оплатить", "← Назад"]], resize_keyboard=True)


def sent_or_back():
    return ReplyKeyboardMarkup([["Отправил!", "← Назад"]], resize_keyboard=True)


def address_type_menu():
    return ReplyKeyboardMarkup([["TrustWallet"], ["← Назад"]], resize_keyboard=True)


def confirm_address_menu():
    return ReplyKeyboardMarkup([["Да!", "Изменить"], ["← Назад"]], resize_keyboard=True)


def admin_approve_kb(tx_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"approve:{tx_id}"),
            InlineKeyboardButton("❌ Отклонить",   callback_data=f"reject:{tx_id}")
        ]
    ])
