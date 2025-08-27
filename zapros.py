import os
import asyncio
from typing import List

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, MenuButtonCommands, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# --- Dev-удобство: подхватить .env если есть (на проде можно не ставить python-dotenv) ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
# -------------------------------------------------------------------------------------------

def get_bot_token() -> str:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Переменная окружения BOT_TOKEN не задана. "
            "Задай её в окружении или добавь в локальный .env (BOT_TOKEN=...)"
        )
    return token


# ===== Настройки доступа =====
# Твой Telegram user_id. Узнать можно через @userinfobot.
MY_USER_ID = 1040008041  # <-- ЗАМЕНИ на свой user_id!

# В списке менеджеров для выбора — только общий AirexSupport
MANAGERS = ['AirexSupport']

# Чаты менеджеров (подставь реальные ID)
MANAGER_CHAT_IDS = {
    "AirexSupport": 8017918640,  # <-- chat_id аккаунта AirexSupport
    "TEST": 1040008041           # <-- твой chat_id (обычно = user_id)
}

def build_manager_keyboard(user_id: int):
    """Все видят AirexSupport; TEST — только владелец (MY_USER_ID)."""
    managers = MANAGERS.copy()
    if user_id == MY_USER_ID:
        managers.append("TEST")
    return [[InlineKeyboardButton(name, callback_data=f"sendto_{name}")] for name in managers]


# Состояния
STATES = {
    "CATEGORY": "category",
    "MANAGER": "manager",
    "REQUEST_ID": "request_id",
    "AMOUNT": "amount",
    "BANK_FROM": "bank_from",
    "BANK_TO": "bank_to",
    "REASON": "reason",
    "SCREENSHOTS": "screenshots",
    "NAME_ON_PLATFORM": "name_platform",
    "NAME_ON_DETAILS": "name_details",
    "SHIFT_MANAGER": "shift_manager",
    "STAGE": "stage",
    "COMMENT": "comment",
}

# ---------- UI helpers ----------
def screenshot_prompt_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Кнопка «Пропустить» показывается только владельцу (MY_USER_ID).
    Для остальных — только «Готово».
    """
    rows = [[InlineKeyboardButton("Готово", callback_data="screenshots_done")]]
    if user_id == MY_USER_ID:
        rows.append([InlineKeyboardButton("Пропустить", callback_data="skip_screenshots")])
    return InlineKeyboardMarkup(rows)


# ===========================
#         HANDLERS
# ===========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Переплата", callback_data="overpayment")],
        [InlineKeyboardButton("Перевод не на тот банк", callback_data="wrong_bank")],
        [InlineKeyboardButton("Неверные реквизиты", callback_data="wrong_details")],
        [InlineKeyboardButton("Поступление средств", callback_data="funds_received")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.user_data.clear()

    text = "Для того чтобы составить запрос, нажмите на одну из кнопок:"
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data
    context.user_data[STATES["CATEGORY"]] = category
    # Сразу переходим к запросу ID
    context.user_data[STATES["STAGE"]] = "request_id"
    await query.edit_message_text("Введите ID заявки:")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip() if update.message and update.message.text else ""
    stage = context.user_data.get(STATES["STAGE"])
    category = context.user_data.get(STATES["CATEGORY"])
    user_id = update.effective_user.id

    if stage == "request_id":
        if not text:
            await update.message.reply_text("ID заявки не распознан. Введите, пожалуйста, ID заявки:")
            return
        context.user_data[STATES["REQUEST_ID"]] = text
        if category in ("overpayment", "funds_received"):
            context.user_data[STATES["STAGE"]] = "amount"
            await update.message.reply_text("Введите сумму (пример: 1234.56):")
        elif category == "wrong_bank":
            context.user_data[STATES["STAGE"]] = "bank_to"
            await update.message.reply_text("На какой банк нужно было перевести:")
        elif category == "wrong_details":
            context.user_data[STATES["STAGE"]] = "reason"
            keyboard = [
                [InlineKeyboardButton("Нет банка на реквизитах", callback_data="no_bank")],
                [InlineKeyboardButton("Разные имена", callback_data="diff_names")],
                [InlineKeyboardButton("Проблемный номер", callback_data="bad_number")],
            ]
            await update.message.reply_text("Что случилось?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif stage == "amount":
        # Базовая валидация числа
        normalized = text.replace(",", ".")
        try:
            float(normalized)
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите сумму числом. Пример: 1234.56")
            return
        context.user_data[STATES["AMOUNT"]] = normalized

        if category == "funds_received":
            context.user_data[STATES["STAGE"]] = "choose_manager"
            keyboard = build_manager_keyboard(user_id)
            await update.message.reply_text("Кто старший менеджер на смене?", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            context.user_data[STATES["STAGE"]] = "screenshot"
            await update.message.reply_text(
                "Прикрепите скриншоты (можно несколько), затем нажмите «Готово».",
                reply_markup=screenshot_prompt_keyboard(user_id)
            )

    elif stage == "bank_to":
        context.user_data[STATES["BANK_TO"]] = text
        context.user_data[STATES["STAGE"]] = "bank_from"
        await update.message.reply_text("На какой банк перевели по факту:")

    elif stage == "bank_from":
        context.user_data[STATES["BANK_FROM"]] = text
        context.user_data[STATES["STAGE"]] = "screenshot"
        await update.message.reply_text(
            "Прикрепите скриншоты (можно несколько), затем нажмите «Готово».",
            reply_markup=screenshot_prompt_keyboard(user_id)
        )

    elif stage == "name_platform":
        context.user_data[STATES["NAME_ON_PLATFORM"]] = text
        context.user_data[STATES["STAGE"]] = "name_details"
        await update.message.reply_text("Какое имя указано на реквизитах?")

    elif stage == "name_details":
        context.user_data[STATES["NAME_ON_DETAILS"]] = text
        context.user_data[STATES["STAGE"]] = "screenshot"
        await update.message.reply_text(
            "Прикрепите скриншоты (можно несколько), затем нажмите «Готово».",
            reply_markup=screenshot_prompt_keyboard(user_id)
        )

    elif stage == "bad_number_comment":
        context.user_data[STATES["COMMENT"]] = text
        context.user_data[STATES["STAGE"]] = "choose_manager"
        keyboard = build_manager_keyboard(user_id)
        await update.message.reply_text("Кто старший менеджер на смене?", reply_markup=InlineKeyboardMarkup(keyboard))

    else:
        # На случай непредвиденного состояния
        await update.message.reply_text("Не понял этап. Нажмите /start для начала заново или /cancel чтобы отменить.")


async def wrong_details_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reason = query.data

    uid = update.effective_user.id

    if reason == "no_bank":
        context.user_data[STATES["REASON"]] = "Нет банка на реквизитах"
        context.user_data[STATES["STAGE"]] = "screenshot"
        await query.edit_message_text(
            "Прикрепите скриншоты (можно несколько), затем нажмите «Готово».",
            reply_markup=screenshot_prompt_keyboard(uid)
        )

    elif reason == "diff_names":
        context.user_data[STATES["REASON"]] = "Разные имена"
        context.user_data[STATES["STAGE"]] = "name_platform"
        await query.edit_message_text("Какое имя указано в платформе?")

    elif reason == "bad_number":
        context.user_data[STATES["REASON"]] = "Проблемный номер"
        context.user_data[STATES["STAGE"]] = "bad_number_comment"
        await query.edit_message_text("Опишите, в чём проблема:")


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stage = context.user_data.get(STATES["STAGE"])
    user_id = update.effective_user.id
    if stage == "screenshot":
        if STATES["SCREENSHOTS"] not in context.user_data:
            context.user_data[STATES["SCREENSHOTS"]] = []

        photo_id = update.message.photo[-1].file_id
        context.user_data[STATES["SCREENSHOTS"]].append(photo_id)

        # Кнопки показываем один раз
        if not context.user_data.get("photos_acknowledged"):
            await update.message.reply_text(
                "Фото сохранено. Прикрепите ещё или нажмите «Готово».",
                reply_markup=screenshot_prompt_keyboard(user_id)
            )
            context.user_data["photos_acknowledged"] = True
    else:
        await update.message.reply_text("Фото сейчас не требуется. Если хотите начать заново — нажмите /start.")


async def screenshots_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[STATES["STAGE"]] = "choose_manager"
    keyboard = build_manager_keyboard(update.effective_user.id)
    await query.edit_message_text("Кто старший менеджер на смене?", reply_markup=InlineKeyboardMarkup(keyboard))


async def skip_screenshots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки «Пропустить» — минуем этап загрузки скриншотов (видна только владельцу)."""
    query = update.callback_query
    await query.answer()
    # убедимся, что ключ существует (пусть пустой список)
    context.user_data.setdefault(STATES["SCREENSHOTS"], [])
    context.user_data[STATES["STAGE"]] = "choose_manager"
    keyboard = build_manager_keyboard(update.effective_user.id)
    await query.edit_message_text("Кто старший менеджер на смене?", reply_markup=InlineKeyboardMarkup(keyboard))


def _chunk_list(items: List[str], size: int) -> List[List[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


async def send_to_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shift_manager = query.data.replace("sendto_", "")
    context.user_data[STATES["SHIFT_MANAGER"]] = shift_manager

    # Защита: TEST может выбрать и отправлять только владелец
    if shift_manager == "TEST" and update.effective_user.id != MY_USER_ID:
        await query.message.reply_text("⚠️ Недостаточно прав для отправки запросов этому менеджеру.")
        return

    user_data = context.user_data
    category = user_data.get(STATES["CATEGORY"])
    screenshots = user_data.get(STATES["SCREENSHOTS"], [])

    # Формируем текст
    if category == "overpayment":
        message_text = (
            f"Заявка ID: {user_data.get(STATES['REQUEST_ID'])}\n"
            f"Переплата в размере {user_data.get(STATES['AMOUNT'])}\n"
            f"Просьба связаться с клиентом для возврата средств\n"
            f"Реквизиты для возврата:"
        )
    elif category == "wrong_bank":
        message_text = (
            f"Заявка ID: {user_data.get(STATES['REQUEST_ID'])}\n"
            f"Отправили не на тот банк\n"
            f"Нужно было: {user_data.get(STATES['BANK_TO'])}\n"
            f"Перевели на: {user_data.get(STATES['BANK_FROM'])}\n"
            f"Уточните, пожалуйста, есть ли доступ к средствам"
        )
    elif category == "wrong_details":
        reason = user_data.get(STATES["REASON"])
        if reason == "Нет банка на реквизитах":
            message_text = (
                f"Заявка ID: {user_data.get(STATES['REQUEST_ID'])}\n"
                f"На реквизитах отсутствует банк"
            )
        elif reason == "Разные имена":
            message_text = (
                f"Заявка ID: {user_data.get(STATES['REQUEST_ID'])}\n"
                f"Разные имена\n"
                f"В платформе: {user_data.get(STATES['NAME_ON_PLATFORM'])}\n"
                f"На реквизитах: {user_data.get(STATES['NAME_ON_DETAILS'])}"
            )
        elif reason == "Проблемный номер":
            message_text = (
                f"Заявка ID: {user_data.get(STATES['REQUEST_ID'])}\n"
                f"Проблемный номер\n"
                f"Комментарий: {user_data.get(STATES['COMMENT'])}"
            )
        else:
            message_text = f"Заявка ID: {user_data.get(STATES['REQUEST_ID'])}\n(подробности не указаны)"
    elif category == "funds_received":
        message_text = (
            f"Заявка ID: {user_data.get(STATES['REQUEST_ID'])}\n"
            f"Просьба уточнить поступление {user_data.get(STATES['AMOUNT'])}"
        )
    else:
        message_text = f"Заявка ID: {user_data.get(STATES['REQUEST_ID'])}"

    # Кому отправляем
    chat_id = MANAGER_CHAT_IDS.get(shift_manager)
    if not chat_id:
        await query.message.reply_text("⚠️ Ошибка: chat_id менеджера не найден.")
        return

    # ID инициатора (чтобы уведомить его по кнопке «Запрос сделан»)
    requester_id = update.effective_user.id
    manager_action_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Запрос сделан", callback_data=f"mark_done_{requester_id}")]
    ])

    try:
        # 1 фото → send_photo; 2–10 → send_media_group; >10 → чанками по 10
        if screenshots:
            if len(screenshots) == 1:
                await context.bot.send_photo(chat_id=chat_id, photo=screenshots[0])
            else:
                for chunk in _chunk_list(screenshots, 10):
                    media = [InputMediaPhoto(photo_id) for photo_id in chunk]
                    await context.bot.send_media_group(chat_id=chat_id, media=media)

        # Текст запроса + кнопка для менеджера
        await context.bot.send_message(chat_id=chat_id, text=message_text, reply_markup=manager_action_kb)

        keyboard = [[InlineKeyboardButton("Создать ещё один запрос", callback_data="start")]]
        await query.message.reply_text("✅ Запрос отправлен.", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data.clear()
    except Exception as e:
        await query.message.reply_text(f"⚠️ Не удалось отправить сообщение менеджеру: {e}")


async def request_mark_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Менеджер нажал «Запрос сделан» в своём чате.
    Уведомляем инициатора запроса.
    """
    query = update.callback_query
    await query.answer()
    data = query.data  # формат: mark_done_{worker_id}
    try:
        worker_id = int(data.split("_", 2)[2])
    except Exception:
        await query.answer("Ошибка данных кнопки.", show_alert=True)
        return

    # Отправим уведомление работнику
    try:
        await context.bot.send_message(
            chat_id=worker_id,
            text="Запрос был отправлен партнеру, ждите обратной связи"
        )
        # Небольшое уведомление менеджеру
        await query.answer("Уведомление отправлено сотруднику.", show_alert=False)
    except Exception as e:
        await query.answer(f"Не удалось уведомить сотрудника: {e}", show_alert=True)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Окей, отменил. Нажмите /start, чтобы начать заново.")


async def setup_menu(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Создать запрос"),
        BotCommand("cancel", "Отменить и начать заново"),
    ])
    await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())


def main():
    token = get_bot_token()  # <-- безопасно берём токен из окружения
    app = Application.builder().token(token).build()

    # Инициализация меню
    asyncio.get_event_loop().run_until_complete(setup_menu(app))

    # Хэндлеры
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))

    app.add_handler(CallbackQueryHandler(start, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(overpayment|wrong_bank|wrong_details|funds_received)$"))
    app.add_handler(CallbackQueryHandler(wrong_details_reason, pattern="^(no_bank|diff_names|bad_number)$"))
    app.add_handler(CallbackQueryHandler(screenshots_done, pattern="^screenshots_done$"))
    app.add_handler(CallbackQueryHandler(skip_screenshots, pattern="^skip_screenshots$"))
    app.add_handler(CallbackQueryHandler(send_to_manager, pattern="^sendto_"))
    app.add_handler(CallbackQueryHandler(request_mark_done, pattern=r"^mark_done_\d+$"))

    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
