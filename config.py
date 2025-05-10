"""
Configuration settings for the Mess Management Bot.
"""

# Meal credits to subscription day conversion rate
CREDITS_PER_DAY = 2  # 2 credits (lunch + dinner) = 1 day

# Auto-conversion threshold (minimum credits to trigger automatic conversion)
AUTO_CONVERT_THRESHOLD = 2  # Convert as soon as user has enough for 1 day

# Maximum meal credits a user can accumulate before forced conversion
MAX_CREDITS = 30  # Prevent users from accumulating too many credits

# Time thresholds for marking meals off
LUNCH_CUTOFF_HOUR = 11  # Cannot mark lunch off after 11 AM
DINNER_CUTOFF_HOUR = 17  # Cannot mark dinner off after 5 PM
