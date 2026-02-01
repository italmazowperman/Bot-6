import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode
import sys
import schedule
import time
import threading

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация менеджеров
from database import DatabaseManager
from notification_service import NotificationService
from pdf_generator import generate_order_pdf, generate_summary_pdf
import io

db = DatabaseManager()
notification_service = NotificationService()

# Переменные для уведомлений
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_IDS = os.getenv('ADMIN_CHAT_IDS', '').split(',')

# Команда /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    chat_id = str(update.effective_chat.id)
    
    # Подписываем пользователя на уведомления
    notification_service.subscribe_user(chat_id)
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я бот логистической компании Margiana Logistic Services.
Теперь вы подписаны на уведомления об изменениях заказов.

📋 *Доступные команды:*

*Основные команды:*
/active - Активные заказы
/today - События сегодня
/search <текст> - Поиск заказов
/status <статус> - Заказы по статусу
/orders_no_photos - Заказы без фото загрузки

*Отчеты:*
/summary - Сводный отчет
/pdf <номер_заказа> - PDF отчет по заказу
/pdf_summary - Сводный PDF отчет

*Уведомления:*
/subscribe - Подписаться на уведомления
/unsubscribe - Отписаться от уведомлений
/settings - Настройки уведомлений

*Помощь:*
/help - Показать все команды
/contacts - Контакты компании
"""
    
    keyboard = [
        [InlineKeyboardButton("📊 Активные заказы", callback_data="active")],
        [InlineKeyboardButton("📅 События сегодня", callback_data="today")],
        [InlineKeyboardButton("📷 Без фото", callback_data="nophotos")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")]
    ]
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Команда /orders_no_photos
async def orders_no_photos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Заказы без фото загрузки"""
    try:
        orders = db.get_orders_without_photos()
        
        if not orders:
            await update.message.reply_text(
                "✅ Все заказы имеют фото загрузки!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = f"📷 *Заказы без фото загрузки* ({len(orders)}):\n\n"
        for i, order in enumerate(orders[:15], 1):
            text += f"{i}. *{order.order_number}*\n"
            text += f"   👤 {order.client_name}\n"
            text += f"   📍 {order.route}\n"
            text += f"   📦 Контейнеров: {order.container_count}\n"
            text += f"   📅 Создан: {order.creation_date.strftime('%d.%m.%Y')}\n\n"
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка: {str(e)[:100]}"
        )

# Команда /pdf
async def pdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сгенерировать PDF отчет по заказу"""
    if not context.args:
        await update.message.reply_text(
            "📄 Использование: `/pdf <номер_заказа>`\n\n"
            "Пример: `/pdf ORD-001`\n"
            "Пример: `/pdf 2024-001`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    order_number = ' '.join(context.args)
    try:
        order = db.get_order_by_number(order_number)
        
        if not order:
            await update.message.reply_text(
                f"❌ Заказ '{order_number}' не найден.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Генерируем PDF
        pdf_bytes = generate_order_pdf(order)
        
        # Отправляем PDF
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename=f"Отчет_{order_number}_{datetime.now().strftime('%Y%m%d')}.pdf",
            caption=f"📄 Отчет по заказу {order_number}"
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка генерации PDF: {str(e)[:100]}"
        )

# Команда /pdf_summary
async def pdf_summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сгенерировать сводный PDF отчет"""
    try:
        # Получаем период из аргументов
        days = 30
        if context.args:
            try:
                days = int(context.args[0])
                if days > 365:
                    days = 365
            except:
                pass
        
        # Генерируем PDF
        pdf_bytes = generate_summary_pdf(days)
        
        # Отправляем PDF
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename=f"Сводный_отчет_{datetime.now().strftime('%Y%m%d')}.pdf",
            caption=f"📊 Сводный отчет за {days} дней"
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка генерации PDF: {str(e)[:100]}"
        )

# Команда /subscribe
async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подписаться на уведомления"""
    chat_id = str(update.effective_chat.id)
    
    try:
        success = notification_service.subscribe_user(chat_id)
        
        if success:
            await update.message.reply_text(
                "✅ Вы подписаны на уведомления!\n\n"
                "Вы будете получать:\n"
                "• Изменения статусов заказов\n"
                "• Напоминания о событиях\n"
                "• Оповещения о проблемах\n\n"
                "Используйте /settings для настройки",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось подписаться. Попробуйте позже."
            )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка: {str(e)[:100]}"
        )

# Команда /unsubscribe
async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отписаться от уведомлений"""
    chat_id = str(update.effective_chat.id)
    
    try:
        success = notification_service.unsubscribe_user(chat_id)
        
        if success:
            await update.message.reply_text(
                "❌ Вы отписаны от уведомлений.\n"
                "Используйте /subscribe чтобы подписаться снова.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось отписаться."
            )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка: {str(e)[:100]}"
        )

# Команда /settings
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройки уведомлений"""
    chat_id = str(update.effective_chat.id)
    
    try:
        settings = notification_service.get_user_settings(chat_id)
        
        if not settings:
            await update.message.reply_text(
                "Вы не подписаны на уведомления. Используйте /subscribe"
            )
            return
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Уведомления о событиях", 
                                   callback_data="toggle_events"),
                InlineKeyboardButton("✅" if settings['notify_events'] else "❌", 
                                   callback_data="toggle_events_status")
            ],
            [
                InlineKeyboardButton("⏰ Напоминания", 
                                   callback_data="toggle_reminders"),
                InlineKeyboardButton("✅" if settings['notify_reminders'] else "❌", 
                                   callback_data="toggle_reminders_status")
            ],
            [
                InlineKeyboardButton("⚠️ Оповещения", 
                                   callback_data="toggle_alerts"),
                InlineKeyboardButton("✅" if settings['notify_alerts'] else "❌", 
                                   callback_data="toggle_alerts_status")
            ],
            [
                InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
            ]
        ]
        
        text = f"""
⚙️ *Настройки уведомлений:*

📅 Уведомления о событиях: {'✅ Включено' if settings['notify_events'] else '❌ Выключено'}
⏰ Напоминания за {settings['hours_before']} часов: {'✅ Включено' if settings['notify_reminders'] else '❌ Выключено'}
⚠️ Оповещения о проблемах: {'✅ Включено' if settings['notify_alerts'] else '❌ Выключено'}

Нажмите на кнопки чтобы изменить настройки.
"""
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка: {str(e)[:100]}"
        )

# Функция для отправки уведомлений
async def send_notifications(context: ContextTypes.DEFAULT_TYPE):
    """Отправка уведомлений"""
    try:
        notifications = notification_service.get_upcoming_notifications()
        
        for notification in notifications:
            chat_id = notification['chat_id']
            message = notification['message']
            
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Помечаем как отправленное
                notification_service.mark_notification_sent(notification['id'])
                
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка получения уведомлений: {e}")

# Фоновая задача для уведомлений
async def notification_job(context: ContextTypes.DEFAULT_TYPE):
    """Фоновая задача для проверки уведомлений"""
    await send_notifications(context)

# Функция для запуска планировщика
def start_scheduler(application):
    """Запуск планировщика уведомлений"""
    # Проверяем каждые 5 минут
    job_queue = application.job_queue
    job_queue.run_repeating(notification_job, interval=300, first=10)

# Основная функция
def main():
    """Запуск бота"""
    logger.info("=" * 50)
    logger.info("🚀 Запуск Logistics Telegram Bot с уведомлениями")
    logger.info("=" * 50)
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не найден!")
        sys.exit(1)
    
    # Создание приложения
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("dbstatus", dbstatus_command))
    application.add_handler(CommandHandler("active", active_orders_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(CommandHandler("contacts", contacts_command))
    application.add_handler(CommandHandler("orders_no_photos", orders_no_photos_command))
    application.add_handler(CommandHandler("pdf", pdf_command))
    application.add_handler(CommandHandler("pdf_summary", pdf_summary_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    application.add_handler(CommandHandler("settings", settings_command))
    
    # Регистрация обработчика callback-запросов
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Регистрация обработчика ошибок
    application.add_error_handler(error_handler)
    
    # Запуск планировщика уведомлений
    start_scheduler(application)
    
    logger.info("✅ Бот запущен и готов к работе!")
    logger.info("ℹ️  Уведомления включены, проверка каждые 5 минут")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
