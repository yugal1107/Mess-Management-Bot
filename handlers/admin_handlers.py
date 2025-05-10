"""
Admin-only handlers for the Mess Management Bot.
These commands are restricted to the mess owner.
"""

from telegram import Update
from telegram.ext import ContextTypes
from database import add_user, parse_off_dates, auto_convert_credits_to_days
import pytz
from datetime import datetime, timedelta
import sqlite3
import pandas as pd
from config import CREDITS_PER_DAY, AUTO_CONVERT_THRESHOLD, MAX_CREDITS

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
        
        # Extract mobile number (second last argument)
        mobile = args[-2]
        
        # Extract subscription start date (last argument)
        subscription_start = args[-1]
        subscription_end = subscription_start
        
        # Name is all arguments except the last two (mobile and start date)
        name = ' '.join(args[:-2])
        
        # Only process off dates if we have more than 3 arguments
        # (name could be multiple words, so we check total argument count)
        if len(args) > 3:
            # Off dates are any arguments after the name, mobile, and start date
            # Calculate how many words are in the name
            name_word_count = len(name.split())
            
            # Off dates start after name + mobile + start date
            off_dates_start_index = name_word_count + 2
            
            if off_dates_start_index < len(args):
                off_dates_str = ' '.join(args[off_dates_start_index:])
                off_dates = parse_off_dates(off_dates_str)
            else:
                off_dates_str = ""
                off_dates = []
        else:
            off_dates_str = ""
            off_dates = []
        
        username = add_user(name, mobile, subscription_start, subscription_end, off_dates)
        if username:
            # Only show "with off dates" if we actually have off dates
            off_msg = f" with off dates: {off_dates_str}" if off_dates_str else ""
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
    # Remove @ symbol if present, as usernames in the database might not include it
    if username.startswith('@'):
        username_clean = username
    else:
        username_clean = f"@{username}"
    
    try:
        days = int(context.args[1])
        if days <= 0:
            await update.message.reply_text("Days must be a positive number.")
            return
    except ValueError:
        await update.message.reply_text("Days must be a valid number.")
        return
    
    # Check if user exists - try both with and without @ prefix
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, subscription_end, meal_credits FROM Users WHERE username = ? OR username = ?", 
                 (username, username_clean))
    user = cursor.fetchone()
    
    if not user:
        # If still not found, try searching by partial username
        cursor.execute("SELECT username, subscription_end, meal_credits FROM Users WHERE username LIKE ?",
                     (f"%{username.replace('@', '')}%",))
        user = cursor.fetchone()
    
    if not user:
        conn.close()
        await update.message.reply_text(f"User {username} not found. Please check the username and try again.")
        return
    
    # Get the actual username from the database
    actual_username, current_end, meal_credits = user
    
    # Update subscription dates
    if current_end:
        new_end_date = (datetime.strptime(current_end, '%Y-%m-%d') + timedelta(days=days)).strftime('%Y-%m-%d')
    else:
        # If no end date set, use today as starting point
        new_end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    
    payment_date = datetime.now().strftime('%Y-%m-%d')
    
    # Update user's subscription using the actual username from the database
    cursor.execute("UPDATE Users SET subscription_end = ? WHERE username = ?", (new_end_date, actual_username))
    
    # Record the payment
    cursor.execute(
        "INSERT INTO Payments (username, payment_date, days_added) VALUES (?, ?, ?)",
        (actual_username, payment_date, days)
    )
    
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ Payment recorded for {actual_username}:\n"
        f"• {days} days added\n"
        f"• New subscription end date: {new_end_date}\n"
        f"• Current meal credits: {meal_credits}"
    )

async def update_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Update a user's meal credits (owner only)"""
    if str(update.message.from_user.id) != context.bot_data['owner_telegram_id']:
        await update.message.reply_text("Unauthorized: Only the mess owner can use this command.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /updatecredits <username> <credits>\n"
            "Example: /updatecredits @John1 5\n"
            "Note: Use positive number to add credits, negative to deduct"
        )
        return
    
    username = context.args[0]
    try:
        credits = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Credits must be a valid number.")
        return
    
    # Check if user exists
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    cursor.execute("SELECT meal_credits FROM Users WHERE username = ?", (username,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        await update.message.reply_text(f"User {username} not found.")
        return
    
    current_credits = user[0] or 0
    new_credits = max(0, current_credits + credits)
    
    # Update user's meal credits
    cursor.execute("UPDATE Users SET meal_credits = ? WHERE username = ?", (new_credits, username))
    conn.commit()
    conn.close()
    
    action = "added to" if credits > 0 else "deducted from"
    await update.message.reply_text(
        f"✅ Meal credits updated for {username}:\n"
        f"• {abs(credits)} credits {action} account\n"
        f"• New meal credits balance: {new_credits}"
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

async def convert_all_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Convert all users' meal credits to subscription days (owner only)"""
    if str(update.message.from_user.id) != context.bot_data['owner_telegram_id']:
        await update.message.reply_text("Unauthorized: Only the mess owner can use this command.")
        return
    
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    
    # Get all users with meal credits
    cursor.execute("SELECT username FROM Users WHERE meal_credits >= ?", (CREDITS_PER_DAY,))
    users = [row[0] for row in cursor.fetchall()]
    
    if not users:
        await update.message.reply_text("No users with enough meal credits to convert.")
        conn.close()
        return
    
    # Process each user
    conversions = []
    for username in users:
        # Save current state
        cursor.execute("SELECT meal_credits, subscription_end FROM Users WHERE username = ?", (username,))
        old_credits, old_end = cursor.fetchone()
        
        # Convert credits
        auto_convert_credits_to_days(cursor, username)
        
        # Get new state
        cursor.execute("SELECT meal_credits, subscription_end FROM Users WHERE username = ?", (username,))
        new_credits, new_end = cursor.fetchone()
        
        # Calculate days added
        days_added = (datetime.strptime(new_end, '%Y-%m-%d') - 
                     datetime.strptime(old_end, '%Y-%m-%d')).days if old_end and new_end else 0
        
        if days_added > 0:
            conversions.append({
                'username': username,
                'credits_used': old_credits - new_credits,
                'days_added': days_added,
                'new_end': new_end
            })
    
    conn.commit()
    conn.close()
    
    if not conversions:
        await update.message.reply_text("No credits were converted.")
        return
    
    # Prepare response message
    response = "✅ **Credits converted to subscription days:**\n\n"
    for c in conversions:
        response += f"• **{c['username']}**: {c['credits_used']} credits → {c['days_added']} days\n"
        response += f"  New end date: {c['new_end']}\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")
