"""
Preference Questions Module for EEP1.

This module provides functions to get preference and algorithm questions for the schedule generator.
These questions are used to customize the scheduling algorithm after all required information is collected.
"""

import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_preference_questions():
    """
    Get the list of user preference questions for scheduling.
    
    Returns:
        A list of question objects with id, text, type, and options.
    """
    return [
        {
            "id": "work_start",
            "text": "What time do you usually start your work day?",
            "type": "time",
            "default": "09:00"
        },
        {
            "id": "work_end",
            "text": "What time do you usually end your work day?",
            "type": "time",
            "default": "17:00"
        },
        {
            "id": "productivity_pattern",
            "text": "When are you most productive?",
            "type": "single_choice",
            "options": [
                {"value": "morning", "text": "Morning"},
                {"value": "afternoon", "text": "Afternoon"},
                {"value": "evening", "text": "Evening"},
                {"value": "mixed", "text": "No specific time"}
            ],
            "default": "morning"
        },
        {
            "id": "break_preference",
            "text": "How would you like breaks to be scheduled?",
            "type": "single_choice",
            "options": [
                {"value": "frequent", "text": "Frequent short breaks"},
                {"value": "regular", "text": "Regular medium breaks"},
                {"value": "few", "text": "Few longer breaks"},
                {"value": "none", "text": "No scheduled breaks"}
            ],
            "default": "regular"
        },
        {
            "id": "include_weekend",
            "text": "Would you like to include weekends in your schedule?",
            "type": "boolean",
            "default": False
        },
        {
            "id": "task_grouping",
            "text": "How would you like to group your tasks?",
            "type": "single_choice",
            "options": [
                {"value": "by_course", "text": "Group by course/subject"},
                {"value": "by_priority", "text": "Group by priority"},
                {"value": "mixed", "text": "Mix different types of tasks"}
            ],
            "default": "mixed"
        }
    ]

def get_algorithm_questions():
    """
    Get the list of algorithm-specific questions that influence the scheduling strategy.
    
    Returns:
        A list of question objects with id, text, type, and options.
    """
    return [
        {
            "id": "scheduling_strategy",
            "text": "What scheduling strategy would you prefer?",
            "type": "single_choice",
            "options": [
                {"value": "balanced", "text": "Balanced workload across days"},
                {"value": "front_loaded", "text": "More work early in the week"},
                {"value": "back_loaded", "text": "More work later in the week"},
                {"value": "priority_based", "text": "Strictly prioritize high-priority tasks"}
            ],
            "default": "balanced"
        },
        {
            "id": "break_duration",
            "text": "How long should default breaks be (in minutes)?",
            "type": "number",
            "min": 5,
            "max": 60,
            "default": 15
        },
        {
            "id": "break_frequency",
            "text": "How often would you like to have breaks?",
            "type": "single_choice",
            "options": [
                {"value": "low", "text": "After about 2 hours of work"},
                {"value": "medium", "text": "After about 1.5 hours of work"},
                {"value": "high", "text": "After about 1 hour of work"}
            ],
            "default": "medium"
        },
        {
            "id": "preparation_time",
            "text": "When do you prefer to do preparation tasks for events?",
            "type": "single_choice",
            "options": [
                {"value": "well_before", "text": "Well in advance (3-5 days before)"},
                {"value": "few_days", "text": "A few days before (1-2 days)"},
                {"value": "day_before", "text": "The day before"},
                {"value": "same_day", "text": "Same day (if possible)"}
            ],
            "default": "few_days"
        }
    ]

def get_default_preferences():
    """
    Get the default values for all preferences.
    
    Returns:
        A dictionary with default preference values.
    """
    defaults = {}
    
    # Add default values from preference questions
    for question in get_preference_questions():
        defaults[question["id"]] = question.get("default")
    
    # Add default values from algorithm questions
    for question in get_algorithm_questions():
        defaults[question["id"]] = question.get("default")
    
    return defaults 