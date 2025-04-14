import copy
import json

# Helper functions for time conversion
def time_str_to_minutes(tstr):
    """Convert a time string 'HH:MM' to minutes since midnight."""
    hours, minutes = map(int, tstr.split(":"))
    return hours * 60 + minutes

def minutes_to_time_str(mins):
    """Convert minutes to a 'HH:MM' formatted string."""
    h = mins // 60
    m = mins % 60
    return f"{h:02d}:{m:02d}"

def subtract_interval(interval, block):
    """
    Subtract a block interval (start, end) from an available interval.
    Returns a list of resulting intervals.
    """
    avail_start, avail_end = interval
    block_start, block_end = block
    if block_end <= avail_start or block_start >= avail_end:
        return [interval]
    result = []
    if block_start > avail_start:
        result.append((avail_start, min(block_start, avail_end)))
    if block_end < avail_end:
        result.append((max(block_end, avail_start), avail_end))
    return result

def remove_interval(free_intervals, block):
    """
    Remove a block interval from a list of free intervals.
    """
    new_intervals = []
    for intrvl in free_intervals:
        new_intervals.extend(subtract_interval(intrvl, block))
    new_intervals.sort(key=lambda x: x[0])
    return new_intervals

def split_task(duration, max_session):
    """Split a task duration into segments of max_session minutes (last segment may be smaller)."""
    segments = []
    while duration > max_session:
        segments.append(max_session)
        duration -= max_session
    if duration > 0:
        segments.append(duration)
    return segments

def generate_schedule(input_data):
    """
    generate_schedule() is a rule-based scheduling algorithm that:
      - Checks for top-level keys "meetings", "tasks", and "preferences".
      - Wraps them into a "schedule" object if not already provided.
      - Computes free intervals for each day based on work hours.
      - Places fixed meetings (and removes their time from the free intervals).
      - Processes flexible tasks:
            * For each task, if "duration_minutes" is missing, empty, or the string "null", 
              it sets a default (240 minutes for high priority, 180 for others) and stores it
              in the "duration" field as an integer.
            * If the task’s duration exceeds the preferred session length (default 120 minutes),
              it is split into parts.
      - Greedily schedules each task part (sub-task) into the earliest available free interval,
        favoring days before an exam (if one exists for that course).
      - Builds a "generated_calendar" in the "schedule" section.
    
    Returns the input data augmented with the final "generated_calendar".
    """
    data = copy.deepcopy(input_data)
    
    # If the input doesn't already wrap meetings/tasks under "schedule", do it now.
    if "schedule" not in data:
        data["schedule"] = {
            "course_codes": data.get("course_codes", []),
            "meetings": data.get("meetings", []),
            "tasks": data.get("tasks", [])
        }
    schedule_in = data["schedule"]
    
    # Always create a fresh generated_calendar.
    schedule_in["generated_calendar"] = {}
    
    # Extract meetings, tasks, and preferences.
    meetings = schedule_in.get("meetings", [])
    tasks = schedule_in.get("tasks", [])
    prefs = data.get("preferences", {})
    
    # ---------------------------
    # Setup Workday Parameters
    # ---------------------------
    work_start = prefs.get("work_start", "09:00")
    work_end = prefs.get("work_end", "17:00")
    work_start_min = time_str_to_minutes(work_start)
    work_end_min = time_str_to_minutes(work_end)
    work_day_minutes = work_end_min - work_start_min  # e.g., 480 minutes
    include_weekend = prefs.get("include_weekend", False)
    total_days = 7 if include_weekend else 5
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    if include_weekend:
        day_names += ["Saturday", "Sunday"]
    
    # Initialize calendar and free intervals per day.
    calendar = { day: [] for day in day_names }
    free_intervals = { day: [(work_start_min, work_end_min)] for day in day_names }
    
    # ---------------------------
    # Place Fixed Meetings
    # ---------------------------
    exam_days = {}  # Records exam day per course.
    for event in meetings:
        event_day = event.get("day")
        event_time = event.get("time")
        duration = event.get("duration_minutes") or event.get("duration")
        if event_day is None or event_time is None or duration is None:
            continue
        event_day = event_day.capitalize()
        start = time_str_to_minutes(event_time)
        end = start + int(duration)
        meeting_entry = {
            "id": event.get("id"),
            "type": event.get("type"),
            "description": event.get("description"),
            "course_code": event.get("course_code"),
            "location": event.get("location"),
            "start_time": event.get("time"),
            "end_time": minutes_to_time_str(end),
            "duration": int(duration)
        }
        if event_day in calendar:
            calendar[event_day].append(meeting_entry)
        block = (start, end)
        free_intervals[event_day] = remove_interval(free_intervals[event_day], block)
        if event.get("type", "").lower() in ["exam", "presentation"]:
            course = event.get("course_code")
            if course:
                exam_days[course] = event_day
    
    # ---------------------------
    # Process Flexible Tasks
    # ---------------------------
    for task in tasks:
        # Check if duration_minutes is missing, empty, or equals "null".
        if task.get("duration_minutes") in [None, "", "null"]:
            priority = task.get("priority", "medium").lower()
            task["duration_minutes"] = 240 if priority in ["high", "1", "urgent"] else 180
        try:
            task["duration"] = int(task.get("duration_minutes"))
        except:
            task["duration"] = 0
    
    # Preferred session length; if a task exceeds this, it will be split.
    preferred_session = prefs.get("preferred_session_length", 120)
    
    # Split tasks if needed.
    split_tasks = []
    split_map = {}  # original task id -> list of sub-task ids.
    for task in tasks:
        duration = task.get("duration")
        if duration > preferred_session:
            segments = split_task(duration, preferred_session)
            part_ids = []
            part_number = 1
            for seg in segments:
                part = copy.deepcopy(task)
                part_id = f"{task['id']}-part{part_number}"
                part["id"] = part_id
                part["duration_minutes"] = seg
                part["duration"] = seg
                split_tasks.append(part)
                part_ids.append(part_id)
                part_number += 1
            split_map[task["id"]] = part_ids
        else:
            split_tasks.append(task)
            split_map.setdefault(task["id"], []).append(task["id"])
    
    # ---------------------------
    # Greedy Scheduling: Place Task Parts into Free Blocks
    # ---------------------------
    for task in split_tasks:
        if task.get("category", "").lower() != "preparation":
            continue
        course = task.get("course_code")
        target_day = None
        if course in exam_days:
            try:
                exam_index = day_names.index(exam_days[course])
                target_day = day_names[max(0, exam_index - 1)]
            except:
                pass
        candidates = []
        if target_day:
            candidates.append(target_day)
        for d in day_names:
            if d not in candidates:
                candidates.append(d)
        scheduled = False
        task_duration = int(task["duration"])
        for day in candidates:
            free_blocks = free_intervals.get(day, [])
            for block in free_blocks:
                block_start, block_end = block
                if (block_end - block_start) >= task_duration:
                    task["scheduled_day"] = day
                    task["scheduled_start"] = block_start
                    task["scheduled_end"] = block_start + task_duration
                    free_intervals[day] = remove_interval(free_blocks, (block_start, block_start + task_duration))
                    scheduled = True
                    break
            if scheduled:
                break
        if not scheduled:
            task["scheduled_day"] = None
            task["scheduled_start"] = None
            task["scheduled_end"] = None
    
    # ---------------------------
    # Build the Final Calendar Output
    # ---------------------------
    generated_calendar = { day: [] for day in day_names }
    # Insert fixed meetings.
    for day in calendar:
        generated_calendar[day] = sorted(calendar[day],
                                          key=lambda x: time_str_to_minutes(x["start_time"]))
    # Insert scheduled task parts.
    for task in split_tasks:
        if task.get("category", "").lower() != "preparation":
            continue
        day = task.get("scheduled_day")
        if day:
            start = task.get("scheduled_start")
            end = task.get("scheduled_end")
            entry = {
                "id": task.get("id"),
                "type": "task",
                "description": task.get("description"),
                "course_code": task.get("course_code"),
                "duration": int(task.get("duration")),
                "start_time": minutes_to_time_str(start),
                "end_time": minutes_to_time_str(end)
            }
            generated_calendar[day].append(entry)
    for day in generated_calendar:
        generated_calendar[day].sort(key=lambda x: time_str_to_minutes(x["start_time"]) if x.get("start_time") else 0)
    
    # Attach the generated calendar.
    schedule_in["generated_calendar"] = generated_calendar
    data["success"] = True
    data["message"] = "Schedule successfully generated using rule-based heuristics"
    return data

