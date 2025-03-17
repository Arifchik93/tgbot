import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ApplicationBuilder
import dateparser
import os
import psycopg2
from psycopg2 import sql

# Функция для подключения к базе данных
def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def drop_tables():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS notes")
    c.execute("DROP TABLE IF EXISTS reminders")
    conn.commit()
    conn.close()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы для действий
ACTION_ADD_NOTE = 'add_note'
ACTION_ADD_REMINDER = 'add_reminder'
ACTION_EDIT_NOTE = 'edit_note'
ACTION_EDIT_REMINDER = 'edit_reminder'

# Инициализация базы данных
def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    user_id BIGINT,
                    tag TEXT,
                    note TEXT
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    user_id BIGINT,
                    reminder_time TIMESTAMP,
                    reminder_text TEXT
                )
            ''')
            conn.commit()

# Добавление заметки
def add_note(user_id, tag, note):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO notes (user_id, tag, note) VALUES (%s, %s, %s)", (user_id, tag, note))
            conn.commit()

# Поиск заметок по тегу
def find_notes(user_id, tag=None):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            if tag:
                c.execute("SELECT note FROM notes WHERE user_id=%s AND tag=%s", (user_id, tag))
            else:
                c.execute("SELECT note FROM notes WHERE user_id=%s", (user_id,))
            notes = c.fetchall()
    return notes

# Получение всех тегов заметок
def get_all_tags(user_id):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT DISTINCT tag FROM notes WHERE user_id=%s", (user_id,))
            tags = c.fetchall()
    return tags

# Удаление заметки
def delete_note(user_id, note_text):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("DELETE FROM notes WHERE user_id=%s AND note=%s", (user_id, note_text))
            conn.commit()

# Добавление напоминания
def add_reminder(user_id, reminder_time, reminder_text):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO reminders (user_id, reminder_time, reminder_text) VALUES (%s, %s, %s)", 
                      (user_id, reminder_time, reminder_text))
            conn.commit()

# Удаление напоминания
def delete_reminder(user_id, reminder_text):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("DELETE FROM reminders WHERE user_id=%s AND reminder_text=%s", (user_id, reminder_text))
            conn.commit()

# Получение напоминаний на определенную дату
def get_reminders_by_date(user_id, date):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT reminder_time, reminder_text FROM reminders WHERE user_id=%s AND DATE(reminder_time)=%s ORDER BY reminder_time", 
                      (user_id, date))
            reminders = c.fetchall()
    return reminders

# Получение напоминаний на неделю
def get_reminders_for_week(user_id):
    today = datetime.now().date()
    next_week = today + timedelta(days=7)
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT reminder_time, reminder_text FROM reminders WHERE user_id=%s AND reminder_time BETWEEN %s AND %s ORDER BY reminder_time", 
                      (user_id, today, next_week))
            reminders = c.fetchall()
    return reminders

# Получение прошедших напоминаний
def get_past_reminders(user_id):
    today = datetime.now().date()
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT reminder_time, reminder_text FROM reminders WHERE user_id=%s AND reminder_time < %s ORDER BY reminder_time", 
                      (user_id, today))
            reminders = c.fetchall()
    return reminders

# Главное меню с Inline-клавиатурой и Reply-клавиатурой
async def start(update: Update, context) -> None:
    inline_keyboard = [
        [InlineKeyboardButton("Добавить заметку", callback_data=ACTION_ADD_NOTE)],
        [InlineKeyboardButton("Добавить напоминание", callback_data=ACTION_ADD_REMINDER)],
        [InlineKeyboardButton("Заметки", callback_data='notes_menu')],
        [InlineKeyboardButton("Напоминания", callback_data='reminders_menu')]
    ]
    inline_reply_markup = InlineKeyboardMarkup(inline_keyboard)

    reply_keyboard = [
        ["Меню"],
        ["Добавить заметку", "Добавить напоминание"]
    ]
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    await update.message.reply_text("Или используйте меню ниже:", reply_markup=inline_reply_markup)

# Меню заметок
async def notes_menu(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Все теги заметок", callback_data='all_tags')],
        [InlineKeyboardButton("Поиск по тегу", callback_data='find_note')],
        [InlineKeyboardButton("Все заметки", callback_data='all_notes')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Меню заметок:", reply_markup=reply_markup)

# Меню напоминаний
async def reminders_menu(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Напоминания на сегодня", callback_data='today_reminders')],
        [InlineKeyboardButton("Напоминания на завтра", callback_data='tomorrow_reminders')],
        [InlineKeyboardButton("Напоминания на неделю", callback_data='week_reminders')],
        [InlineKeyboardButton("Прошлые напоминания", callback_data='past_reminders')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Меню напоминаний:", reply_markup=reply_markup)

# Отображение всех тегов заметок
async def all_tags(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    tags = get_all_tags(user_id)

    if tags:
        keyboard = [[InlineKeyboardButton(tag[0], callback_data=f"tag_{tag[0]}")] for tag in tags]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Все теги заметок:", reply_markup=reply_markup)
    else:
        await query.edit_message_text(text="У вас нет заметок с тегами.")

# Отображение заметок по тегу
async def show_notes_by_tag(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    tag = query.data.split('_', 1)[1]
    notes = find_notes(user_id, tag)

    if notes:
        for note in notes:
            keyboard = [
                [InlineKeyboardButton("✏️", callback_data=f"edit_note_{note[0]}"),
                 InlineKeyboardButton("❌", callback_data=f"delete_note_{note[0]}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(f"Тег: {tag}\nЗаметка: {note[0]}", reply_markup=reply_markup)
    else:
        await query.edit_message_text(text=f"Заметок с тегом {tag} не найдено.")

# Отображение всех заметок
async def all_notes(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    notes = find_notes(user_id, "")

    if notes:
        for note in notes:
            keyboard = [
                [InlineKeyboardButton("✏️", callback_data=f"edit_note_{note[0]}"),
                 InlineKeyboardButton("❌", callback_data=f"delete_note_{note[0]}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(f"Заметка: {note[0]}", reply_markup=reply_markup)
    else:
        await query.edit_message_text(text="У вас нет заметок.")

# Отображение напоминаний
async def show_reminders(update: Update, context, reminders, message_text):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if reminders:
        for reminder in reminders:
            reminder_time = reminder[0]
            reminder_text = reminder[1]
            keyboard = [
                [InlineKeyboardButton("✏️", callback_data=f"edit_reminder_{reminder_text}"),
                 InlineKeyboardButton("❌", callback_data=f"delete_reminder_{reminder_text}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(f"{message_text} {reminder_time.strftime('%Y-%m-%d %H:%M')}:\n{reminder_text}", reply_markup=reply_markup)
    else:
        await query.edit_message_text(text=f"У вас нет {message_text}.")

# Отображение напоминаний на сегодня
async def today_reminders(update: Update, context) -> None:
    user_id = update.callback_query.from_user.id
    today = datetime.now().date()
    reminders = get_reminders_by_date(user_id, today)
    await show_reminders(update, context, reminders, "напоминаний на сегодня")

# Отображение напоминаний на завтра
async def tomorrow_reminders(update: Update, context) -> None:
    user_id = update.callback_query.from_user.id
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    reminders = get_reminders_by_date(user_id, tomorrow)
    await show_reminders(update, context, reminders, "напоминаний на завтра")

# Отображение напоминаний на неделю
async def week_reminders(update: Update, context) -> None:
    user_id = update.callback_query.from_user.id
    reminders = get_reminders_for_week(user_id)
    await show_reminders(update, context, reminders, "напоминаний на неделю")

# Отображение прошедших напоминаний
async def past_reminders(update: Update, context) -> None:
    user_id = update.callback_query.from_user.id
    reminders = get_past_reminders(user_id)
    await show_reminders(update, context, reminders, "прошедших напоминаний")

# Обработка нажатий на кнопки редактирования и удаления
async def button(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    callback_data = query.data

    if callback_data.startswith('edit_note_'):
        note_text = callback_data.split('_', 2)[2]
        context.user_data['action'] = ACTION_EDIT_NOTE
        context.user_data['note_to_edit'] = note_text
        await query.edit_message_text(text=f"Редактируем заметку: {note_text}\nВведите новый текст заметки:")
    elif callback_data.startswith('delete_note_'):
        note_text = callback_data.split('_', 2)[2]
        delete_note(user_id, note_text)
        await query.edit_message_text(text=f"Заметка удалена: {note_text}")
    elif callback_data.startswith('edit_reminder_'):
        reminder_text = callback_data.split('_', 2)[2]
        context.user_data['action'] = ACTION_EDIT_REMINDER
        context.user_data['reminder_to_edit'] = reminder_text
        await query.edit_message_text(text=f"Редактируем напоминание: {reminder_text}\nВведите новый текст и время:")
    elif callback_data.startswith('delete_reminder_'):
        reminder_text = callback_data.split('_', 2)[2]
        delete_reminder(user_id, reminder_text)
        await query.edit_message_text(text=f"Напоминание удалено: {reminder_text}")
    elif callback_data == ACTION_ADD_NOTE:
        await query.edit_message_text(text="Введите заметку в формате: #тег текст заметки")
        context.user_data['action'] = ACTION_ADD_NOTE
    elif callback_data == ACTION_ADD_REMINDER:
        await query.edit_message_text(text="Введите напоминание в формате: текст напоминания - дата и время")
        context.user_data['action'] = ACTION_ADD_REMINDER
    elif callback_data == 'notes_menu':
        await notes_menu(update, context)
    elif callback_data == 'reminders_menu':
        await reminders_menu(update, context)
    elif callback_data == 'all_tags':
        await all_tags(update, context)
    elif callback_data == 'all_notes':
        await all_notes(update, context)
    elif callback_data == 'today_reminders':
        await today_reminders(update, context)
    elif callback_data == 'tomorrow_reminders':
        await tomorrow_reminders(update, context)
    elif callback_data == 'week_reminders':
        await week_reminders(update, context)
    elif callback_data == 'past_reminders':
        await past_reminders(update, context)
    elif callback_data.startswith('tag_'):
        await show_notes_by_tag(update, context)

# Указываем ваш часовой пояс (UTC+3)
MY_TIMEZONE = timezone(timedelta(hours=3))

async def handle_message(update: Update, context) -> None:
    user_id = update.message.from_user.id
    text = update.message.text

    if text == "Добавить заметку":
        await update.message.reply_text("Введите заметку в формате: #тег текст заметки")
        context.user_data['action'] = ACTION_ADD_NOTE
    elif text == "Добавить напоминание":
        await update.message.reply_text("Введите напоминание в формате: текст напоминания - дата и время")
        context.user_data['action'] = ACTION_ADD_REMINDER
    elif text == "Меню":
        await start(update, context)
    else:
        action = context.user_data.get('action')
        if action == ACTION_ADD_NOTE:
            if '#' in text:
                tag, note = text.split(' ', 1)
                add_note(user_id, tag, note)
                await update.message.reply_text(f"Заметка добавлена с тегом {tag}:\n{note}")
            else:
                await update.message.reply_text("Неверный формат. Используйте #тег текст заметки")
        elif action == ACTION_ADD_REMINDER:
            try:
                if '-' in text:
                    reminder_text, time_part = text.split('-', 1)
                    reminder_text = reminder_text.strip()
                    time_part = time_part.strip()

                    # Парсим время с учетом локального времени пользователя
                    reminder_time = dateparser.parse(time_part, languages=['ru'], settings={'TIMEZONE': 'UTC+3'})
                    
                    if reminder_time:
                        # Явно устанавливаем часовой пояс UTC+3
                        reminder_time = reminder_time.replace(tzinfo=MY_TIMEZONE)
                        # Преобразуем в UTC для хранения в базе данных
                        reminder_time_utc = reminder_time.astimezone(timezone.utc)
                        add_reminder(user_id, reminder_time_utc, reminder_text)
                        await update.message.reply_text(f"Напоминание добавлено на {reminder_time.strftime('%Y-%m-%d %H:%M')} (UTC+3):\n{reminder_text}")
                    else:
                        await update.message.reply_text("Не удалось распознать дату и время. Попробуйте еще раз.")
                else:
                    await update.message.reply_text("Неверный формат. Используйте: текст напоминания - дата и время")
            except Exception as e:
                logger.error(f"Ошибка при добавлении напоминания: {e}")
                await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
        elif action == ACTION_EDIT_NOTE:
            new_note_text = text
            old_note_text = context.user_data.get('note_to_edit')
            delete_note(user_id, old_note_text)
            add_note(user_id, context.user_data.get('tag'), new_note_text)
            await update.message.reply_text(f"Заметка отредактирована:\n{new_note_text}")
            context.user_data.pop('action')
            context.user_data.pop('note_to_edit')
        elif action == ACTION_EDIT_REMINDER:
            try:
                if '-' in text:
                    new_reminder_text, time_part = text.split('-', 1)
                    new_reminder_text = new_reminder_text.strip()
                    time_part = time_part.strip()

                    # Парсим время с учетом локального времени пользователя
                    new_reminder_time = dateparser.parse(time_part, languages=['ru'], settings={'TIMEZONE': 'UTC+3'})
                    
                    if new_reminder_time:
                        # Явно устанавливаем часовой пояс UTC+3
                        new_reminder_time = new_reminder_time.replace(tzinfo=MY_TIMEZONE)
                        # Преобразуем в UTC для хранения в базе данных
                        new_reminder_time_utc = new_reminder_time.astimezone(timezone.utc)
                        old_reminder_text = context.user_data.get('reminder_to_edit')
                        delete_reminder(user_id, old_reminder_text)
                        add_reminder(user_id, new_reminder_time_utc, new_reminder_text)
                        await update.message.reply_text(f"Напоминание отредактировано на {new_reminder_time.strftime('%Y-%m-%d %H:%M')} (UTC+3):\n{new_reminder_text}")
                    else:
                        await update.message.reply_text("Не удалось распознать дату и время. Попробуйте еще раз.")
                else:
                    await update.message.reply_text("Неверный формат. Используйте: текст напоминания - дата и время")
            except Exception as e:
                logger.error(f"Ошибка при редактировании напоминания: {e}")
                await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
            context.user_data.pop('action')
            context.user_data.pop('reminder_to_edit')
            
async def check_reminders(context):
    try:
        # Получаем текущее время в UTC
        now = datetime.now(timezone.utc)
        logger.info(f"Проверка напоминаний. Текущее время: {now}")
        
        # Ищем напоминания, время которых наступило
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("SELECT user_id, reminder_text FROM reminders WHERE reminder_time <= %s", (now,))
                reminders = c.fetchall()
        
        logger.info(f"Найдено напоминаний: {len(reminders)}")
        
        # Отправляем уведомления и удаляем напоминания
        for reminder in reminders:
            user_id, reminder_text = reminder
            await context.bot.send_message(chat_id=user_id, text=f"⏰ Напоминание: {reminder_text}")
            delete_reminder(user_id, reminder_text)  # Удаляем напоминание после отправки
        
    except Exception as e:
        logger.error(f"Ошибка в check_reminders: {e}")
        
# Основная функция
def main() -> None:
    # удаление бд
    drop_tables() 
    # Инициализация базы данных
    init_db()

    # Получение токена из переменной окружения
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # Проверка наличия токена
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Токен Telegram-бота не задан. Убедитесь, что переменная окружения TELEGRAM_BOT_TOKEN установлена.")

    # Создание приложения с поддержкой JobQueue
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Добавление фоновой задачи для проверки напоминаний
    application.job_queue.run_repeating(check_reminders, interval=60.0, first=0.0)

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
