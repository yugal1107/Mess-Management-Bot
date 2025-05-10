"""
Handlers for managing meal off requests in the Mess Management Bot.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import check_mobile_by_telegram_id, add_off_request, get_user_offs, delete_off_request
from utils import check_thresholds
import pytz
from datetime import datetime, timedelta
from . import OFF_DATE, OFF_MEAL, CANCEL_OFF

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
    
    # The delete_off_request function now handles deducting meal credits
    delete_off_request(off_id)
    await query.message.reply_text("Off request cancelled successfully.")
    return ConversationHandler.END
