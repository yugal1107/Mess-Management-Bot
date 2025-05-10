# Mess Management Bot

A Telegram bot for managing meal subscriptions and day-offs for mess/cafeteria services.

## Features

### For Users

- Account activation with mobile number
- Request meals off on specific dates or date ranges
- Earn meal credits for skipped meals
- Cancel upcoming meal off requests
- View subscription status and upcoming off dates
- Automatic conversion of meal credits to subscription days

### For Mess Owners/Admins

- Add new users and manage subscriptions
- View off requests for specific dates
- Update user payments and extend subscriptions
- Manage meal credits for users
- Send broadcast messages to all users
- View database contents for debugging

## System Requirements

- Python 3.12+
- Required Python packages (see `pyproject.toml`)
- SQLite3 for database storage
- Telegram Bot API token

## Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd mess-management
   ```

2. Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -e .
   ```

4. Create a `.env` file with your Telegram bot token and owner ID:
   ```
   BOT_TOKEN=your-bot-token-here
   OWNER_TELEGRAM_ID=your-telegram-id
   ```

## Configuration

The bot's behavior can be customized through the `config.py` file:

- `CREDITS_PER_DAY`: Number of meal credits that convert to one day of subscription (default: 2)
- `AUTO_CONVERT_THRESHOLD`: Minimum credits before automatic conversion (default: 2)
- `MAX_CREDITS`: Maximum meal credits before forced conversion (default: 30)
- `LUNCH_CUTOFF_HOUR`: Time after which lunch cannot be marked off (default: 11)
- `DINNER_CUTOFF_HOUR`: Time after which dinner cannot be marked off (default: 17)

## Usage

### Starting the Bot

```bash
python bot.py
```

### User Commands

- `/start` - Activate your account with your mobile number
- `/offmess` - Request to skip meals on specific dates
- `/canceloff` - Cancel a previously requested meal off
- `/status` - View your subscription status and upcoming offs
- `/help` - Show help message

### Owner/Admin Commands

- `/adduser <Name> <Mobile> <Start Date> [Off Dates]` - Add a new user
- `/listusers` - List all registered users
- `/viewoffs <date>` - See all users who are off on a specific date
- `/updatepayment <username> <days>` - Add days to a user's subscription
- `/updatecredits <username> <credits>` - Manually adjust user's meal credits
- `/convertallcredits` - Convert all users' credits to subscription days
- `/broadcast <message>` - Send a message to all registered users
- `/showdb <table>` - Show database tables (users, offs, payments)

## Project Structure

```
mess-management/
├── bot.py                # Main application entry point
├── database.py           # Database operations
├── config.py             # Configuration settings
├── utils.py              # Utility functions
├── handlers/             # Command handlers organized by function
│   ├── __init__.py       # Handler exports
│   ├── admin_handlers.py # Admin-only commands
│   ├── user_handlers.py  # User authentication and commands
│   └── off_meal_handlers.py # Meal off request handling
├── README.md             # This documentation
├── .env                  # Environment variables (not in git)
└── pyproject.toml        # Project dependencies
```

## Meal Credit System

- Each lunch or dinner off earns 1 credit (2 credits for both meals)
- Credits are automatically converted to subscription days based on the configured ratio
- Conversion happens when the user's credits exceed the auto-convert threshold
- Credits can also be manually converted by the mess owner

## Database Schema

The bot uses SQLite with the following tables:

### Users

- `username` (TEXT): Unique username
- `name` (TEXT): User's full name
- `mobile` (TEXT): User's mobile number
- `telegram_id` (TEXT): User's Telegram ID
- `subscription_start` (DATE): Subscription start date
- `subscription_end` (DATE): Subscription end date
- `meal_credits` (INTEGER): Current meal credits

### Off_Requests

- `id` (INTEGER): Unique ID
- `username` (TEXT): Associated user
- `date` (DATE): Date of the off request
- `meal` (TEXT): Meal type (lunch, dinner, both)

### Payments

- `id` (INTEGER): Unique ID
- `username` (TEXT): Associated user
- `payment_date` (DATE): Date of payment
- `days_added` (INTEGER): Number of days added to subscription

## License

This project is licensed under the MIT License - see the LICENSE file for details.
