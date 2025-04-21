"""
Schedule Generation Prompts and Helpers
This module contains prompt templates and utility functions for LLM-based schedule generation.
"""

def get_schedule_prompt(schedule_data, preferences=None, google_calendar=None):
    """
    Create a detailed prompt for the LLM to generate an optimized schedule.
    
    Args:
        schedule_data: Dictionary containing meetings and tasks
        preferences: Dictionary containing user preferences
        google_calendar: Optional Google Calendar data to incorporate
        
    Returns:
        String prompt for the LLM
    """
    # Format meetings for prompt
    meetings_text = ""
    for meeting in schedule_data.get("meetings", []):
        meeting_str = f"- {meeting.get('description', 'Untitled Meeting')}\n"
        meeting_str += f"  Day: {meeting.get('day', 'N/A')}\n"
        meeting_str += f"  Time: {meeting.get('time', 'N/A')}\n"
        meeting_str += f"  Duration: {meeting.get('duration_minutes', 'N/A')} minutes\n"
        meeting_str += f"  Type: {meeting.get('type', 'general')}\n"
        meeting_str += f"  Course: {meeting.get('course_code', 'N/A')}\n"
        meeting_str += f"  Priority: {meeting.get('priority', 'medium')}\n"
        meeting_str += f"  ID: {meeting.get('id', 'unknown')}\n\n"
        meetings_text += meeting_str

    # Format tasks for prompt
    tasks_text = ""
    for task in schedule_data.get("tasks", []):
        # Set a default duration if none provided
        duration = task.get("duration_minutes")
        if duration in [None, "", "null"]:
            priority = task.get("priority", "medium").lower()
            duration = 240 if priority in ["high", "1", "urgent"] else 180
            
        task_str = f"- {task.get('description', 'Untitled Task')}\n"
        task_str += f"  Category: {task.get('category', 'N/A')}\n"
        task_str += f"  Course: {task.get('course_code', 'N/A')}\n"
        task_str += f"  Duration: {duration} minutes\n"
        task_str += f"  Priority: {task.get('priority', 'medium')}\n"
        task_str += f"  Related Event: {task.get('related_event', 'N/A')}\n"
        task_str += f"  ID: {task.get('id', 'unknown')}\n\n"
        tasks_text += task_str

    # Format Google Calendar events if available
    google_calendar_text = ""
    if google_calendar:
        google_calendar_text = "# GOOGLE CALENDAR\nThe user has provided the following events from their Google Calendar that should be treated as fixed commitments:\n\n"
        for day, events in google_calendar.items():
            if events:  # Only include days with events
                google_calendar_text += f"{day}:\n"
                for event in events:
                    google_calendar_text += f"- {event.get('description', 'Untitled Event')}\n"
                    if 'start_time' in event and 'end_time' in event:
                        google_calendar_text += f"  Time: {event['start_time']} - {event['end_time']}\n"
                    if 'location' in event and event['location']:
                        google_calendar_text += f"  Location: {event['location']}\n"
                    google_calendar_text += "\n"
        google_calendar_text += "These Google Calendar events are mandatory and must be respected when creating the schedule. Do not schedule any activities that would conflict with these events.\n\n"

    # Format user preferences for the prompt if provided
    preferences_text = ""
    if preferences:
        preferences_text += "- Daily Schedule:\n"
        if 'wake_time' in preferences:
            preferences_text += f"  Wake-up time: {preferences['wake_time']}\n"
        if 'sleep_time' in preferences:
            preferences_text += f"  Sleep time: {preferences['sleep_time']}\n"
        
        if 'productivity_pattern' in preferences:
            productivity_map = {
                "morning": "Morning (6am-11am)",
                "midday": "Midday (11am-3pm)",
                "afternoon": "Afternoon (3pm-6pm)",
                "evening": "Evening (6pm-10pm)",
                "night": "Night (10pm-2am)"
            }
            pattern = productivity_map.get(preferences['productivity_pattern'], preferences['productivity_pattern'])
            preferences_text += f"- Productivity: User is most productive during {pattern}\n"
        
        if 'break_preference' in preferences:
            break_map = {
                "short_frequent": "short frequent breaks (10-15 min every hour)",
                "medium": "medium breaks (20-30 min every 2 hours)",
                "long_infrequent": "longer infrequent breaks (45-60 min every 3-4 hours)"
            }
            break_pref = break_map.get(preferences['break_preference'], preferences['break_preference'])
            preferences_text += f"- Break Preferences: User prefers {break_pref}\n"
        
        if 'study_session_length' in preferences:
            session_map = {
                "short": "short sessions (30-45 minutes)",
                "medium": "medium sessions (1-1.5 hours)",
                "long": "long sessions (2+ hours)"
            }
            session_pref = session_map.get(preferences['study_session_length'], preferences['study_session_length'])
            preferences_text += f"- Study Session Length: User prefers {session_pref}\n"
        
        if 'weekend_scheduling' in preferences:
            weekend_map = {
                "no": "no tasks on weekends",
                "light": "lighter workload on weekends",
                "same": "same workload on weekends as weekdays"
            }
            weekend_pref = weekend_map.get(preferences['weekend_scheduling'], preferences['weekend_scheduling'])
            preferences_text += f"- Weekend Scheduling: User prefers {weekend_pref}\n"
        
        if 'meal_times' in preferences:
            preferences_text += "- Meal Times:\n"
            meal_times = preferences['meal_times']
            if isinstance(meal_times, dict):
                if 'breakfast' in meal_times:
                    preferences_text += f"  Breakfast: {meal_times['breakfast']}\n"
                if 'lunch' in meal_times:
                    preferences_text += f"  Lunch: {meal_times['lunch']}\n"
                if 'dinner' in meal_times:
                    preferences_text += f"  Dinner: {meal_times['dinner']}\n"
        
        if 'study_location_preference' in preferences:
            location_map = {
                "home": "at home",
                "library": "in a library or quiet space",
                "cafe": "in a cafe or social space",
                "mixed": "in mixed environments"
            }
            location_pref = location_map.get(preferences['study_location_preference'], preferences['study_location_preference'])
            preferences_text += f"- Study Location: User prefers to study {location_pref}\n"
        
        if 'focus_duration' in preferences:
            focus_map = {
                "short": "short periods (15-30 minutes)",
                "medium": "medium periods (30-60 minutes)",
                "long": "long periods (60+ minutes)"
            }
            focus_pref = focus_map.get(preferences['focus_duration'], preferences['focus_duration'])
            preferences_text += f"- Focus Duration: User can maintain deep focus for {focus_pref}\n"
        
        if 'learning_style' in preferences:
            style_map = {
                "spaced": "spaced practice (spread out over time)",
                "blocked": "blocked practice (concentrated sessions)",
                "interleaved": "interleaved practice (mixing different subjects)"
            }
            style_pref = style_map.get(preferences['learning_style'], preferences['learning_style'])
            preferences_text += f"- Learning Style: User prefers {style_pref}\n"

    # Build the complete prompt
    prompt = f"""You are an advanced AI scheduling assistant that optimizes weekly schedules. Your task is to generate a balanced, optimized schedule based on the meetings and tasks provided.

{google_calendar_text}# FIXED MEETINGS
The following meetings are fixed and must be included exactly as specified:

{meetings_text if meetings_text else "No fixed meetings."}

# TASKS TO SCHEDULE
The following tasks need to be scheduled:

{tasks_text if tasks_text else "No tasks to schedule."}

# USER PREFERENCES
These preferences should guide your scheduling decisions:

{preferences_text if preferences_text else "No specific preferences provided. Use general best practices for scheduling."}

# SCHEDULING GUIDELINES
1. Fixed meetings cannot be moved - schedule them exactly as specified.
2. Google Calendar events (if provided) are top priority and must be respected - do not schedule anything that conflicts with them.
3. Tasks should be scheduled based on priority, with higher priority tasks scheduled first.
4. For exam preparation tasks, schedule them in multiple sessions across days leading up to the exam.
5. Schedule challenging tasks during the user's peak productivity hours based on their productivity pattern.
6. Allow appropriate breaks according to the user's break preference.
7. If a task requires multiple sessions, try to schedule these on consecutive days when possible.
8. Tasks labeled as "preparation" for an exam or presentation should be scheduled before the related event.
9. Respect the user's sleep and wake times - don't schedule activities outside of these hours.
10. Avoid scheduling important tasks during the user's meal times.
11. Consider the user's preferred study session length when allocating time for tasks.
12. If the user prefers not to work on weekends or prefers a lighter weekend load, adjust accordingly.
13. Match the user's focus duration - schedule difficult tasks in chunks that match their ability to focus.
14. Apply the user's learning style preference (spaced, blocked, or interleaved) when scheduling similar tasks.

# MEAL TIMES
Always schedule regular meal times each day:
1. Breakfast: Include a 30-minute breakfast slot (typically between 7:00-9:00)
2. Lunch: Include a 60-minute lunch break (typically between 12:00-14:00)
3. Dinner: Include a 60-minute dinner time (typically between 18:00-20:00)

Use the user's preferred meal times if specified in their preferences, otherwise use reasonable default times. Treat these as fixed appointments that should not have conflicting tasks.

# OUTPUT FORMAT
Your response must include a "generated_calendar" object that follows this structure exactly:

{{
  "Monday": [
    {{
      "id": "task-id",
      "type": "task",
      "description": "Task description",
      "course_code": "COURSE101",
      "duration": 120,
      "start_time": "09:00",
      "end_time": "11:00"
    }},
    // more events...
  ],
  "Tuesday": [ ... ],
  // other days of the week...
}}

Only include days from Monday to Friday unless weekend scheduling is requested.
Times must be in 24-hour format (HH:MM).
All existing meeting properties (id, type, description, etc.) must be preserved exactly.
For tasks, include: id, type ("task"), description, course_code, duration, start_time, and end_time.
For meals, use type "meal" and appropriate descriptions (e.g., "Breakfast", "Lunch", "Dinner").
For Google Calendar events, use type "google_event" and preserve their original properties.

# ADDITIONAL INSTRUCTIONS
- Do not modify the input data - preserve all IDs and metadata.
- If a task is too long, split it into multiple sessions of appropriate length (usually 1-2 hours).
- If you split a task, use the following ID format: "[original-id]-part1", "[original-id]-part2", etc.
- Ensure your response contains valid JSON that can be parsed.
- Return ONLY the generated_calendar JSON object and nothing else.
"""

    return prompt

def get_response_parsing_prompt(llm_response, original_schedule_data):
    """
    Create a prompt to help parse and validate the LLM's schedule response
    
    Args:
        llm_response: The raw response from the LLM
        original_schedule_data: The original schedule data sent to the LLM
        
    Returns:
        String prompt for the parsing LLM
    """
    
    prompt = f"""You are a JSON validation assistant. Your task is to take the JSON schedule below and validate it, ensuring it follows the correct format and contains all required information. If there are any errors or missing information, fix them.

# ORIGINAL SCHEDULE INPUT
```json
{original_schedule_data}
```

# LLM GENERATED SCHEDULE
```
{llm_response}
```

# VALIDATION REQUIREMENTS
1. The response should be a valid JSON object with a "generated_calendar" property.
2. The "generated_calendar" should contain day keys (Monday, Tuesday, etc.) with arrays of events.
3. Each event should have at minimum: id, type, description, start_time, end_time, and duration.
4. Fixed meetings from the original schedule must be preserved exactly.
5. All times must be in 24-hour format (HH:MM).
6. If the response doesn't contain proper JSON, extract the calendar data and format it correctly.

# OUTPUT FORMAT
Return a valid JSON object with the following structure:
{{
  "success": true,
  "schedule": {{
    "meetings": [...],  // from original data
    "tasks": [...],     // from original data
    "generated_calendar": {{
      "Monday": [...],  // validated events
      "Tuesday": [...],
      // other days
    }}
  }},
  "message": "Schedule successfully generated"
}}

Only return valid JSON and nothing else. If you need to make corrections, explain them in the "message" field.
"""
    
    return prompt 