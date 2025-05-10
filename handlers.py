from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import check_mobile, update_telegram_id, check_mobile_by_telegram_id, add_user, add_off_request, parse_off_dates, get_user_offs, delete_off_request
from utils import check_thresholds
import pytz
from datetime import datetime

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Please enter your mobile number to activate your account.")
    return 1  # MOBILE

async def mobile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    mobile = update.message.text.strip()
    if not mobile.isdigit() or len(mobile) != 10:
        await update.message.reply_text("Please enter a valid 10-digit mobile number.")
        return 1
    user = check_mobile(mobile)
    if user:
        username, name, telegram_id = user
        if telegram_id:
            await update.message.reply_text(f"You are already registered as {username} ({name}).")
        else:
            update_telegram_id(mobile, str(update.message.from_user.id))
            await update.message.reply_text(f"Welcome, {username} ({name})! Use /help for commands.")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Mobile number not found. Contact the mess owner to be added.")
        return ConversationHandler.END

async def offmess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = check_mobile_by_telegram_id(str(update.message.from_user.id))
    if not user:
        await update.message.reply_text("You must activate your account with /start first.")
        return ConversationHandler.END
    context.user_data['username'] = user[0]
    await update.message.reply_text("Enter the date for off (YYYY-MM-DD) or 'today'.")
    return 2  # OFF_DATE

async def off_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    date_str = update.message.text.strip().lower()
    target_date, lunch_allowed, dinner_allowed = check_thresholds(date_str)
    if not target_date:
        await update.message.reply_text("Invalid date. Use YYYY-MM-DD or 'today'.")
        return 2  # OFF_DATE
    
    context.user_data['date'] = target_date
    buttons = []
    if lunch_allowed:
        buttons.append([InlineKeyboardButton("Lunch", callback_data='lunch')])
    if dinner_allowed:
        buttons.append([InlineKeyboardButton("Dinner", callback_data='dinner')])
    if lunch_allowed and dinner_allowed:
        buttons.append([InlineKeyboardButton("Both", callback_data='both')])
    
    if not buttons:
        await update.message.reply_text("Too late to off this date's meals (past 11 AM for lunch, 5 PM for dinner).")
        return ConversationHandler.END
    
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Select meal to off:", reply_markup=keyboard)
    return 3  # OFF_MEAL

async def off_meal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    meal = query.data
    username = context.user_data['username']
    date = context.user_data['date']
    
    if add_off_request(username, date, meal):
        await query.message.reply_text(f"Mess off confirmed for {meal} on {date}.")
    else:
        await query.message.reply_text("Error saving off request.")
    
    return ConversationHandler.END

async def canceloff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = check_mobile_by_telegram_id(str(update.message.from_user.id))
    if not user:
        await update.message.reply_text("You must activate your account with /start first.")
        return ConversationHandler.END
    
    username = user[0]
    offs = get_user_offs(username)
    if not offs:
        await update.message.reply_text("You have no active off requests.")
        return ConversationHandler.END
    
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    current_hour = now.hour
    buttons = []
    for off_id, date, meal in offs:
        off_date = datetime.strptime(date, '%Y-%m-%d')
        if off_date.date() > now.date() or (
            off_date.date() == now.date() and (
                (meal in ['lunch', 'both'] and current_hour < 11) or
                (meal in ['dinner', 'both'] and current_hour < 17)
            )
        ):
            buttons.append([InlineKeyboardButton(f"{date} {meal}", callback_data=str(off_id))])
    
    if not buttons:
        await update.message.reply_text("No off requests can be cancelled (past thresholds: 11 AM lunch, 5 PM dinner).")
        return ConversationHandler.END
    
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Select off request to cancel:", reply_markup=keyboard)
    return 4  # CANCEL_OFF

async def cancel_off_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    off_id = int(query.data)
    
    delete_off_request(off_id)
    await query.message.reply_text("Off request cancelled successfully.")
    return ConversationHandler.END

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.message.from_user.id) != context.bot_data['owner_telegram_id']:
        await update.message.reply_text("Unauthorized: Only the mess owner can add users.")
        return
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text(
                "Usage: /adduser <Name> <Mobile> <Payment Start Date> [Off Dates]\n"
                "Example: /adduser John Doe 9876543210 2025-05-01 2025-05-10,2025-05-12 to 2025-05-14"
            )
            return
        name = ' '.join(args[:-2])
        mobile = args[-2]
        subscription_start = args[-1]
        subscription_end = subscription_start
        off_dates_str = ' '.join(args[3:]) if len(args) > 3 else ''
        off_dates = parse_off_dates(off_dates_str)
        
        username = add_user(name, mobile, subscription_start, subscription_end, off_dates)
        if username:
            off_msg = f" with off dates: {off_dates_str}" if off_dates else ""
            await update.message.reply_text(f"User added: {username} ({name}, {mobile}){off_msg}")
        else:
            await update.message.reply_text("Error: Mobile number already exists.")
    except Exception as e:
        await update.message.reply_text(
            f"Error: {str(e)}. Usage: /adduser <Name> <Mobile> <YYYY-MM-DD> [Off Dates]"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_owner = str(update.message.from_user.id) == context.bot_data.get('owner_telegram_id', '')
    
    user_commands = (
        "🍽️ **Mess Management Bot Help** 🍽️\n\n"
        "**User Commands:**\n"
        "• `/start` - Activate your account with your mobile number\n"
        "• `/offmess` - Request to skip meals on specific dates\n"
        "• `/canceloff` - Cancel a previously requested meal off\n"
        "• `/help` - Show this message\n\n"
    )
    
    owner_commands = (
        "**Owner Commands:**\n"
        "• `/adduser <Name> <Mobile> <Start Date> [Off Dates]` - Add a new user\n"
        "  Example: `/adduser John Doe 9876543210 2023-05-01 2023-05-10,2023-05-12 to 2023-05-14`\n\n"
    )
    
    coming_soon = "**Coming Soon:**\n• User status tracking\n• Attendance reporting\n• Payment management"
    
    help_text = user_commands + (owner_commands if is_owner else "") + coming_soon
    
    await update.message.reply_text(help_text, parse_mode="Markdown")