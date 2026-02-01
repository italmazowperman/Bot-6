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

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверка обязательных переменных
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не найден!")
    logger.info("Добавьте TELEGRAM_BOT_TOKEN в переменные окружения Railway")
    logger.info("Получите токен у @BotFather в Telegram")
    sys.exit(1)

# Инициализация менеджеров с обработкой ошибок
try:
    from database import DatabaseManager
    from models import OrderStatus
    from utils import format_date, get_status_emoji, format_order_info
    
    db = DatabaseManager()
    logger.info("✅ База данных подключена успешно")
    
except Exception as e:
    logger.error(f"❌ Ошибка при подключении к базе данных: {e}")
    logger.info("Создаем временную базу данных для тестирования...")
    
    # Создаем простой заглушечный DatabaseManager для тестирования
    class MockDatabaseManager:
        def get_all_orders(self):
            return []
        def get_order_by_number(self, order_number):
            return None
        def get_orders_by_status(self, status):
            return []
        def get_orders_by_statuses(self, statuses):
            return []
        def get_active_orders(self):
            return []
        def search_orders(self, search_text):
            return []
        def get_statistics(self, days=30):
            return {
                'total_orders': 0,
                'completed_orders': 0,
                'active_orders': 0,
                'total_containers': 0,
                'total_weight': 0,
                'total_volume': 0,
                'period_days': days
            }
    
    db = MockDatabaseManager()
    
    # Заглушки для утилит
    def format_date(date):
        return date.strftime('%d.%m.%Y') if date else "-"
    
    def get_status_emoji(status):
        return "📋"
    
    def format_order_info(order):
        return f"Заказ: {order.order_number}"

# Команда /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я бот логистической компании Margiana Logistic Services.

📋 *Доступные команды:*

*Основные команды:*
/active - Активные заказы
/today - События сегодня
/search <текст> - Поиск заказов
/status <статус> - Заказы по статусу

*Отчеты:*
/summary - Сводный отчет
/contacts - Контакты компании

*Помощь:*
/help - Показать все команды
/dbstatus - Проверить статус базы данных

💡 *Примеры:*
`/search ORD-001`
`/status In Progress`
"""
    
    keyboard = [
        [InlineKeyboardButton("📊 Активные заказы", callback_data="active")],
        [InlineKeyboardButton("📅 События сегодня", callback_data="today")],
        [InlineKeyboardButton("📞 Контакты", callback_data="contacts")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Команда /dbstatus - проверка статуса БД
async def dbstatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить статус подключения к базе данных"""
    try:
        # Проверяем подключение
        orders_count = len(db.get_all_orders())
        
        # Получаем информацию о переменных окружения (без паролей)
        db_url = os.getenv('DATABASE_URL', 'Не установлена')
        bot_token_exists = bool(os.getenv('TELEGRAM_BOT_TOKEN'))
        
        status_text = f"""
📊 *Статус системы:*

✅ Бот запущен и работает
✅ Telegram токен: {'Установлен' if bot_token_exists else 'Отсутствует'}
✅ База данных: {'Подключена' if not isinstance(db, MockDatabaseManager) else 'Временная'}
📦 Заказов в базе: {orders_count}

*Переменные окружения:*
• DATABASE_URL: {'Установлена' if os.getenv('DATABASE_URL') else 'Отсутствует'}
• TELEGRAM_BOT_TOKEN: {'Установлен' if bot_token_exists else 'Отсутствует'}

*Для настройки:*
1. Получите токен у @BotFather
2. Создайте базу на Supabase.com
3. Добавьте переменные в Railway
"""
        
        await update.message.reply_text(
            status_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка проверки статуса: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать помощь"""
    help_text = """
📋 *Доступные команды:*

*Основные:*
/start - Начать работу
/active - Активные заказы
/today - События сегодня
/search [текст] - Поиск заказов
/status [статус] - Заказы по статусу

*Информация:*
/contacts - Контакты компании
/dbstatus - Статус базы данных

*Настройка:*
1. Получите токен бота у @BotFather
2. Создайте базу данных на supabase.com
3. Добавьте переменные в Railway:
   - TELEGRAM_BOT_TOKEN
   - DATABASE_URL
4. Перезапустите приложение

*Поддержка:*
Для помощи по настройке обратитесь к разработчику.
"""
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN
    )

# Команда /active
async def active_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные заказы"""
    try:
        orders = db.get_active_orders()
        
        if not orders:
            await update.message.reply_text(
                "📭 Нет активных заказов.\n\n"
                "Возможно:\n"
                "1. База данных пуста\n"
                "2. Нет заказов со статусами 'New', 'In Progress', 'In Transit'\n"
                "3. Не настроена синхронизация с WPF программой",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Проверить статус", callback_data="dbstatus")
                ]])
            )
            return
        
        text = f"📊 *Активные заказы* ({len(orders)}):\n\n"
        for i, order in enumerate(orders[:10], 1):
            text += f"{i}. *{order.order_number}*\n"
            text += f"   👤 {order.client_name}\n"
            text += f"   📦 Контейнеров: {order.container_count}\n"
            text += f"   📍 {order.route}\n"
            text += f"   📝 {order.status}\n\n"
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка при получении заказов: {str(e)[:100]}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 Проверить настройки", callback_data="dbstatus")
            ]])
        )

# Команда /search
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск заказов"""
    if not context.args:
        await update.message.reply_text(
            "🔍 Использование: `/search <текст>`\n\n"
            "Пример: `/search ORD-001`\n"
            "Пример: `/search Company`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    search_text = ' '.join(context.args)
    try:
        orders = db.search_orders(search_text)
        
        if not orders:
            await update.message.reply_text(
                f"🔍 По запросу '{search_text}' ничего не найдено.\n\n"
                "Проверьте:\n"
                "1. Правильность написания\n"
                "2. Есть ли данные в базе\n"
                "3. Настройки синхронизации"
            )
            return
        
        text = f"🔍 *Результаты поиска* ({len(orders)}):\n\n"
        for i, order in enumerate(orders[:5], 1):
            text += f"{i}. *{order.order_number}* - {order.client_name}\n"
            text += f"   📦 {order.container_count} контейнеров\n"
            text += f"   📍 {order.route}\n"
            text += f"   📝 {order.status}\n\n"
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка поиска: {str(e)[:100]}"
        )

# Команда /summary
async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сводная статистика"""
    try:
        stats = db.get_statistics(30)
        
        text = f"""
📊 *Сводная статистика за 30 дней:*

📦 Всего заказов: {stats['total_orders']}
✅ Завершено: {stats['completed_orders']}
🔄 Активных: {stats['active_orders']}
📦 Контейнеров: {stats['total_containers']}
⚖️ Вес: {stats['total_weight']:.0f} кг
📏 Объем: {stats['total_volume']:.1f} м³

*Информация о системе:*
🤖 Бот: Работает
🗄️ База: {'Supabase' if os.getenv('DATABASE_URL') else 'Временная'}
🔄 Синхронизация: {'Настроена' if os.getenv('SYNC_API_KEY') else 'Требует настройки'}

*Для полной функциональности:*
1. Настройте синхронизацию с WPF программой
2. Добавьте API ключ в переменные Railway
"""
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка при получении статистики: {str(e)[:100]}"
        )

# Команда /contacts
async def contacts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Контакты компании"""
    contacts_text = """
🏢 *Margiana Logistic Services*

📞 Телефон: +993 61 55 77 79
📧 Email: perman@margianalogistics.com
📱 Telegram: @margiana_logistics

🌐 *Международная логистика и транспорт:*
• Китай → Туркменистан через Иран
• Морские перевозки
• Таможенное оформление
• Сопровождение грузов

*Техническая поддержка бота:*
Для настройки синхронизации с WPF программой
обратитесь к разработчику.
"""
    
    await update.message.reply_text(
        contacts_text,
        parse_mode=ParseMode.MARKDOWN
    )

# Обработчик callback-запросов
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "active":
        await active_orders_command(update, context)
    elif data == "today":
        await update.message.reply_text("Функция 'События сегодня' скоро будет доступна!")
    elif data == "contacts":
        await contacts_command(update, context)
    elif data == "help":
        await help_command(update, context)
    elif data == "dbstatus":
        await dbstatus_command(update, context)

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Используйте /dbstatus для проверки настроек."
        )

# Основная функция
def main():
    """Запуск бота"""
    logger.info("=" * 50)
    logger.info("🚀 Запуск Logistics Telegram Bot")
    logger.info("=" * 50)
    
    # Выводим информацию о настройках
    logger.info(f"🤖 TELEGRAM_BOT_TOKEN: {'✅ Установлен' if TELEGRAM_BOT_TOKEN else '❌ Отсутствует'}")
    logger.info(f"🗄️ DATABASE_URL: {'✅ Установлен' if os.getenv('DATABASE_URL') else '❌ Отсутствует'}")
    logger.info(f"👑 ADMIN_CHAT_IDS: {os.getenv('ADMIN_CHAT_IDS', 'Не установлены')}")
    
    if not os.getenv('DATABASE_URL'):
        logger.warning("⚠️  DATABASE_URL не установлен. Используется временная база данных.")
        logger.info("Для работы с реальными данными создайте базу на supabase.com")
    
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
    
    # Регистрация обработчика callback-запросов
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Регистрация обработчика ошибок
    application.add_error_handler(error_handler)
    
    # Запуск бота
    logger.info("✅ Бот запущен и готов к работе!")
    logger.info("ℹ️  Используйте /dbstatus для проверки настроек")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
