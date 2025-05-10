from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import os
from dotenv import load_dotenv
from database import init_database
from handlers import (
    # Conversation states
    MOBILE, OFF_DATE, OFF_MEAL, CANCEL_OFF,
    
    # User handlers
    start, mobile_handler, help_command, status_command,
    
    # Off meal handlers
    offmess, off_date_handler, off_meal_handler, 
    canceloff, cancel_off_handler,
    
    # Admin handlers
    add_user_command, list_users_command, view_offs_command, 
    update_payment_command, broadcast_command, show_database_command,
    update_credits_command, convert_all_credits_command
)

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
            MOBILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, mobile_handler)],
        },
        fallbacks=[],
    )
    
    # Conversation handler for /offmess
    offmess_conv = ConversationHandler(
        entry_points=[CommandHandler('offmess', offmess)],
        states={
            OFF_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, off_date_handler)],
            OFF_MEAL: [CallbackQueryHandler(off_meal_handler)],
        },
        fallbacks=[],
        per_message=False,
    )
    
    # Conversation handler for /canceloff
    canceloff_conv = ConversationHandler(
        entry_points=[CommandHandler('canceloff', canceloff)],
        states={
            CANCEL_OFF: [CallbackQueryHandler(cancel_off_handler)],
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
    application.add_handler(CommandHandler('status', status_command))
    
    # Register admin handlers
    application.add_handler(CommandHandler('listusers', list_users_command))
    application.add_handler(CommandHandler('viewoffs', view_offs_command))
    application.add_handler(CommandHandler('updatepayment', update_payment_command))
    application.add_handler(CommandHandler('updatecredits', update_credits_command))
    application.add_handler(CommandHandler('broadcast', broadcast_command))
    application.add_handler(CommandHandler('showdb', show_database_command))
    application.add_handler(CommandHandler('convertallcredits', convert_all_credits_command))
    
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()