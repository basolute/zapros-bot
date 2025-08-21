from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardRemove, InputMediaPhoto, MenuButtonCommands, BotCommand
)
import asyncio
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# Имена работников и старших менеджеров
MANAGERS = ['Dima', 'Masha', 'Olka']

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
MANAGER_CHAT_IDS = {
    "Dima": 7367191192 , #1040008041
    "Masha": 874826440 ,
    "Olka": 950905671
    
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Переплата", callback_data="overpayment")],
        [InlineKeyboardButton("Перевод не на тот банк", callback_data="wrong_bank")],
        [InlineKeyboardButton("Неверные реквизиты", callback_data="wrong_details")],
        [InlineKeyboardButton("Поступление средств", callback_data="funds_received")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.user_data.clear()

    if update.message:
        await update.message.reply_text(
            "Для того чтобы составить запрос нажмите на одну из кнопок",
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "Для того чтобы составить запрос нажмите на одну из кнопок",
            reply_markup=reply_markup
        )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data
    context.user_data[STATES["CATEGORY"]] = category
    context.user_data[STATES["STAGE"]] = "select_worker"
    context.user_data[STATES["STAGE"]] = "request_id"
    await query.edit_message_text("Введите ID заявки:")



async def select_worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    worker = query.data.replace("worker_", "")
    if worker == "none":
        context.user_data[STATES["MANAGER"]] = None
    else:
        context.user_data[STATES["MANAGER"]] = worker

    category = context.user_data[STATES["CATEGORY"]]
    context.user_data[STATES["STAGE"]] = "request_id"
    await query.edit_message_text("Введите ID заявки:")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    stage = context.user_data.get(STATES["STAGE"])
    category = context.user_data.get(STATES["CATEGORY"])

    if stage == "request_id":
        context.user_data[STATES["REQUEST_ID"]] = text
        if category == "overpayment" or category == "funds_received":
            context.user_data[STATES["STAGE"]] = "amount"
            await update.message.reply_text("Введите сумму:")
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
        context.user_data[STATES["AMOUNT"]] = text
        if category == "funds_received":
            context.user_data[STATES["STAGE"]] = "choose_manager"
            keyboard = [[InlineKeyboardButton(name, callback_data=f"sendto_{name}")] for name in MANAGERS]
            await update.message.reply_text("Кто старший менеджер на смене?", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            context.user_data[STATES["STAGE"]] = "screenshot"
            await update.message.reply_text("Прикрепите скриншоты (можно несколько), затем нажмите Готово")

    elif stage == "bank_to":
        context.user_data[STATES["BANK_TO"]] = text
        context.user_data[STATES["STAGE"]] = "bank_from"
        await update.message.reply_text("На какой банк перевели по факту:")

    elif stage == "bank_from":
        context.user_data[STATES["BANK_FROM"]] = text
        context.user_data[STATES["STAGE"]] = "screenshot"
        await update.message.reply_text("Прикрепите скриншоты (можно несколько), затем нажмите Готово")

    elif stage == "name_platform":
        context.user_data[STATES["NAME_ON_PLATFORM"]] = text
        context.user_data[STATES["STAGE"]] = "name_details"
        await update.message.reply_text("Какое имя указано на реквизитах?")

    elif stage == "name_details":
        context.user_data[STATES["NAME_ON_DETAILS"]] = text
        context.user_data[STATES["STAGE"]] = "screenshot"
        await update.message.reply_text("Прикрепите скриншоты (можно несколько), затем нажмите Готово")

    elif stage == "bad_number_comment":
        context.user_data[STATES["COMMENT"]] = text
        context.user_data[STATES["STAGE"]] = "choose_manager"
        keyboard = [[InlineKeyboardButton(name, callback_data=f"sendto_{name}")] for name in MANAGERS]
        await update.message.reply_text("Кто старший менеджер на смене?", reply_markup=InlineKeyboardMarkup(keyboard))


async def wrong_details_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reason = query.data

    if reason == "no_bank":
        context.user_data[STATES["REASON"]] = "Нет банка на реквизитах"
        context.user_data[STATES["STAGE"]] = "screenshot"
        await query.edit_message_text("Прикрепите скриншоты (можно несколько), затем нажмите Готово")
    
    elif reason == "diff_names":
        context.user_data[STATES["REASON"]] = "Разные имена"
        context.user_data[STATES["STAGE"]] = "name_platform"
        await query.edit_message_text("Какое имя указано в платформе?")
    
    elif reason == "bad_number":
        context.user_data[STATES["REASON"]] = "Проблемный номер"
        context.user_data[STATES["STAGE"]] = "bad_number_comment"
        await query.edit_message_text("Опишите в чём проблема:")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stage = context.user_data.get(STATES["STAGE"])
    if stage == "screenshot":
        if STATES["SCREENSHOTS"] not in context.user_data:
            context.user_data[STATES["SCREENSHOTS"]] = []

        photo_id = update.message.photo[-1].file_id
        context.user_data[STATES["SCREENSHOTS"]].append(photo_id)

        # "Готово"
        if not context.user_data.get("photos_acknowledged"):
            keyboard = [[InlineKeyboardButton("Готово", callback_data="screenshots_done")]]
            await update.message.reply_text(
                "Фото сохранено. Прикрепите ещё или нажмите \"Готово\".",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            context.user_data["photos_acknowledged"] = True

async def screenshots_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[STATES["STAGE"]] = "choose_manager"
    keyboard = [[InlineKeyboardButton(name, callback_data=f"sendto_{name}")] for name in MANAGERS]
    await query.edit_message_text("Кто старший менеджер на смене?", reply_markup=InlineKeyboardMarkup(keyboard))

async def send_to_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shift_manager = query.data.replace("sendto_", "")
    context.user_data[STATES["SHIFT_MANAGER"]] = shift_manager
    user_data = context.user_data
    category = user_data[STATES["CATEGORY"]]
    screenshots = user_data.get(STATES["SCREENSHOTS"], [])

    # Формируем текст
    if category == "overpayment":
        message_text = (
            f"Заявка ID: {user_data[STATES['REQUEST_ID']]}\n"
            f"Переплата в размере {user_data[STATES['AMOUNT']]}\n"
            f"Просьба связаться с клиентом для возврата средств\n"
            f"Реквизиты для возврата:"
        )

    elif category == "wrong_bank":
        message_text = (
            f"Заявка ID: {user_data[STATES['REQUEST_ID']]}\n"
            f"Отправили не на тот банк\n"
            f"Нужно было: {user_data[STATES['BANK_TO']]}\n"
            f"Перевели на: {user_data[STATES['BANK_FROM']]}\n"
            f"Уточните пожалуйста есть ли доступ к средствам"
        )

    elif category == "wrong_details":
        reason = user_data[STATES["REASON"]]
        if reason == "Нет банка на реквизитах":
            message_text = (
                f"Заявка ID: {user_data[STATES['REQUEST_ID']]}\n"
                f"На реквизитах отсутствует банк"
            )
        elif reason == "Разные имена":
            message_text = (
                f"Заявка ID: {user_data[STATES['REQUEST_ID']]}\n"
                f"Разные имена\n"
                f"В платформе: {user_data[STATES['NAME_ON_PLATFORM']]}\n"
                f"На реквизитах: {user_data[STATES['NAME_ON_DETAILS']]}"
            )
        elif reason == "Проблемный номер":
            message_text = (
                f"Заявка ID: {user_data[STATES['REQUEST_ID']]}\n"
                f"Проблемный номер\n"
                f"Комментарий: {user_data[STATES['COMMENT']]}"
            )

    elif category == "funds_received":
        message_text = (
            f"Заявка ID: {user_data[STATES['REQUEST_ID']]}\n"
            f"Просьба уточнить поступление {user_data[STATES['AMOUNT']]}"
        )

    # Отправляем старшему менеджеру
    chat_id = MANAGER_CHAT_IDS.get(shift_manager)
    if chat_id:
        if screenshots:
            media = [InputMediaPhoto(photo_id) for photo_id in screenshots]
            await context.bot.send_media_group(chat_id=chat_id, media=media)
        await context.bot.send_message(chat_id=chat_id, text=message_text)
    else:
        await query.message.reply_text("⚠️ Ошибка: chat_id старшего менеджера не найден.")

    keyboard = [[InlineKeyboardButton("Создать ещё один запрос", callback_data="start")]]
    await query.message.reply_text("✅ Запрос отправлен.", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data.clear()



async def setup_menu(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Создать запрос")
    ])
    await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

def main():
    app = Application.builder().token("7551888806:AAHEqSnn4NZtKCLSAL6r5vOuwvgTnTjrC-o").build()
    asyncio.get_event_loop().run_until_complete(setup_menu(app))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(overpayment|wrong_bank|wrong_details|funds_received)$"))
    app.add_handler(CallbackQueryHandler(wrong_details_reason, pattern="^(no_bank|diff_names|bad_number)$"))
    app.add_handler(CallbackQueryHandler(screenshots_done, pattern="^screenshots_done$"))
    app.add_handler(CallbackQueryHandler(send_to_manager, pattern="^sendto_"))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
