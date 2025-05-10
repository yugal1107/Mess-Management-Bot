import sqlite3
from datetime import datetime, timedelta

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
            subscription_end DATE
        )
    ''')
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
            INSERT INTO Users (username, name, mobile, subscription_start, subscription_end)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, name, mobile, subscription_start, subscription_end))
        
        if off_dates:
            for date, meal in off_dates:
                cursor.execute('''
                    INSERT INTO Off_Requests (username, date, meal)
                    VALUES (?, ?, ?)
                ''', (username, date, meal))
        
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
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO Off_Requests (username, date, meal)
            VALUES (?, ?, ?)
        ''', (username, date, meal))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

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