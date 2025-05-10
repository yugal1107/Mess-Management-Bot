"""
User authentication and basic user commands for the Mess Management Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import check_mobile, update_telegram_id, check_mobile_by_telegram_id
import sqlite3
from datetime import datetime
from . import MOBILE
from config import CREDITS_PER_DAY  # Import the configuration variable

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start conversation and request mobile number for registration"""
    await update.message.reply_text("Please enter your mobile number to activate your account.")
    return MOBILE

async def mobile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle mobile number verification and user registration"""
    mobile = update.message.text.strip()
    if not mobile.isdigit() or len(mobile) != 10:
        await update.message.reply_text("Please enter a valid 10-digit mobile number.")
        return MOBILE
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message with available commands based on user role"""
    is_owner = str(update.message.from_user.id) == context.bot_data.get('owner_telegram_id', '')
    
    user_commands = (
        "🍽️ *Mess Management Bot Help* 🍽️\n\n"
        "*User Commands:*\n"
        "• /start - Activate your account with your mobile number\n"
        "• /offmess - Request to skip meals on specific dates\n"
        "• /canceloff - Cancel a previously requested meal off\n"
        "• /status - View your subscription status and upcoming offs\n"
        "• /help - Show this message\n\n"
        "*About Meal Credits:*\n"
        f"• Each lunch or dinner off earns 1 credit\n"
        f"• Every {CREDITS_PER_DAY} credits are automatically converted to 1 day of subscription\n\n"
    )
    
    owner_commands = (
        "*Owner Commands:*\n"
        "• /adduser <Name> <Mobile> <Start Date> [Off Dates] - Add a new user\n"
        "• /listusers - List all registered users\n"
        "• /viewoffs <date> - See all users who are off on a specific date\n"
        "• /updatepayment <username> <days> - Add days to a user's subscription\n"
        "• /updatecredits <username> <credits> - Manually adjust user's meal credits\n"
        "• /convertallcredits - Convert all users' credits to subscription days\n"
        "• /broadcast <message> - Send a message to all registered users\n"
        "• /showdb <table> - Show database tables (users, offs, payments)\n\n"
    )
    
    coming_soon = "*Coming Soon:*\n• User status tracking\n• Attendance reporting"
    
    help_text = user_commands + (owner_commands if is_owner else "") + coming_soon
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's current status including subscription and active off days"""
    user = check_mobile_by_telegram_id(str(update.message.from_user.id))
    if not user:
        await update.message.reply_text("You must activate your account with /start first.")
        return
    
    username = user[0]
    
    # Get user details
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, subscription_start, subscription_end, meal_credits 
        FROM Users 
        WHERE username = ?
    """, (username,))
    user_details = cursor.fetchone()
    
    if not user_details:
        conn.close()
        await update.message.reply_text("Error: User data not found.")
        return
    
    name, sub_start, sub_end, meal_credits = user_details
    
    # Get active off days
    cursor.execute("""
        SELECT date, meal 
        FROM Off_Requests 
        WHERE username = ? AND date >= date('now') 
        ORDER BY date
    """, (username,))
    off_days = cursor.fetchall()
    conn.close()
    
    # Format subscription info
    today = datetime.now().date()
    sub_end_date = datetime.strptime(sub_end, '%Y-%m-%d').date() if sub_end else None
    days_left = (sub_end_date - today).days if sub_end_date else 0
    
    # Create response message
    response = f"📊 **Status for {name}** (@{username})\n\n"
    
    if sub_start and sub_end:
        subscription_status = "Active ✅" if days_left > 0 else "Expired ❌"
        response += f"**Subscription:** {subscription_status}\n"
        response += f"**Period:** {sub_start} to {sub_end}\n"
        response += f"**Days remaining:** {max(0, days_left)}\n"
        response += f"**Meal credits:** {meal_credits}\n\n"
    else:
        response += "**Subscription:** Not active\n\n"
    
    if off_days:
        response += "**Upcoming Off Days:**\n"
        for date, meal in off_days:
            response += f"• {date}: {meal.capitalize()}\n"
    else:
        response += "**Upcoming Off Days:** None\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")
