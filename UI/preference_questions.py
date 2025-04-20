"""
Preference questions for the scheduling system.
These questions help the LLM generate a more personalized schedule.
"""

# Define preference questions with their types and options
PREFERENCE_QUESTIONS = [
    {
        "id": "wake_time",
        "question": "What time do you usually wake up?",
        "type": "time",
        "default": "07:00",
        "help_text": "This helps us schedule early morning activities appropriately."
    },
    {
        "id": "sleep_time",
        "question": "What time do you usually go to sleep?",
        "type": "time",
        "default": "23:00",
        "help_text": "We'll avoid scheduling tasks too close to your bedtime."
    },
    {
        "id": "productivity_pattern",
        "question": "When are you most productive during the day?",
        "type": "select",
        "options": [
            {"value": "morning", "label": "Morning (6am-11am)"},
            {"value": "midday", "label": "Midday (11am-3pm)"},
            {"value": "afternoon", "label": "Afternoon (3pm-6pm)"},
            {"value": "evening", "label": "Evening (6pm-10pm)"},
            {"value": "night", "label": "Night (10pm-2am)"}
        ],
        "default": "morning",
        "help_text": "We'll schedule your most challenging tasks during your peak productivity hours."
    },
    {
        "id": "break_preference",
        "question": "How often do you prefer to take breaks?",
        "type": "select",
        "options": [
            {"value": "short_frequent", "label": "Short frequent breaks (10-15 min every hour)"},
            {"value": "medium", "label": "Medium breaks (20-30 min every 2 hours)"},
            {"value": "long_infrequent", "label": "Longer infrequent breaks (45-60 min every 3-4 hours)"}
        ],
        "default": "medium",
        "help_text": "This helps us design your schedule with appropriate break intervals."
    },
    {
        "id": "study_session_length",
        "question": "What is your ideal study/work session length?",
        "type": "select",
        "options": [
            {"value": "short", "label": "Short (30-45 minutes)"},
            {"value": "medium", "label": "Medium (1-1.5 hours)"},
            {"value": "long", "label": "Long (2+ hours)"}
        ],
        "default": "medium",
        "help_text": "We'll try to chunk your tasks into sessions of this approximate length."
    },
    {
        "id": "weekend_scheduling",
        "question": "Do you want tasks scheduled on weekends?",
        "type": "select",
        "options": [
            {"value": "no", "label": "No, keep weekends free"},
            {"value": "light", "label": "Yes, but lighter load than weekdays"},
            {"value": "same", "label": "Yes, same as weekdays"}
        ],
        "default": "light",
        "help_text": "This determines how we distribute your workload across the week."
    },
    {
        "id": "meal_times",
        "question": "When do you typically have your meals?",
        "type": "complex",
        "subfields": [
            {"id": "breakfast", "label": "Breakfast", "type": "time", "default": "08:00"},
            {"id": "lunch", "label": "Lunch", "type": "time", "default": "12:30"},
            {"id": "dinner", "label": "Dinner", "type": "time", "default": "19:00"}
        ],
        "help_text": "We'll avoid scheduling important tasks during your meal times."
    },
    {
        "id": "study_location_preference",
        "question": "Where do you prefer to study/work?",
        "type": "select",
        "options": [
            {"value": "home", "label": "At home"},
            {"value": "library", "label": "Library or quiet space"},
            {"value": "cafe", "label": "Cafe or social space"},
            {"value": "mixed", "label": "Mixed environments"}
        ],
        "default": "mixed",
        "help_text": "This helps us group similar tasks that are best done in the same environment."
    },
    {
        "id": "focus_duration",
        "question": "How long can you typically maintain deep focus?",
        "type": "select",
        "options": [
            {"value": "short", "label": "Short periods (15-30 minutes)"},
            {"value": "medium", "label": "Medium periods (30-60 minutes)"},
            {"value": "long", "label": "Long periods (60+ minutes)"}
        ],
        "default": "medium",
        "help_text": "We'll design your task blocks based on your typical focus duration."
    },
    {
        "id": "learning_style",
        "question": "What learning/working style works best for you?",
        "type": "select",
        "options": [
            {"value": "spaced", "label": "Spaced practice (spread out over time)"},
            {"value": "blocked", "label": "Blocked practice (concentrated sessions)"},
            {"value": "interleaved", "label": "Interleaved practice (mixing different subjects)"}
        ],
        "default": "spaced",
        "help_text": "This helps us determine how to distribute your tasks across your schedule."
    }
]

def get_default_preferences():
    """Return a dictionary of default preferences"""
    defaults = {}
    for question in PREFERENCE_QUESTIONS:
        if question["type"] == "complex":
            defaults[question["id"]] = {subfield["id"]: subfield["default"] for subfield in question["subfields"]}
        else:
            defaults[question["id"]] = question["default"]
    return defaults 