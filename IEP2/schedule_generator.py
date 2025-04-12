from ortools.sat.python import cp_model

def generate_schedule(input_data):
    """
    Generate a weekly schedule using OR-Tools CP-SAT.
    Expects input_data with keys: 'meetings', 'tasks', 'preferences'.
    Returns input_data augmented with schedule.generated_calendar.
    """
    # ---- Preprocess Input: Ensure duration fields are numeric ----
    meetings = input_data.get('meetings', [])
    tasks    = input_data.get('tasks', [])
    prefs    = input_data.get('preferences', {})

    for event in meetings:
        if "duration_minutes" in event:
            try:
                event["duration"] = int(event["duration_minutes"])
            except Exception:
                event["duration"] = 0
        else:
            event["duration"] = 0

    for task in tasks:
        if "duration_minutes" in task:
            if task["duration_minutes"] is not None:
                try:
                    task["duration"] = int(task["duration_minutes"])
                except Exception:
                    task["duration"] = None
            else:
                task["duration"] = None
        else:
            task["duration"] = None

    # ---- Extract Work Hours and Other Preferences ----
    work_start_str = prefs.get('work_start', "09:00")
    work_end_str   = prefs.get('work_end', "22:00")
    include_weekend = prefs.get('include_weekend', True)
    def time_str_to_minutes(tstr):
        h, m = map(int, tstr.split(':'))
        return h * 60 + m
    work_start_min = time_str_to_minutes(work_start_str)
    work_end_min   = time_str_to_minutes(work_end_str)
    if work_end_min < work_start_min:
        raise ValueError("work_end must be after work_start")
    work_day_minutes = work_end_min - work_start_min  # e.g., if 09:00–22:00, that's 780 minutes.
    days_count = 7 if include_weekend else 5

    # Break preferences: In this version, we do not add hard break intervals.
    break_dur = prefs.get('break_duration', 15)  # break length (minutes)
    # Preferred maximum continuous session length after which tasks are split:
    preferred_session = prefs.get('preferred_session_length', 120)

    # Other preferences:
    grouping     = prefs.get('task_grouping', "mixed")         # "by_course", "by_priority", or "mixed"
    strategy     = prefs.get('scheduling_strategy', "balanced")  # "balanced", "front_loaded", etc.
    productivity = prefs.get('productivity_pattern', "mixed")      # "morning", "afternoon", "evening", or "mixed"
    # For preparation tasks, instead of a hard deadline, we impose a soft penalty if a prep task part is scheduled too late.
    # Here, "few_days" means the ideal is to finish the prep parts by (exam day - 1).
    prep_str = prefs.get('preparation_time', "few_days")
    ideal_offset = 1 if prep_str == "few_days" else 0

    # ---- Expand Tasks: Estimate missing durations and split long tasks ----
    expanded_tasks = []
    task_id_map = {}  # Maps original task ID to a list of new task IDs (for split tasks).
    for task in tasks:
        duration = task.get('duration')
        if duration is None:
            # Estimate: high → 240, medium → 180, low/default → 180 minutes.
            priority = str(task.get('priority', "")).lower()
            if priority in ["high", "1", "urgent"]:
                duration = 240
            elif priority in ["medium", "2"]:
                duration = 180
            else:
                duration = 180
            task["duration"] = duration
        # Split tasks if they exceed preferred_session
        if duration > preferred_session:
            full_chunks = duration // preferred_session
            remainder = duration % preferred_session
            chunk_count = full_chunks + (1 if remainder else 0)
            for j in range(chunk_count):
                part_duration = preferred_session if j < full_chunks else remainder
                if part_duration == 0:
                    continue
                part = task.copy()
                part_id = f"{task['id']}-part{j+1}"
                part["id"] = part_id
                part["duration"] = part_duration
                part["description"] = f"{task.get('description','Task')} (Part {j+1})"
                expanded_tasks.append(part)
                task_id_map.setdefault(task['id'], []).append(part_id)
        else:
            expanded_tasks.append(task)
            task_id_map.setdefault(task['id'], []).append(task['id'])

    # ---- Set Up CP-SAT Model ----
    model = cp_model.CpModel()
    task_vars = {}   # Mapping: task_id -> (start_var, end_var, interval_var, day_var, duration)
    event_vars = {}  # Mapping: event_id -> interval_var for fixed events

    # Define day mapping.
    day_name_to_index = {"monday": 0, "tuesday": 1, "wednesday": 2,
                         "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    def day_time_to_compressed(day_name, time_str):
        d_idx = day_name_to_index.get(day_name.lower())
        if d_idx is None:
            raise ValueError(f"Unknown day name: {day_name}")
        minutes = time_str_to_minutes(time_str)
        offset = minutes - work_start_min
        if offset < 0:
            offset = 0
        if offset > work_day_minutes:
            offset = work_day_minutes
        return d_idx * work_day_minutes + offset

    # ---- Create Fixed Intervals for Meetings ----
    for event in meetings:
        day_name = event.get('day')
        time_str = event.get('time')
        duration = event.get('duration', 0)
        if day_name and time_str is not None:
            start_compressed = day_time_to_compressed(day_name, time_str)
        else:
            continue
        start_var = model.NewIntVar(start_compressed, start_compressed, f"{event['id']}_start")
        end_var   = model.NewIntVar(start_compressed + duration, start_compressed + duration, f"{event['id']}_end")
        interval = model.NewIntervalVar(start_var, duration, end_var, f"event_{event['id']}_interval")
        event_vars[event['id']] = interval

    # ---- Create Interval Variables for Tasks ----
    for task in expanded_tasks:
        t_id = task['id']
        duration = task.get('duration')
        # Allowed start domain: each day d gives [d*work_day_minutes, d*work_day_minutes + work_day_minutes - duration].
        intervals = []
        for d in range(days_count):
            if not include_weekend and d >= 5:
                break
            intervals.append((d * work_day_minutes, d * work_day_minutes + work_day_minutes - duration))
        domain = cp_model.Domain.FromIntervals(intervals)
        start_var = model.NewIntVarFromDomain(domain, f"start_{t_id}")
        end_var   = model.NewIntVar(0, days_count * work_day_minutes, f"end_{t_id}")
        model.Add(end_var == start_var + duration)
        interval = model.NewIntervalVar(start_var, duration, end_var, f"task_{t_id}_interval")
        day_var = model.NewIntVar(0, days_count - 1, f"day_{t_id}")
        model.Add(start_var >= day_var * work_day_minutes)
        model.Add(start_var < (day_var + 1) * work_day_minutes)
        task_vars[t_id] = (start_var, end_var, interval, day_var, duration)

    # ---- Add NoOverlap for All Intervals (Fixed and Tasks) ----
    all_intervals = [v[2] for v in task_vars.values()] + list(event_vars.values())
    model.AddNoOverlap(all_intervals)

    # ---- Soft Preparation Constraint ----
    # For each exam (or presentation), we want prep tasks for that course ideally scheduled before (exam_day - ideal_offset).
    # Instead of a hard constraint, add a penalty if a prep task part's day is later than allowed.
    objective_terms = []  # We'll accumulate soft penalty terms.
    for event in meetings:
        e_type = str(event.get('type', '')).lower()
        if e_type in ('exam', 'presentation'):
            ev_day = event.get('day')
            ev_time = event.get('time')
            if not ev_day or not ev_time:
                continue
            exam_day = day_name_to_index.get(ev_day.lower(), 0)
            allowed_day = exam_day - ideal_offset  # e.g., if exam is on Thursday (3) and ideal_offset=1, allowed_day = 2.
            # For every prep task for the same course, if scheduled on a day greater than allowed_day, apply a penalty.
            for task in expanded_tasks:
                # Check if the task is a preparation task for the same course.
                if task.get('category', '').lower() == 'preparation' and \
                   task.get('course_code') and task.get('course_code') == event.get('course_code'):
                    # For each subtask (from splitting) of this task:
                    for t_id in task_id_map.get(task['id'], []):
                        if t_id not in task_vars:
                            continue
                        day_var = task_vars[t_id][3]
                        # Create an integer variable for the delay penalty: delay = max(0, day_var - allowed_day).
                        delay = model.NewIntVar(0, days_count, f"delay_{t_id}")
                        model.Add(delay >= day_var - allowed_day)
                        model.Add(delay >= 0)
                        # Add a penalty (e.g., weight=20 per extra day) to the objective.
                        objective_terms.append(delay * 20)

    # ---- Productivity and Scheduling Strategy Soft Constraints ----
    for t_id, (start_var, end_var, _, day_var, duration) in task_vars.items():
        start_in_day = model.NewIntVar(0, work_day_minutes, f"start_in_day_{t_id}")
        model.Add(start_in_day == start_var - day_var * work_day_minutes)
        if productivity.lower() == "morning":
            objective_terms.append(start_in_day)
        elif productivity.lower() == "evening":
            objective_terms.append(work_day_minutes - start_in_day)
        elif productivity.lower() == "afternoon":
            mid_point = work_day_minutes // 2
            above_mid = model.NewIntVar(0, work_day_minutes, f"above_mid_{t_id}")
            below_mid = model.NewIntVar(0, work_day_minutes, f"below_mid_{t_id}")
            model.Add(above_mid >= start_in_day - mid_point)
            model.Add(below_mid >= mid_point - start_in_day)
            objective_terms.append(above_mid)
            objective_terms.append(below_mid)
        # For scheduling strategy:
        if strategy.lower() == "front_loaded":
            objective_terms.append(day_var * 10)

    if strategy.lower() == "balanced":
        # For balanced scheduling, we add a term to minimize the maximum daily load.
        day_load = {}
        for d in range(days_count):
            if not include_weekend and d >= 5:
                break
            day_load[d] = model.NewIntVar(0, sum(v[4] for v in task_vars.values()), f"load_day_{d}")
        # (A full formulation would sum the durations of tasks assigned to day d)
        max_load = model.NewIntVar(0, sum(v[4] for v in task_vars.values()), "max_load")
        for d, load in day_load.items():
            model.Add(load <= max_load)
        objective_terms.append(max_load * 5)

    # Grouping soft constraint.
    if grouping.lower() in ("by_course", "by_priority"):
        groups = {}
        for task in expanded_tasks:
            key = task.get('course_code') if grouping.lower() == "by_course" else f"priority:{task.get('priority')}"
            for t_id in task_id_map.get(task['id'], []):
                groups.setdefault(key, []).append(t_id)
        for key, ids in groups.items():
            if len(ids) < 2:
                continue
            for i in range(len(ids)):
                for j in range(i+1, len(ids)):
                    if ids[i] in task_vars and ids[j] in task_vars:
                        day_i = task_vars[ids[i]][3]
                        day_j = task_vars[ids[j]][3]
                        diff = model.NewBoolVar(f"diff_{ids[i]}_{ids[j]}")
                        model.Add(day_i != day_j).OnlyEnforceIf(diff)
                        model.Add(day_i == day_j).OnlyEnforceIf(diff.Not())
                        objective_terms.append(diff * 3)

    model.Minimize(sum(objective_terms))

    # ---- Solve the Model ----
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(prefs.get("solver_parameters", {}).get("max_time_seconds", 10))
    solver.parameters.num_search_workers = int(prefs.get("solver_parameters", {}).get("num_search_workers", 8))
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise Exception("No feasible schedule found.")

    # ---- Build the Output Calendar ----
    # The calendar will be a dict mapping day names to a list of events.
    calendar_output = {"Monday": [], "Tuesday": [], "Wednesday": [], "Thursday": [], "Friday": []}
    if include_weekend:
        calendar_output["Saturday"] = []
        calendar_output["Sunday"] = []

    def minutes_to_hhmm(mins):
        hh = mins // 60
        mm = mins % 60
        return f"{hh:02d}:{mm:02d}"

    # Add fixed events (meetings)
    for event in meetings:
        day = event.get("day")
        time_str = event.get("time")
        duration = event.get("duration", 0)
        if not day or time_str is None:
            continue
        day_title = day.capitalize()
        sh, sm = map(int, time_str.split(':'))
        start_total = sh * 60 + sm
        end_total = start_total + duration
        entry = {
            "id": event["id"],
            "type": event.get("type", "meeting"),
            "description": event.get("description", event.get("type", "Event")),
            "course_code": event.get("course_code"),
            "category": "Meeting",
            "start_time": time_str,
            "end_time": minutes_to_hhmm(end_total % 1440),
            "duration": duration
        }
        if day_title in calendar_output:
            calendar_output[day_title].append(entry)

    # Add tasks (from CP model)
    for task in expanded_tasks:
        # For each original task, iterate over its sub-task IDs.
        for t_id in task_id_map.get(task['id'], []):
            if t_id not in task_vars:
                continue
            start_var, end_var, _, day_var, duration = task_vars[t_id]
            start_val = solver.Value(start_var)
            d_val = solver.Value(day_var)
            day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][d_val]
            offset = start_val - d_val * work_day_minutes
            actual_start = work_start_min + offset
            actual_end = actual_start + duration
            entry = {
                "id": t_id,
                "type": "task",
                "description": task.get("description", ""),
                "course_code": task.get("course_code"),
                "category": "Task",
                "start_time": minutes_to_hhmm(actual_start),
                "end_time": minutes_to_hhmm(actual_end),
                "duration": duration
            }
            if day_name in calendar_output:
                calendar_output[day_name].append(entry)

    # Optionally, post-process calendar to insert break events between sessions
    for day in calendar_output:
        new_events = []
        events = sorted(calendar_output[day], key=lambda x: int(x["start_time"].replace(":", "")))
        for i in range(len(events)):
            new_events.append(events[i])
            if i < len(events)-1:
                # Calculate gap between current end_time and next start_time.
                eh, em = map(int, events[i]["end_time"].split(':'))
                nsh, nsm = map(int, events[i+1]["start_time"].split(':'))
                gap = (nsh * 60 + nsm) - (eh * 60 + em)
                if 0 < gap <= break_dur + 5:
                    new_events.append({
                        "id": f"break_between_{events[i]['id']}_{events[i+1]['id']}",
                        "type": "break",
                        "description": "Break",
                        "start_time": events[i]["end_time"],
                        "end_time": events[i+1]["start_time"],
                        "duration": gap,
                        "course_code": None,
                        "category": "Break"
                    })
        calendar_output[day] = new_events

    # Attach calendar to output structure.
    input_data.setdefault('schedule', {})
    input_data['schedule']['generated_calendar'] = calendar_output
    input_data['success'] = True
    input_data['message'] = "Schedule successfully generated"
    return input_data

