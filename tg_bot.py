import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, JobQueue, ApplicationBuilder
import dateparser
import os
import asyncio 
import psycopg2
from psycopg2 import sql




# Функция для подключения к базе данных
def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))
        

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

def drop_tables():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS notes")
    c.execute("DROP TABLE IF EXISTS reminders")
    conn.commit()
    conn.close()
    
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
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
            reminder_time TEXT,
            reminder_text TEXT
        )
    ''')
    conn.commit()
    conn.close()
        
            
def execute_query(query, params=(), fetch=False):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(query, params)
    if fetch:
        result = c.fetchall()
        conn.close()
        return result
    conn.commit()
    conn.close()


# Добавление заметки
def add_note(user_id, tag, note):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO notes (user_id, tag, note) VALUES (%s, %s, %s)", (user_id, tag, note))
    conn.commit()
    conn.close()

# Поиск заметок по тегу
def find_notes(user_id, tag=None):
    conn = get_db_connection()
    c = conn.cursor()
    if tag:
        c.execute("SELECT note FROM notes WHERE user_id=%s AND tag=%s", (user_id, tag))
    else:
        c.execute("SELECT note FROM notes WHERE user_id=%s", (user_id,))
    notes = c.fetchall()
    conn.close()
    return notes

# Добавление напоминания
def add_reminder(user_id, reminder_time, reminder_text):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO reminders (user_id, reminder_time, reminder_text) VALUES (%s, %s, %s)", (user_id, reminder_time, reminder_text))
    conn.commit()
    conn.close()


# Получение всех тегов заметок
def get_all_tags(user_id):
    return execute_query("SELECT DISTINCT tag FROM notes WHERE user_id=?", (user_id,), fetch=True)

# Удаление заметки
def delete_note(user_id, note_text):
    execute_query("DELETE FROM notes WHERE user_id=? AND note=?", (user_id, note_text))

# Добавление напоминания
def add_reminder(user_id, reminder_time, reminder_text):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO reminders (user_id, reminder_time, reminder_text) VALUES (%s, %s, %s)", (user_id, reminder_time, reminder_text))
    conn.commit()
    conn.close()
    

# Удаление напоминания
def delete_reminder(user_id, reminder_text):
    execute_query("DELETE FROM reminders WHERE user_id=? AND reminder_text=?", (user_id, reminder_text))

# Получение напоминаний на определенную дату
def get_reminders_by_date(user_id, date):
    return execute_query("SELECT reminder_time, reminder_text FROM reminders WHERE user_id=? AND date(reminder_time)=? ORDER BY reminder_time", (user_id, date), fetch=True)

# Получение напоминаний на неделю
def get_reminders_for_week(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    next_week = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    return execute_query("SELECT reminder_time, reminder_text FROM reminders WHERE user_id=? AND date(reminder_time) BETWEEN ? AND ? ORDER BY reminder_time", (user_id, today, next_week), fetch=True)

# Получение прошедших напоминаний
def get_past_reminders(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    return execute_query("SELECT reminder_time, reminder_text FROM reminders WHERE user_id=? AND date(reminder_time) < ? ORDER BY reminder_time", (user_id, today), fetch=True)

from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup

# Главное меню с Inline-клавиатурой и Reply-клавиатурой
async def start(update: Update, context) -> None:
    # Создаем Inline-клавиатуру
    inline_keyboard = [
        [InlineKeyboardButton("Добавить заметку", callback_data=ACTION_ADD_NOTE)],
        [InlineKeyboardButton("Добавить напоминание", callback_data=ACTION_ADD_REMINDER)],
        [InlineKeyboardButton("Заметки", callback_data='notes_menu')],
        [InlineKeyboardButton("Напоминания", callback_data='reminders_menu')]
    ]
    inline_reply_markup = InlineKeyboardMarkup(inline_keyboard)

    # Создаем Reply-клавиатуру
    reply_keyboard = [
        ["Меню"],
        ["Добавить заметку", "Добавить напоминание"]
    ]
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)

    # Отправляем сообщение с обеими клавиатурами
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=reply_markup  # Reply-клавиатура
    )
    await update.message.reply_text(
        "Или используйте меню ниже:",
        reply_markup=inline_reply_markup  # Inline-клавиатура
    )


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
            reminder_time = datetime.fromisoformat(reminder[0])
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
    today = datetime.now().strftime('%Y-%m-%d')
    reminders = get_reminders_by_date(user_id, today)
    await show_reminders(update, context, reminders, "напоминаний на сегодня")

# Отображение напоминаний на завтра
async def tomorrow_reminders(update: Update, context) -> None:
    user_id = update.callback_query.from_user.id
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
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

# Обработка текстовых сообщений (включая Reply-клавиатуру)
async def handle_message(update: Update, context) -> None:
    user_id = update.message.from_user.id
    text = update.message.text

    # Обработка нажатий кнопок Reply-клавиатуры
    if text == "Добавить заметку":
        await update.message.reply_text("Введите заметку в формате: #тег текст заметки")
        context.user_data['action'] = ACTION_ADD_NOTE
    elif text == "Добавить напоминание":
        await update.message.reply_text("Введите напоминание в формате: текст напоминания - дата и время")
        context.user_data['action'] = ACTION_ADD_REMINDER
    elif text == "Меню":  # Обработка кнопки "Меню"
        await start(update, context)  # Запускаем команду /start
    else:
        # Обработка других текстовых сообщений (например, добавление заметки или напоминания)
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

                    reminder_time = dateparser.parse(time_part, languages=['ru'])

                    if reminder_time:
                        add_reminder(user_id, reminder_time.isoformat(), reminder_text)
                        await update.message.reply_text(f"Напоминание добавлено на {reminder_time.strftime('%Y-%m-%d %H:%M')}:\n{reminder_text}")
                    else:
                        await update.message.reply_text("Не удалось распознать дату и время. Попробуйте еще раз.")
                else:
                    await update.message.reply_text("Неверный формат. Используйте: текст напоминания - дата и время")
            except Exception as e:
                logger.error(f"Ошибка при добавлении напоминания: {e}")
                await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
                


async def check_reminders(context):
    try:
        # Получаем текущее время в UTC
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        logger.info(f"Проверка напоминаний. Текущее время: {now}")
        
        # Ищем напоминания, время которых наступило
        reminders = execute_query(
            "SELECT user_id, reminder_time, reminder_text FROM reminders WHERE reminder_time <= ?",
            (now,),
            fetch=True
        )
        logger.info(f"Найдено напоминаний: {len(reminders)}")
        
        # Логируем найденные напоминания
        for reminder in reminders:
            user_id, reminder_time, reminder_text = reminder
            logger.info(f"Напоминание для user_id={user_id}: {reminder_time} - {reminder_text}")
        
        # Отправляем уведомления и удаляем напоминания
        for reminder in reminders:
            user_id, reminder_time, reminder_text = reminder
            await context.bot.send_message(chat_id=user_id, text=f"⏰ Напоминание: {reminder_text}")
            delete_reminder(user_id, reminder_text)  # Удаляем напоминание после отправки
        
    except Exception as e:
        logger.error(f"Ошибка в check_reminders: {e}")
            

def main() -> None:
    drop_tables():
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
    application.job_queue.run_repeating(check_reminders, interval=300.0, first=0.0)

    # Запуск бота
    application.run_polling()
    

if __name__ == '__main__':
    main()
