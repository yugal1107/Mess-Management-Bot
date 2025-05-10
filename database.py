import sqlite3
from datetime import datetime, timedelta
from config import CREDITS_PER_DAY, AUTO_CONVERT_THRESHOLD, MAX_CREDITS

def init_database():
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            username TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            mobile TEXT UNIQUE NOT NULL,
            telegram_id TEXT UNIQUE,
            subscription_start DATE,
            subscription_end DATE,
            meal_credits INTEGER DEFAULT 0
        )
    ''')
    
    # Check if meal_credits column exists, add if it doesn't
    cursor.execute("PRAGMA table_info(Users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'meal_credits' not in columns:
        cursor.execute("ALTER TABLE Users ADD COLUMN meal_credits INTEGER DEFAULT 0")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Off_Requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            date DATE NOT NULL,
            meal TEXT NOT NULL,
            FOREIGN KEY (username) REFERENCES Users(username)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            payment_date DATE NOT NULL,
            days_added INTEGER NOT NULL,
            FOREIGN KEY (username) REFERENCES Users(username)
        )
    ''')
    conn.commit()
    conn.close()

def add_user(name, mobile, subscription_start, subscription_end, off_dates=None):
    """Add a user and optional off dates."""
    first_name = name.split()[0]
    cursor = sqlite3.connect('mess.db').cursor()
    cursor.execute('SELECT COUNT(*) FROM Users WHERE username LIKE ?', (f'@%{first_name}%',))
    count = cursor.fetchone()[0]
    username = f'@{first_name}{count + 1}'
    
    try:
        cursor.execute('''
            INSERT INTO Users (username, name, mobile, subscription_start, subscription_end, meal_credits)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (username, name, mobile, subscription_start, subscription_end))
        
        if off_dates:
            for date, meal in off_dates:
                cursor.execute('''
                    INSERT INTO Off_Requests (username, date, meal)
                    VALUES (?, ?, ?)
                ''', (username, date, meal))
                
                # Add meal credits for initial off dates
                meal_credit = 2 if meal == 'both' else 1
                cursor.execute('''
                    UPDATE Users SET meal_credits = meal_credits + ?
                    WHERE username = ?
                ''', (meal_credit, username))
        
        cursor.connection.commit()
        return username
    except sqlite3.IntegrityError:
        cursor.connection.close()
        return None
    finally:
        cursor.connection.close()

def check_mobile(mobile):
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username, name, telegram_id FROM Users WHERE mobile = ?', (mobile,))
    user = cursor.fetchone()
    conn.close()
    return user

def check_mobile_by_telegram_id(telegram_id):
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username, name, telegram_id FROM Users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_telegram_id(mobile, telegram_id):
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE Users SET telegram_id = ? WHERE mobile = ?', (telegram_id, mobile))
    conn.commit()
    conn.close()

def add_off_request(username, date, meal):
    """Add an off request for a user's meal"""
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    
    # Check if the user already has this meal off on this date
    cursor.execute(
        "SELECT id FROM Off_Requests WHERE username = ? AND date = ? AND (meal = ? OR meal = 'both')",
        (username, date, meal)
    )
    existing = cursor.fetchone()
    
    if existing:
        conn.close()
        return False, "You already have this meal marked as off for this date."
    
    # If user has one meal off and is requesting both, update existing record
    credits_to_add = 0
    if meal == 'both':
        cursor.execute(
            "SELECT id, meal FROM Off_Requests WHERE username = ? AND date = ?",
            (username, date)
        )
        existing_meal = cursor.fetchone()
        if existing_meal:
            # Only add 1 more credit since they already have 1 meal off
            credits_to_add = 1
            # Delete the existing record as we'll create a new 'both' record
            cursor.execute("DELETE FROM Off_Requests WHERE id = ?", (existing_meal[0],))
        else:
            credits_to_add = 2  # Both meals = 2 credits
    else:
        credits_to_add = 1  # Single meal = 1 credit
    
    # Add the off request
    cursor.execute(
        "INSERT INTO Off_Requests (username, date, meal) VALUES (?, ?, ?)",
        (username, date, meal)
    )
    
    # Add meal credits
    cursor.execute(
        "UPDATE Users SET meal_credits = meal_credits + ? WHERE username = ?",
        (credits_to_add, username)
    )
    
    # After adding credits, check if we should auto-convert to subscription days
    auto_convert_credits_to_days(cursor, username)
    
    conn.commit()
    conn.close()
    return True, "Meal off request added successfully."

def get_user_offs(username):
    """Fetch all off requests for a user."""
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, date, meal FROM Off_Requests WHERE username = ?', (username,))
    offs = cursor.fetchall()
    conn.close()
    return offs

def delete_off_request(off_id):
    """Delete an off request by ID."""
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    
    # First get the meal type so we know how many credits to remove
    cursor.execute("SELECT username, meal FROM Off_Requests WHERE id = ?", (off_id,))
    result = cursor.fetchone()
    if result:
        username, meal = result
        credits_to_deduct = 2 if meal == 'both' else 1
        
        # Deduct the credits
        cursor.execute(
            "UPDATE Users SET meal_credits = MAX(0, meal_credits - ?) WHERE username = ?",
            (credits_to_deduct, username)
        )
    
    # Delete the off request
    cursor.execute('DELETE FROM Off_Requests WHERE id = ?', (off_id,))
    conn.commit()
    conn.close()

def parse_off_dates(off_dates_str):
    """Parse off dates (single or range) and return list of (date, meal)."""
    if not off_dates_str:
        return []
    result = []
    parts = off_dates_str.split(',')
    for part in parts:
        part = part.strip()
        if ' to ' in part:
            start_date, end_date = part.split(' to ')
            try:
                start = datetime.strptime(start_date.strip(), '%Y-%m-%d')
                end = datetime.strptime(end_date.strip(), '%Y-%m-%d')
                while start <= end:
                    result.append((start.strftime('%Y-%m-%d'), 'both'))
                    start += timedelta(days=1)
            except ValueError:
                continue
        else:
            try:
                datetime.strptime(part, '%Y-%m-%d')
                result.append((part, 'both'))
            except ValueError:
                continue
    return result

def auto_convert_credits_to_days(cursor, username):
    """Automatically convert meal credits to subscription days when threshold is reached"""
    # Get current credits
    cursor.execute("SELECT meal_credits, subscription_end FROM Users WHERE username = ?", (username,))
    result = cursor.fetchone()
    if not result:
        return
    
    meal_credits, subscription_end = result
    
    # Only convert if credits are above threshold and enough for at least one day
    if meal_credits < AUTO_CONVERT_THRESHOLD or meal_credits < CREDITS_PER_DAY:
        return
    
    # If user has more than MAX_CREDITS, force convert all possible days
    if meal_credits > MAX_CREDITS:
        days_to_add = meal_credits // CREDITS_PER_DAY
    else:
        # Otherwise, convert just enough to get below threshold
        excess_credits = meal_credits - (AUTO_CONVERT_THRESHOLD - 1)
        days_to_add = excess_credits // CREDITS_PER_DAY
    
    # Ensure we're adding at least one day
    days_to_add = max(1, days_to_add)
    
    # Calculate credits to deduct
    credits_to_deduct = days_to_add * CREDITS_PER_DAY
    
    # Calculate new subscription end date
    if subscription_end:
        new_end_date = (datetime.strptime(subscription_end, '%Y-%m-%d') + 
                        timedelta(days=days_to_add)).strftime('%Y-%m-%d')
    else:
        new_end_date = (datetime.now() + timedelta(days=days_to_add)).strftime('%Y-%m-%d')
    
    # Update user's subscription end date and deduct used credits
    cursor.execute(
        "UPDATE Users SET subscription_end = ?, meal_credits = meal_credits - ? WHERE username = ?",
        (new_end_date, credits_to_deduct, username)
    )
    
    # Record this automatic payment
    cursor.execute(
        "INSERT INTO Payments (username, payment_date, days_added) VALUES (?, ?, ?)",
        (username, datetime.now().strftime('%Y-%m-%d'), days_to_add)
    )