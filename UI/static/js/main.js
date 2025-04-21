// Authentication functions
function showSignUp() {
    document.querySelector('.auth-form').classList.add('hidden');
    document.getElementById('signup-form').classList.remove('hidden');
}

function showSignIn() {
    document.querySelector('.auth-form').classList.remove('hidden');
    document.getElementById('signup-form').classList.add('hidden');
}

function signIn() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    // TODO: Implement actual authentication
    if (email && password) {
        document.getElementById('auth-section').classList.add('hidden');
        document.getElementById('schedule-section').classList.remove('hidden');
    }
}

function signUp() {
    const email = document.getElementById('signup-email').value;
    const password = document.getElementById('signup-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    if (password !== confirmPassword) {
        alert('Passwords do not match!');
        return;
    }
    
    // TODO: Implement actual signup
    if (email && password) {
        showSignIn();
    }
}

// Schedule functions
let currentQuestions = [];
let currentQuestionIndex = 0;
let currentSchedule = null;
let allMissingInfoResolved = false;

function showQuestionDialog(questions) {
    // Remove loading overlay if it exists
    let overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.remove();
    }
    if (!questions || questions.length === 0) {
        console.warn('No questions to display');
        return;
    }
    
    const question = questions[0]; // Get the first question
    const dialog = document.getElementById('questionDialog');
    
    // Set data attributes to store question info
    dialog.dataset.questionId = question.target_id;
    dialog.dataset.questionType = question.type;
    dialog.dataset.questionTarget = question.target;
    dialog.dataset.questionField = question.field;
    dialog.dataset.questionTargetType = question.target_type;
    
    // For AM/PM questions, store the original time value
    if (question.type === 'ampm' && question.original_time) {
        dialog.dataset.originalTime = question.original_time;
    }
    
    // Set the question text
    document.getElementById('questionText').textContent = question.question;
    
    // Create appropriate input based on question type
    const inputContainer = document.getElementById('questionInput');
    inputContainer.innerHTML = '';
    
    // Check if the question specifies input_type as dropdown
    if (question.input_type === 'dropdown' && question.options && question.options.length > 0) {
        // Create a dropdown/select element
        const selectElement = document.createElement('select');
        selectElement.id = 'dropdownInput';
        selectElement.className = 'form-control';
        selectElement.required = true;
        
        // Add empty default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Please select an option';
        defaultOption.disabled = true;
        defaultOption.selected = true;
        selectElement.appendChild(defaultOption);
        
        // Add options from the question
        question.options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option.value;
            optionElement.textContent = option.text;
            selectElement.appendChild(optionElement);
        });
        
        inputContainer.appendChild(selectElement);
    } else if (question.type === 'time') {
        // Create time input
        const timeInput = document.createElement('input');
        timeInput.type = 'time';
        timeInput.id = 'timeInput';
        timeInput.className = 'form-control';
        timeInput.required = true;
        inputContainer.appendChild(timeInput);
    } else if (question.type === 'duration') {
        // Create duration input (minutes)
        const durationInput = document.createElement('input');
        durationInput.type = 'number';
        durationInput.id = 'durationInput';
        durationInput.className = 'form-control';
        durationInput.min = '1';
        durationInput.placeholder = 'Duration in minutes';
        durationInput.required = true;
        inputContainer.appendChild(durationInput);
    } else {
        // Create text input for other types (like course_code)
        const answerInput = document.createElement('input');
        answerInput.type = 'text';
        answerInput.id = 'answerInput';
        answerInput.className = 'form-control';
        answerInput.placeholder = 'Your answer';
        answerInput.required = true;
        
        if (question.type === 'course_code') {
            answerInput.placeholder = 'e.g., EECE503';
            answerInput.pattern = '[A-Z]{2,4}[0-9]{3}[A-Z]?';
        }
        
        inputContainer.appendChild(answerInput);
    }
    
    // Show the dialog
    dialog.classList.remove('hidden');
}

function submitAnswer() {
    // Get the current question information from the dialog
    const dialog = document.querySelector('#questionDialog');
    const questionId = dialog.dataset.questionId;
    const questionType = dialog.dataset.questionType;
    const questionTarget = dialog.dataset.questionTarget;
    const questionField = dialog.dataset.questionField;
    const questionTargetType = dialog.dataset.questionTargetType;
    const originalTime = dialog.dataset.originalTime; // For AM/PM questions

    // Get the answer from the appropriate input field
    let answer;
    
    // Check if we're dealing with a dropdown input
    const dropdownInput = document.getElementById('dropdownInput');
    if (dropdownInput) {
        answer = dropdownInput.value;
    } else if (questionType === 'time') {
        const timeInput = document.getElementById('timeInput');
        answer = timeInput ? timeInput.value : '';
    } else if (questionType === 'duration') {
        const durationInput = document.getElementById('durationInput');
        answer = durationInput ? durationInput.value : '';
    } else {
        const answerInput = document.getElementById('answerInput');
        answer = answerInput ? answerInput.value : '';
    }

    if (!answer) {
        alert('Please provide an answer');
        return;
    }

    // Disable the submit button to prevent double submission
    const submitBtn = document.querySelector('#questionDialog .dialog-buttons button:first-child');
    submitBtn.disabled = true;
    submitBtn.innerText = 'Submitting...';

    // If currentSchedule is null, try to retrieve from localStorage
    if (!currentSchedule) {
        const storedSchedule = localStorage.getItem('currentSchedule');
        if (storedSchedule) {
            currentSchedule = JSON.parse(storedSchedule);
        }
    }

    // Prepare the request body
    const requestBody = {
        item_id: questionId,
        type: questionType,
        answer: answer,
        field: questionField,
        target: questionTarget,
        target_type: questionTargetType,
        schedule: currentSchedule
    };

    // Add original_time for AM/PM questions
    if (questionType === 'ampm' && originalTime) {
        requestBody.original_time = originalTime;
    }

    fetch('http://localhost:5002/answer-question', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Answer response:', data);
        currentSchedule = data.schedule;
        localStorage.setItem('currentSchedule', JSON.stringify(currentSchedule));

        // Close the current question dialog
        closeDialog();

        if (data.questions && data.questions.length > 0) {
            // Show the next question
            showQuestionDialog(data.questions);
        } else {
            // No more missing info questions
            allMissingInfoResolved = true;
            document.getElementById('scheduleOutput').innerHTML = '<div class="info-message">Generating your optimized schedule...</div>';
            
            // Go directly to optimization
            setTimeout(() => {
                generateOptimizedSchedule();
            }, 500);
        }
        
        // Re-enable the button
        submitBtn.disabled = false;
        submitBtn.innerText = 'Submit';
    })
    .catch(error => {
        console.error('Error:', error);
        alert(`Error submitting answer: ${error.message}`);
        
        // Re-enable the button
        submitBtn.disabled = false;
        submitBtn.innerText = 'Submit';
    });
}

function closeDialog() {
    document.getElementById('questionDialog').classList.add('hidden');
    currentQuestions = [];
    currentQuestionIndex = 0;
}

function setLoadingState(state) {
    // Create an overlay div that mimics the dialog styling (centered, covering the prompt area)
    let overlay = document.createElement('div');
    overlay.className = 'dialog';
    overlay.id = 'loadingOverlay';

    let content = document.createElement('div');
    content.className = 'dialog-content';

    let header = document.createElement('h2');
    if (state === 'missing_info') {
         header.textContent = "Looking for Missing Information...";
    } else if (state === 'optimizing') {
         header.textContent = "Optimizing Your Schedule...";
    } else {
         header.textContent = "Processing...";
    }
    content.appendChild(header);

    let spinner = document.createElement('div');
    spinner.className = 'spinner';
    content.appendChild(spinner);

    let infoText = document.createElement('p');
    if (state === 'missing_info') {
         infoText.textContent = "We are collecting the missing information required.";
    } else if (state === 'optimizing') {
         infoText.textContent = "We are creating your optimized schedule!";
    }
    content.appendChild(infoText);

    overlay.appendChild(content);

    // Append the overlay to the document body, covering the prompt area
    document.body.appendChild(overlay);
}

// Add a parseSchedule function
function parseSchedule(scheduleText, onSuccess) {
    setLoadingState('missing_info');

    fetch('http://localhost:5002/parse-schedule', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: scheduleText }),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Received data:', data);
        currentSchedule = data.schedule;
        localStorage.setItem('currentSchedule', JSON.stringify(currentSchedule));
        
        if (data.questions && data.questions.length > 0) {
            showQuestionDialog(data.questions);
        } else {
            // No questions, all info is complete
            allMissingInfoResolved = true;
            
            if (onSuccess) {
                onSuccess();
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('scheduleOutput').innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
        
        // Remove loading overlay
        let overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            overlay.remove();
        }
    });
}

// Update generateSchedule to use parseSchedule
function generateSchedule() {
    const scheduleText = document.getElementById('scheduleText').value;
    if (!scheduleText.trim()) {
        alert('Please enter a schedule description');
        return;
    }

    // Reset state
    allMissingInfoResolved = false;

    // Get the button that was clicked to handle proper re-enabling
    const submitBtn = document.querySelector('button[onclick="generateSchedule()"]');
    submitBtn.disabled = true;
    submitBtn.innerText = 'Submitting...';
    
    // Parse the schedule first, then generate optimized schedule
    parseSchedule(scheduleText, () => {
        document.getElementById('scheduleOutput').innerHTML = '<div class="info-message">Generating your optimized schedule...</div>';
        
        // Skip preferences and go directly to optimization
        setTimeout(() => {
            generateOptimizedSchedule();
        }, 500);
    });
    
    // Re-enable the button
    setTimeout(() => {
        submitBtn.disabled = false;
        submitBtn.innerText = 'Generate Schedule';
    }, 1000);
}

// Functions for calendar import
function showImportDialog() {
    document.getElementById('importDialog').classList.remove('hidden');
}

function closeImportDialog() {
    document.getElementById('importDialog').classList.add('hidden');
    // Reset the file input
    document.getElementById('calendarFile').value = '';
}

function uploadCalendar() {
    const fileInput = document.getElementById('calendarFile');
    if (!fileInput.files.length) {
        alert('Please select a JSON file to upload');
        return;
    }
    
    // Create a FormData object to send the file
    const formData = new FormData();
    formData.append('calendar_file', fileInput.files[0]);
    
    // Disable the upload button
    const uploadBtn = document.querySelector('#importDialog button[onclick="uploadCalendar()"]');
    uploadBtn.disabled = true;
    uploadBtn.innerText = 'Uploading...';
    
    // Send the file to the server
    fetch('/import-calendar', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Failed to import calendar');
            });
        }
        return response.json();
    })
    .then(data => {
        alert(data.message || 'Calendar imported successfully');
        closeImportDialog();
        
        // Remove automatic schedule generation - just show success message
        document.getElementById('scheduleOutput').innerHTML = '<div class="info-message">Calendar imported successfully. Enter schedule details and process them, or start with a new schedule from scratch.</div>';
    })
    .catch(error => {
        console.error('Error importing calendar:', error);
        alert(`Error importing calendar: ${error.message}`);
    })
    .finally(() => {
        // Re-enable the upload button
        uploadBtn.disabled = false;
        uploadBtn.innerText = 'Upload';
    });
}

// Update generateOptimizedSchedule function
function generateOptimizedSchedule() {
    console.log('generateOptimizedSchedule called');
    console.log('currentSchedule value:', currentSchedule);
    
    if (!currentSchedule) {
        console.error('Cannot generate optimized schedule: currentSchedule is null');
        document.getElementById('scheduleOutput').innerHTML = `<div class="error-message">Error: No schedule data available. Please parse schedule text first.</div>`;
        return;
    }
    
    setLoadingState('optimizing');
    
    // Call the backend directly to generate the optimized schedule
    fetch('http://localhost:5002/generate-optimized-schedule', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            schedule: currentSchedule
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Failed to generate optimized schedule');
            });
        }
        return response.json();
    })
    .then(data => {
        // Redirect to the schedule-only view
        window.location.href = '/schedule-only';
    })
    .catch(error => {
        setLoadingState('none');
        console.error('Error generating optimized schedule:', error);
        document.getElementById('scheduleOutput').innerHTML = `<div class="error-message">Error generating optimized schedule: ${error.message}</div>`;
    });
}

// --- UPDATED displayFormattedSchedule ---
// in your main.js

function displayFormattedSchedule(schedule) {
    const container = document.getElementById('scheduleOutput');
    container.innerHTML = '';
    container.className = 'calendar-container';
  
    // 1) compute dynamic start/end hours
    let minTime = Infinity, maxTime = -Infinity;
    Object.values(schedule.generated_calendar || {}).forEach(dayEvents => {
      dayEvents.forEach(ev => {
        const [sh, sm] = ev.start_time.split(':').map(Number);
        const [eh, em] = ev.end_time.split(':').map(Number);
        minTime = Math.min(minTime, sh + sm/60);
        maxTime = Math.max(maxTime, eh + em/60);
      });
    });
    
    // If there are no events or all events are after 8AM, start at 8AM
    // Otherwise, use the earliest event time
    const DEFAULT_START_HOUR = 8;
    if (!isFinite(minTime)) {
      minTime = DEFAULT_START_HOUR;
      maxTime = 17; // Default end at 5PM
    } else {
      // If earliest event is after 8AM, start at 8AM
      minTime = Math.min(DEFAULT_START_HOUR, minTime);
    }
    
    // Use EXACT values without rounding for better precision
    // We'll use the integer part for display but keep the exact value for calculations
    const startHour = Math.floor(minTime); // We still need the integer for labels
    const endHour = Math.ceil(maxTime);    // We still need the integer for labels
    const exactStartHour = minTime;        // Keep exact value for precise calculations

    const days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
    const hourCount = endHour - startHour + 1;
    
    // Cell height for calculation (match this with CSS)
    const hourRowHeight = 70; // px, match with .day-cell height in CSS
  
    // 2) set up rows: header + each hour matching hourRowHeight
    container.style.gridTemplateRows = `auto repeat(${hourCount}, ${hourRowHeight}px)`;
  
    // 3) headers
    // corner
    const corner = document.createElement('div');
    corner.className = 'time-label';
    container.appendChild(corner);
    // day names
    days.forEach((day,i) => {
      const dh = document.createElement('div');
      dh.className = 'day-header';
      dh.textContent = day;
      dh.style.gridColumnStart = i+2;
      container.appendChild(dh);
    });
  
    // Store cell references for precise mathematical positioning
    const dayCellsByColumn = {};
    const headerHeight = corner.offsetHeight;

    // 4) time labels + blank cells
    for (let i=0; i<=endHour-startHour; i++) {
      const hour = startHour + i;
      // label
      const tl = document.createElement('div');
      tl.className = 'time-label';
      tl.style.gridRowStart = i+2;
      tl.textContent = formatTime(`${String(hour).padStart(2,'0')}:00`)
                       .replace(':00','').replace(' ','');
      container.appendChild(tl);
      // blanks
      days.forEach((_,d) => {
        const cell = document.createElement('div');
        cell.className = 'day-cell';
        cell.style.gridRowStart = i+2;
        cell.style.gridColumnStart = d+2;
        container.appendChild(cell);
        
        // Store cells by column index for precise positioning later
        if (!dayCellsByColumn[d+2]) {
          dayCellsByColumn[d+2] = [];
        }
        dayCellsByColumn[d+2].push(cell);
      });
    }
  
    // Get the first cell's position to use as a reference
    const firstCellPosition = {
      top: dayCellsByColumn[2]?.[0]?.offsetTop || headerHeight,
      left: dayCellsByColumn[2]?.[0]?.offsetLeft || 70
    };
  
    // 5) events - Create events and position them correctly with CSS grid
    days.forEach((day, di) => {
      const dayEvents = schedule.generated_calendar[day] || [];
      
      dayEvents.forEach(ev => {
        // Parse times
        const [sh, sm] = ev.start_time.split(':').map(Number);
        const [eh, em] = ev.end_time.split(':').map(Number);
        
        // Create the event element
        const eventElement = document.createElement('div');
        eventElement.className = 'event-block';
        
        // Add event type as a class if available
        if (ev.type) {
          eventElement.classList.add(ev.type.toLowerCase());
        }
        
        // Format time for display
        const startLabel = formatTime(ev.start_time).replace(':00','').replace(' ','');
        const endLabel = formatTime(ev.end_time).replace(':00','').replace(' ','');
        const title = `${startLabel}–${endLabel}`;
        
        // Get simplified event description
        const simpleDescription = getSimpleEventType(ev);
        
        // Build the HTML content
        eventElement.innerHTML = `
          <div><strong>${title}</strong></div>
          <div>${simpleDescription}</div>
          ${ev.course_code ? `<div class="course-code">${ev.course_code}</div>` : ''}
        `;
        
        // Add to container first (needed to calculate positions correctly)
        container.appendChild(eventElement);
        
        // Calculate the correct column for this day
        const dayColumn = di + 2; // +2 for time label column
        
        // EXACT mathematical positioning - no more relying on offsetTop!
        // Calculate exact position based on time difference from start hour
        const hourDiffFromStart = (sh - startHour) + (sm / 60);
        
        // Get the first cell in the column to determine left position
        const columnCells = dayCellsByColumn[dayColumn] || [];
        const firstColumnCell = columnCells[0] || null;
        
        // Calculate the exact position mathematically
        // This is the EXACT pixel position based on hours and minutes
        const startPosition = firstCellPosition.top + (hourDiffFromStart * hourRowHeight);
        
        // Calculate the exact height based on the duration
        // Convert time difference to minutes then to pixels
        const durationInHours = ((eh - sh) * 60 + (em - sm)) / 60;
        const height = durationInHours * hourRowHeight;
        
        // Get left position from column reference cell
        const leftPosition = firstColumnCell ? firstColumnCell.offsetLeft : (70 + (dayColumn - 2) * 100);
        const cellWidth = firstColumnCell ? firstColumnCell.offsetWidth : 100;
        
        // Log positioning data for debugging
        console.log(`EXACT Event Positioning: ${ev.description || simpleDescription}, Time: ${ev.start_time}-${ev.end_time}`);
        console.log(`  EXACT startPosition: ${startPosition}px, height: ${height}px`);
        console.log(`  Math: sh=${sh}, sm=${sm}, startHour=${startHour}, hourDiffFromStart=${hourDiffFromStart}`);
        console.log(`  EXACT Calculation: ${firstCellPosition.top} + (${hourDiffFromStart} * ${hourRowHeight}) = ${startPosition}`);
        
        // Apply positioning with !important to override any CSS rules
        // Use the EXACT mathematical values
        eventElement.setAttribute('style', `
          position: absolute !important;
          top: ${startPosition}px !important;
          height: ${Math.max(20, height)}px !important;
          left: ${leftPosition + 1}px !important;
          width: ${cellWidth - 4}px !important;
          box-sizing: border-box !important;
          margin: 0 !important;
          padding: 10px 12px !important;
          z-index: 10 !important;
          transition: none !important;
          transform: none !important;
        `);
        
        // Add a data attribute to help with debugging
        eventElement.setAttribute('data-time', `${ev.start_time}-${ev.end_time}`);
        eventElement.setAttribute('data-day', day);
        eventElement.setAttribute('data-exact-top', startPosition);
        eventElement.setAttribute('data-hour-diff', hourDiffFromStart);
        
        // Add a debug class to show positioning information
        eventElement.classList.add('js-positioned');
      });
    });
    
    // Adjust event styling for proper display
    const styleElement = document.createElement('style');
    styleElement.textContent = `
      .calendar-container {
        display: grid;
        grid-template-columns: 70px repeat(7, 1fr);
        position: relative;
      }
      .calendar-container .day-cell {
        position: relative;
        box-sizing: border-box;
        height: ${hourRowHeight}px;
        min-width: 80px;
        border-width: 0 1px 1px 0;
      }
      /* Override default event-block positioning from calendar.css */
      .calendar-container .event-block.js-positioned {
        position: absolute !important;
        margin: 0 !important;
        box-sizing: border-box !important;
        overflow: hidden !important;
        min-height: 0 !important; /* Remove min-height constraint */
      }
      /* Coloring for different event types */
      .calendar-container .event-block {
        background: rgba(51, 153, 255, 0.1);
        border-left: 4px solid #3399ff;
        border-radius: 6px;
        padding: 10px 12px;
        font-size: 0.9rem;
        color: #333;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
      }
      .calendar-container .event-block.exam {
        background: rgba(239, 71, 111, 0.1);
        border-left: 4px solid #ef476f;
      }
      .calendar-container .event-block.study,
      .calendar-container .event-block.prepare {
        background: rgba(255, 209, 102, 0.1);
        border-left: 4px solid #ffd166;
      }
      .calendar-container .event-block.meeting {
        background: rgba(118, 120, 237, 0.1);
        border-left: 4px solid #7678ed;
      }
    `;
    document.head.appendChild(styleElement);
}
  
  
// Fallback simple schedule view when there is no generated_calendar
function displaySimpleSchedule(data) {
    const scheduleOutput = document.getElementById('scheduleOutput');

    // -- Meetings Section --
    if (data.schedule.meetings && data.schedule.meetings.length > 0) {
        const meetingsContainer = document.createElement('div');
        meetingsContainer.className = 'schedule-section';

        const meetingsTitle = document.createElement('h4');
        meetingsTitle.textContent = 'Events';
        meetingsContainer.appendChild(meetingsTitle);

        const meetingsList = document.createElement('ul');
        meetingsList.className = 'schedule-list';

        data.schedule.meetings.forEach(meeting => {
            const meetingItem = document.createElement('li');
            meetingItem.className = `schedule-item priority-${meeting.priority || 'medium'}`;

            const title = document.createElement('div');
            title.className = 'event-title';
            title.textContent = meeting.description;
            meetingItem.appendChild(title);

            const details = document.createElement('div');
            details.className = 'event-details';

            if (meeting.time) {
                details.innerHTML += `<span class="time">${formatTime(meeting.time)}</span>`;
            }
            if (meeting.day) {
                details.innerHTML += `<span class="day">${meeting.day}</span>`;
            }
            if (meeting.duration_minutes) {
                details.innerHTML += `<span class="duration">${meeting.duration_minutes} minutes</span>`;
            }
            if (meeting.location) {
                details.innerHTML += `<span class="location">${meeting.location}</span>`;
            }
            if (meeting.course_code) {
                details.innerHTML += `<span class="course-code">${meeting.course_code}</span>`;
            }

            meetingItem.appendChild(details);
            meetingsList.appendChild(meetingItem);
        });

        meetingsContainer.appendChild(meetingsList);
        scheduleOutput.appendChild(meetingsContainer);
    }

    // -- Tasks Section --
    if (data.schedule.tasks && data.schedule.tasks.length > 0) {
        const tasksContainer = document.createElement('div');
        tasksContainer.className = 'schedule-section';

        const tasksTitle = document.createElement('h4');
        tasksTitle.textContent = 'Tasks';
        tasksContainer.appendChild(tasksTitle);

        const tasksList = document.createElement('ul');
        tasksList.className = 'schedule-list';

        data.schedule.tasks.forEach(task => {
            const taskItem = document.createElement('li');
            taskItem.className = `schedule-item priority-${task.priority || 'medium'}`;

            const title = document.createElement('div');
            title.className = 'task-title';
            title.textContent = task.description;
            taskItem.appendChild(title);

            const details = document.createElement('div');
            details.className = 'task-details';

            if (task.time) {
                details.innerHTML += `<span class="time">${formatTime(task.time)}</span>`;
            }
            if (task.day) {
                details.innerHTML += `<span class="day">${task.day}</span>`;
            }
            if (task.duration_minutes) {
                details.innerHTML += `<span class="duration">${task.duration_minutes} minutes</span>`;
            }
            if (task.related_event) {
                details.innerHTML += `<span class="related-event">For: ${task.related_event}</span>`;
            }
            if (task.course_code) {
                details.innerHTML += `<span class="course-code">${task.course_code}</span>`;
            }

            taskItem.appendChild(details);
            tasksList.appendChild(taskItem);
        });

        tasksContainer.appendChild(tasksList);
        scheduleOutput.appendChild(tasksContainer);
    }
}

// --- HELPER FUNCTIONS ---

// Converts a time string ("HH:MM") to minutes (used for sorting)
function timeToMinutes(timeStr) {
    if (!timeStr) return 0;
    const [hours, minutes] = timeStr.split(':').map(Number);
    return hours * 60 + (minutes || 0);
}

// Formats time from "HH:MM" to a "H:MM AM/PM" format
function formatTime(time) {
    if (!time) return '';
    try {
        const [hoursStr, minutesStr] = time.split(':');
        const hours = parseInt(hoursStr, 10);
        const mins = parseInt(minutesStr, 10) || 0;
        const ampm = hours >= 12 ? 'PM' : 'AM';
        const hour12 = hours % 12 || 12;
        return `${hour12}:${mins.toString().padStart(2, '0')} ${ampm}`;
    } catch (e) {
        return time;
    }
}

// Converts a duration in minutes into a formatted string ("X hr Y min" or "X min")
function formatDuration(minutes) {
    if (!minutes) return '';
    const hrs = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hrs && mins) {
        return `${hrs} hr ${mins} min`;
    } else if (hrs) {
        return `${hrs} hr`;
    } else {
        return `${mins} min`;
    }
}

// Function to simplify event descriptions
function getSimpleEventType(event) {
    if (!event) return '';
    
    // Extract base event type
    if (event.type === 'exam') return 'Exam';
    if (event.type === 'presentation') return 'Presentation';
    if (event.type === 'meeting') return 'Meeting';
    if (event.type === 'class') return 'Class';
    if (event.type === 'lab') return 'Lab';
    if (event.type === 'workshop') return 'Workshop';
    if (event.type === 'office_hours') return 'Office Hours';
    if (event.type === 'study') return 'Study';
    if (event.type === 'exam_preparation') return 'Exam Prep';
    if (event.type === 'presentation_preparation') return 'Presentation Prep';
    if (event.type === 'meal') return event.description || 'Meal'; // Display meal description (Breakfast/Lunch/Dinner)
    if (event.type === 'task') return event.description || 'Task'; // For generic tasks
    if (event.type === 'work') return 'Work';
    if (event.type === 'research') return 'Research';
    if (event.type === 'prepare') return 'Preparation';
    
    // If the description already indicates what it is, use that directly
    if (event.description) {
        if (event.description.toLowerCase().includes('breakfast')) return 'Breakfast';
        if (event.description.toLowerCase().includes('lunch')) return 'Lunch';
        if (event.description.toLowerCase().includes('dinner')) return 'Dinner';
        
        // Get first word if it's a short description
        const firstWord = event.description.split(' ')[0];
        if (firstWord.length < 10) return event.description;
        
        // Or return full description for readability
        return event.description;
    }
    
    return 'Event';
}

// Updated resetScheduleUI function with logging
function resetScheduleUI() {
    console.log('resetScheduleUI triggered');
    fetch('/reset-schedule', {
        method: 'POST'
    })
    .then(response => {
        console.log('Reset schedule response received', response);
        // If the response is a redirect, use it; otherwise redirect to '/' manually
        if (response.redirected) {
            window.location.href = response.url;
        } else {
            window.location.href = '/';
        }
    })
    .catch(error => {
        console.error('Error resetting schedule:', error);
        alert('Error resetting schedule: ' + error.message);
    });
}
