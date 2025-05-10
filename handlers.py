from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from database import check_mobile, update_telegram_id, check_mobile_by_telegram_id, add_user, add_off_request, parse_off_dates, get_user_offs, delete_off_request
from utils import check_thresholds
import pytz
from datetime import datetime, timedelta
import sqlite3
import pandas as pd

#######################
# CONVERSATION STATES #
#######################

# State definitions for conversation handlers
MOBILE = 1
OFF_DATE = 2
OFF_MEAL = 3
CANCEL_OFF = 4

#######################
# USER AUTHENTICATION #
#######################

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
    )
    
    owner_commands = (
        "*Owner Commands:*\n"
        "• /adduser <Name> <Mobile> <Start Date> [Off Dates] - Add a new user\n"
        "  Example: `/adduser John Doe 9876543210 2023-05-01 2023-05-10,2023-05-12 to 2023-05-14`\n"
        "• /listusers - List all registered users\n"
        "• /viewoffs <date> - See all users who are off on a specific date\n"
        "• /updatepayment <username> <days> - Add days to a user's subscription\n"
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
        SELECT name, subscription_start, subscription_end 
        FROM Users 
        WHERE username = ?
    """, (username,))
    user_details = cursor.fetchone()
    
    if not user_details:
        conn.close()
        await update.message.reply_text("Error: User data not found.")
        return
    
    name, sub_start, sub_end = user_details
    
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
        response += f"**Days remaining:** {max(0, days_left)}\n\n"
    else:
        response += "**Subscription:** Not active\n\n"
    
    if off_days:
        response += "**Upcoming Off Days:**\n"
        for date, meal in off_days:
            response += f"• {date}: {meal.capitalize()}\n"
    else:
        response += "**Upcoming Off Days:** None\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")

#####################
# OFF MEAL HANDLERS #
#####################

async def offmess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start conversation for marking meals as off"""
    user = check_mobile_by_telegram_id(str(update.message.from_user.id))
    if not user:
        await update.message.reply_text("You must activate your account with /start first.")
        return ConversationHandler.END
    context.user_data['username'] = user[0]
    await update.message.reply_text("Enter the date for off (YYYY-MM-DD) or 'today'.")
    return OFF_DATE

async def off_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle date input for off meal requests"""
    date_input = update.message.text.strip().lower()
    
    # Check if it's a date range
    if ' to ' in date_input:
        return await _handle_date_range(update, context, date_input)
    else:
        return await _handle_single_date(update, context, date_input)

async def _handle_date_range(update: Update, context: ContextTypes.DEFAULT_TYPE, date_input: str) -> int:
    """Helper function to handle date range input for off meal requests"""
    start_date_str, end_date_str = date_input.split(' to ')
    
    # Validate start date
    start_date, start_lunch_allowed, start_dinner_allowed = check_thresholds(start_date_str)
    if not start_date:
        await update.message.reply_text("Invalid start date. Use YYYY-MM-DD or 'today'.")
        return OFF_DATE
        
    # Validate end date
    try:
        if end_date_str == 'today':
            tz = pytz.timezone('Asia/Kolkata')
            end_date = datetime.now(tz).strftime('%Y-%m-%d')
        else:
            # Validate date format
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
            
        # Make sure end date is not before start date
        if end_date < start_date:
            await update.message.reply_text("End date cannot be before start date.")
            return OFF_DATE
            
    except ValueError:
        await update.message.reply_text("Invalid end date. Use YYYY-MM-DD or 'today'.")
        return OFF_DATE
        
    # Store date range in context
    context.user_data['date_range'] = (start_date, end_date)
    
    # Ask for meal choice
    buttons = []
    if start_lunch_allowed:
        buttons.append([InlineKeyboardButton("Lunch", callback_data='lunch')])
    if start_dinner_allowed:
        buttons.append([InlineKeyboardButton("Dinner", callback_data='dinner')])
    if start_lunch_allowed and start_dinner_allowed:
        buttons.append([InlineKeyboardButton("Both", callback_data='both')])
        
    if not buttons:
        await update.message.reply_text(
            "Too late to off start date's meals (past 11 AM for lunch, 5 PM for dinner).\n"
            "Please try with a different start date."
        )
        return OFF_DATE
        
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        f"Processing date range: {start_date} to {end_date}\n"
        f"Select meal to off for all dates in range:", 
        reply_markup=keyboard
    )
    return OFF_MEAL

async def _handle_single_date(update: Update, context: ContextTypes.DEFAULT_TYPE, date_input: str) -> int:
    """Helper function to handle single date input for off meal requests"""
    target_date, lunch_allowed, dinner_allowed = check_thresholds(date_input)
    if not target_date:
        await update.message.reply_text("Invalid date. Use YYYY-MM-DD or 'today'.")
        return OFF_DATE
    
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
    return OFF_MEAL

async def off_meal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle meal selection for off requests"""
    query = update.callback_query
    await query.answer()
    meal = query.data
    username = context.user_data['username']
    
    # Check if it's a date range request
    if 'date_range' in context.user_data:
        return await _process_date_range_off(query, context, username, meal)
    else:
        # Handle single date
        return await _process_single_date_off(query, context, username, meal)

async def _process_date_range_off(query, context, username, meal):
    """Process off requests for a date range"""
    start_date, end_date = context.user_data['date_range']
    
    # Calculate all dates in the range
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    # Process each date in the range
    success_count = 0
    error_messages = []
    current_date = start
    
    while current_date <= end:
        date_str = current_date.strftime('%Y-%m-%d')
        success, message = add_off_request(username, date_str, meal)
        
        if success:
            success_count += 1
        else:
            error_messages.append(f"{date_str}: {message}")
        
        current_date += timedelta(days=1)
    
    # Prepare response message
    if success_count > 0:
        response = f"✅ Mess off confirmed for {meal} on {success_count} days from {start_date} to {end_date}."
        if error_messages:
            response += "\n\n⚠️ Some dates could not be processed:"
            for error in error_messages[:5]:  # Show at most 5 errors
                response += f"\n• {error}"
            if len(error_messages) > 5:
                response += f"\n• ...and {len(error_messages) - 5} more."
    else:
        response = "❌ Could not process any dates in the range."
        if error_messages:
            response += " Reasons:"
            for error in error_messages[:5]:
                response += f"\n• {error}"
            if len(error_messages) > 5:
                response += f"\n• ...and {len(error_messages) - 5} more."
    
    await query.message.reply_text(response)
    return ConversationHandler.END

async def _process_single_date_off(query, context, username, meal):
    """Process off request for a single date"""
    date = context.user_data['date']
    success, message = add_off_request(username, date, meal)
    if success:
        await query.message.reply_text(f"Mess off confirmed for {meal} on {date}.")
    else:
        await query.message.reply_text(f"Error: {message}")
    return ConversationHandler.END

async def canceloff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start conversation for cancelling off meal requests"""
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
    return CANCEL_OFF

async def cancel_off_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle cancellation of selected off meal request"""
    query = update.callback_query
    await query.answer()
    off_id = int(query.data)
    
    delete_off_request(off_id)
    await query.message.reply_text("Off request cancelled successfully.")
    return ConversationHandler.END

####################
# OWNER ONLY CMDS #
####################

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a new user to the system (owner only)"""
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

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all registered users with their details (owner only)"""
    if str(update.message.from_user.id) != context.bot_data['owner_telegram_id']:
        await update.message.reply_text("Unauthorized: Only the mess owner can use this command.")
        return
    
    conn = sqlite3.connect('mess.db')
    df = pd.read_sql_query("SELECT username, name, mobile, telegram_id, subscription_start, subscription_end FROM Users", conn)
    conn.close()
    
    if df.empty:
        await update.message.reply_text("No users registered yet.")
        return
    
    # Format the data into a readable message
    user_list = "📋 **Registered Users**\n\n"
    for index, row in df.iterrows():
        user_list += f"• **{row['username']}** ({row['name']})\n"
        user_list += f"  - Mobile: {row['mobile']}\n"
        user_list += f"  - Telegram ID: {row['telegram_id'] or 'Not linked'}\n"
        user_list += f"  - Subscription: {row['subscription_start']} to {row['subscription_end']}\n\n"
    
    await update.message.reply_text(user_list, parse_mode="Markdown")

async def view_offs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View all off requests for a specific date (owner only)"""
    if str(update.message.from_user.id) != context.bot_data['owner_telegram_id']:
        await update.message.reply_text("Unauthorized: Only the mess owner can use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Please provide a date. Example: /viewoffs 2023-05-01 or 'today'")
        return
    
    date_str = context.args[0].lower()
    if date_str == 'today':
        tz = pytz.timezone('Asia/Kolkata')
        date = datetime.now(tz).strftime('%Y-%m-%d')
    else:
        try:
            # Validate date format
            date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
        except ValueError:
            await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD or 'today'")
            return
    
    conn = sqlite3.connect('mess.db')
    # Modified SQL query to only show each user once per meal type
    df = pd.read_sql_query("""
        SELECT DISTINCT o.username, u.name, o.meal 
        FROM Off_Requests o 
        JOIN Users u ON o.username = u.username
        WHERE o.date = ?
    """, conn, params=(date,))
    conn.close()
    
    if df.empty:
        await update.message.reply_text(f"No off requests for {date}.")
        return
    
    # Group by meal type
    lunch_offs = df[df['meal'].isin(['lunch', 'both'])]
    dinner_offs = df[df['meal'].isin(['dinner', 'both'])]
    
    # Format the response
    response = f"🗓️ **Off Requests for {date}**\n\n"
    
    if not lunch_offs.empty:
        response += "**🥗 Lunch Offs:**\n"
        for _, row in lunch_offs.iterrows():
            response += f"• {row['name']} ({row['username']})\n"
        response += "\n"
    
    if not dinner_offs.empty:
        response += "**🍲 Dinner Offs:**\n"
        for _, row in dinner_offs.iterrows():
            response += f"• {row['name']} ({row['username']})\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def update_payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Update a user's payment and subscription end date (owner only)"""
    if str(update.message.from_user.id) != context.bot_data['owner_telegram_id']:
        await update.message.reply_text("Unauthorized: Only the mess owner can use this command.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /updatepayment <username> <days>\n"
            "Example: /updatepayment @John1 30"
        )
        return
    
    username = context.args[0]
    try:
        days = int(context.args[1])
        if days <= 0:
            await update.message.reply_text("Days must be a positive number.")
            return
    except ValueError:
        await update.message.reply_text("Days must be a valid number.")
        return
    
    # Check if user exists
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    cursor.execute("SELECT subscription_end FROM Users WHERE username = ?", (username,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        await update.message.reply_text(f"User {username} not found.")
        return
    
    # Update subscription dates
    current_end = user[0]
    if current_end:
        new_end_date = (datetime.strptime(current_end, '%Y-%m-%d') + timedelta(days=days)).strftime('%Y-%m-%d')
    else:
        # If no end date set, use today as starting point
        new_end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    
    payment_date = datetime.now().strftime('%Y-%m-%d')
    
    # Update user's subscription
    cursor.execute("UPDATE Users SET subscription_end = ? WHERE username = ?", (new_end_date, username))
    
    # Record the payment
    cursor.execute(
        "INSERT INTO Payments (username, payment_date, days_added) VALUES (?, ?, ?)",
        (username, payment_date, days)
    )
    
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ Payment recorded for {username}:\n"
        f"• {days} days added\n"
        f"• New subscription end date: {new_end_date}"
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a broadcast message to all users with telegram_id (owner only)"""
    if str(update.message.from_user.id) != context.bot_data['owner_telegram_id']:
        await update.message.reply_text("Unauthorized: Only the mess owner can use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Please provide a message to broadcast.")
        return
    
    message = ' '.join(context.args)
    
    # Get all users with telegram_id
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM Users WHERE telegram_id IS NOT NULL AND telegram_id != ''")
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text("No users with Telegram accounts found.")
        return
    
    # Send the message to each user
    sent_count = 0
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=f"📢 **Announcement from Mess Owner:**\n\n{message}",
                parse_mode="Markdown"
            )
            sent_count += 1
        except Exception as e:
            continue
    
    await update.message.reply_text(f"Message broadcast to {sent_count} users.")

async def show_database_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show database contents for debugging (owner only)"""
    if str(update.message.from_user.id) != context.bot_data['owner_telegram_id']:
        await update.message.reply_text("Unauthorized: Only the mess owner can use this command.")
        return
    
    if not context.args or context.args[0].lower() not in ['users', 'offs', 'payments']:
        await update.message.reply_text(
            "Please specify which table to show:\n"
            "/showdb users - Show all users\n"
            "/showdb offs - Show all off requests\n"
            "/showdb payments - Show all payments"
        )
        return
    
    table = context.args[0].lower()
    conn = sqlite3.connect('mess.db')
    
    if table == 'users':
        df = pd.read_sql_query("SELECT * FROM Users", conn)
        title = "👥 **Users Table**"
    elif table == 'offs':
        df = pd.read_sql_query("SELECT * FROM Off_Requests ORDER BY date DESC", conn)
        title = "📅 **Off Requests Table**"
    elif table == 'payments':
        df = pd.read_sql_query("SELECT * FROM Payments ORDER BY payment_date DESC", conn)
        title = "💰 **Payments Table**"
    
    conn.close()
    
    if df.empty:
        await update.message.reply_text(f"No data in {table} table.")
        return
    
    # Convert DataFrame to readable format
    result = f"{title}\n\n```\n"
    result += df.to_string(index=False)
    result += "\n```"
    
    # If the message is too long, split it
    if len(result) > 4000:
        await update.message.reply_text("Data too large to display in a message. Sending as chunks...")
        chunks = [result[i:i+4000] for i in range(0, len(result), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode="Markdown")
    else:
        await update.message.reply_text(result, parse_mode="Markdown")