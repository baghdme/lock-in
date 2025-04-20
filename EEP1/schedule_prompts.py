"""
Schedule Generation Prompts and Helpers
This module contains prompt templates and utility functions for LLM-based schedule generation.
"""

def get_schedule_prompt(schedule_data):
    """
    Create a detailed prompt for the LLM to generate an optimized schedule.
    
    Args:
        schedule_data: Dictionary containing meetings and tasks
        preferences: Dictionary containing user preferences
        
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


    # Build the complete prompt
    prompt = f"""You are an advanced AI scheduling assistant that optimizes weekly schedules. Your task is to generate a balanced, optimized schedule based on the meetings and tasks provided.

# FIXED MEETINGS
The following meetings are fixed and must be included exactly as specified:

{meetings_text if meetings_text else "No fixed meetings."}

# TASKS TO SCHEDULE
The following tasks need to be scheduled:

{tasks_text if tasks_text else "No tasks to schedule."}

# USER PREFERENCES
These preferences should guide your scheduling decisions

# SCHEDULING GUIDELINES
1. Fixed meetings cannot be moved - schedule them exactly as specified.
2. Tasks should be scheduled based on priority, with higher priority tasks scheduled first.
3. For exam preparation tasks, schedule them in multiple sessions across days leading up to the exam.
4. Schedule challenging tasks during the user's peak productivity hours based on their productivity pattern.
5. Allow appropriate breaks according to the user's break preference.
6. If a task requires multiple sessions, try to schedule these on consecutive days when possible.
7. Tasks labeled as "preparation" for an exam or presentation should be scheduled before the related event.

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