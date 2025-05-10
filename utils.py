from datetime import datetime, timedelta
import pytz

def check_thresholds(date_str):
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    if date_str.lower() == 'today':
        target_date = now.strftime('%Y-%m-%d')
    else:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
        except ValueError:
            return None, False, False
    current_hour = now.hour
    is_same_day = target_date == now.strftime('%Y-%m-%d')
    lunch_allowed = not is_same_day or current_hour < 11
    dinner_allowed = not is_same_day or current_hour < 17
    return target_date, lunch_allowed, dinner_allowed