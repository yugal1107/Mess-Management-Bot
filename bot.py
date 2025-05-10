from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import os
from dotenv import load_dotenv
from database import init_database
from handlers import start, mobile_handler, offmess, off_date_handler, off_meal_handler, canceloff, cancel_off_handler, add_user_command, help_command

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_TELEGRAM_ID = os.getenv('OWNER_TELEGRAM_ID')

def main():
    init_database()
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Store owner Telegram ID
    application.bot_data['owner_telegram_id'] = OWNER_TELEGRAM_ID
    
    # Conversation handler for /start
    start_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, mobile_handler)],  # MOBILE
        },
        fallbacks=[],
    )
    
    # Conversation handler for /offmess
    offmess_conv = ConversationHandler(
        entry_points=[CommandHandler('offmess', offmess)],
        states={
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, off_date_handler)],  # OFF_DATE
            3: [CallbackQueryHandler(off_meal_handler)],  # OFF_MEAL
        },
        fallbacks=[],
        per_message=False,
    )
    
    # Conversation handler for /canceloff
    canceloff_conv = ConversationHandler(
        entry_points=[CommandHandler('canceloff', canceloff)],
        states={
            4: [CallbackQueryHandler(cancel_off_handler)],  # CANCEL_OFF
        },
        fallbacks=[],
        per_message=False,
    )
    
    # Register handlers
    application.add_handler(start_conv)
    application.add_handler(offmess_conv)
    application.add_handler(canceloff_conv)
    application.add_handler(CommandHandler('adduser', add_user_command))
    application.add_handler(CommandHandler('help', help_command))
    
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()