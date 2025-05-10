"""
Handlers module for Mess Management Bot.
Contains all the command handlers and conversation flows.
"""

# Define conversation state constants
MOBILE = 1
OFF_DATE = 2
OFF_MEAL = 3
CANCEL_OFF = 4

# Import all handlers to make them available when importing from the package
from .user_handlers import start, mobile_handler, help_command, status_command
from .off_meal_handlers import (
    offmess, off_date_handler, off_meal_handler, 
    canceloff, cancel_off_handler
)
from .admin_handlers import (
    add_user_command, list_users_command, view_offs_command,
    update_payment_command, broadcast_command, show_database_command,
    update_credits_command, convert_all_credits_command
)

# Export all handlers
__all__ = [
    # Conversation states
    'MOBILE', 'OFF_DATE', 'OFF_MEAL', 'CANCEL_OFF',
    
    # User handlers
    'start', 'mobile_handler', 'help_command', 'status_command',
    
    # Off meal handlers
    'offmess', 'off_date_handler', 'off_meal_handler', 
    'canceloff', 'cancel_off_handler',
    
    # Admin handlers
    'add_user_command', 'list_users_command', 'view_offs_command',
    'update_payment_command', 'broadcast_command', 'show_database_command',
    'update_credits_command', 'convert_all_credits_command'
]
