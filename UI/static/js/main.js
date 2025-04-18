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
let userPreferences = {};
let preferencesSubmitted = false;
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
    
    // Set the question text
    document.getElementById('questionText').textContent = question.question;
    
    // Create appropriate input based on question type
    const inputContainer = document.getElementById('questionInput');
    inputContainer.innerHTML = '';
    
    if (question.type === 'time') {
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
    const questionId = document.querySelector('#questionDialog').dataset.questionId;
    const questionType = document.querySelector('#questionDialog').dataset.questionType;
    const questionTarget = document.querySelector('#questionDialog').dataset.questionTarget;
    const questionField = document.querySelector('#questionDialog').dataset.questionField;
    const questionTargetType = document.querySelector('#questionDialog').dataset.questionTargetType;

    // Get the answer from the appropriate input field
    let answer;
    if (questionType === 'time') {
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

    fetch('http://localhost:5002/answer-question', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            item_id: questionId,
            type: questionType,
            answer: answer,
            field: questionField,
            target: questionTarget,
            target_type: questionTargetType,
            schedule: currentSchedule
        }),
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
            document.getElementById('scheduleOutput').innerHTML = '<div class="info-message">Collecting your preferences to optimize the schedule...</div>';
            
            // Automatically transition to preference questions
            setTimeout(() => {
                getPreferenceQuestions();
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
    } else if (state === 'preferences') {
         header.textContent = "Gathering Your Preferences...";
    } else if (state === 'cooking') {
         header.textContent = "Cooking Your Schedule...";
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
    } else if (state === 'preferences') {
         infoText.textContent = "We are gathering your preference inputs.";
    } else if (state === 'cooking') {
         infoText.textContent = "We are cooking your schedule!";
    }
    content.appendChild(infoText);

    overlay.appendChild(content);

    // Append the overlay to the document body, covering the prompt area
    document.body.appendChild(overlay);
}

function generateSchedule() {
    const scheduleText = document.getElementById('scheduleText').value;
    if (!scheduleText.trim()) {
        alert('Please enter a schedule description');
        return;
    }

    // Reset state
    allMissingInfoResolved = false;
    preferencesSubmitted = false;

    // Get the button that was clicked to handle proper re-enabling
    const submitBtn = document.querySelector('button[onclick="generateSchedule()"]');
    submitBtn.disabled = true;
    submitBtn.innerText = 'Submitting...';
    
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
            document.getElementById('scheduleOutput').innerHTML = '<div class="info-message">Collecting your preferences to optimize the schedule...</div>';
            
            // Automatically transition to preference questions
            setTimeout(() => {
                getPreferenceQuestions();
            }, 500);
        }
        
        // Re-enable the button
        submitBtn.disabled = false;
        submitBtn.innerText = 'Generate Schedule';
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('scheduleOutput').innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
        
        // Re-enable the button
        submitBtn.disabled = false;
        submitBtn.innerText = 'Generate Schedule';
    });
}

function getPreferenceQuestions() {
    const scheduleOutput = document.getElementById('scheduleOutput');
    setLoadingState('preferences');
    
    // If currentSchedule is null, try to retrieve from localStorage
    if (!currentSchedule) {
        const storedSchedule = localStorage.getItem('currentSchedule');
        if (storedSchedule) {
            currentSchedule = JSON.parse(storedSchedule);
        } else {
            scheduleOutput.innerHTML = '<div class="error-message">Error: No schedule available</div>';
            return;
        }
    }

    // Call backend to get preference questions
    fetch('http://localhost:5002/preference-questions', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Preference questions:', data);
        if (data.preference_questions && data.preference_questions.length > 0) {
            // Show preference dialog with both preference and algorithm questions
            showPreferenceDialog(data.preference_questions, data.algorithm_questions || []);
        } else {
            // No preferences needed, generate schedule directly
            scheduleOutput.innerHTML = '<div class="info-message">No preference questions available. Generating optimized schedule...</div>';
            generateOptimizedSchedule();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        scheduleOutput.innerHTML = `<div class="error-message">Error getting preferences: ${error.message}</div>`;
    });
}

function showPreferenceDialog(preferenceQuestions, algorithmQuestions) {
    // Create a modal for preferences
    const modal = document.createElement('div');
    modal.id = 'preferenceDialog';
    modal.className = 'dialog';
    
    const allQuestions = [...preferenceQuestions, ...algorithmQuestions];
    
    const content = document.createElement('div');
    content.className = 'dialog-content';
    content.innerHTML = `
        <h2>Schedule Preferences</h2>
        <p>Please set your preferences for schedule generation:</p>
        <form id="preferenceForm">
            ${allQuestions.map(q => createPreferenceInput(q)).join('')}
            <div class="dialog-buttons">
                <button type="button" onclick="cancelPreferences()">Cancel</button>
                <button type="button" onclick="submitPreferences()">Generate Schedule</button>
            </div>
        </form>
    `;
    
    modal.appendChild(content);
    document.body.appendChild(modal);
}

function cancelPreferences() {
    const dialog = document.getElementById('preferenceDialog');
    if (dialog) {
        document.body.removeChild(dialog);
    }
}

function submitPreferences() {
    const form = document.getElementById('preferenceForm');
    if (!form) {
        console.error('Preference form not found');
        return;
    }
    
    const formData = new FormData(form);
    const preferences = {};
    
    // Convert form data to preferences object
    for (const [key, value] of formData.entries()) {
        if (key.includes('include_weekend') || key.includes('boolean')) {
            preferences[key] = value === 'true';
        } else if (!isNaN(value) && value !== '') {
            preferences[key] = Number(value);
        } else {
            preferences[key] = value;
        }
    }
    
    console.log('Collected preferences:', preferences);
    userPreferences = preferences;
    
    // Display message while submitting
    const scheduleOutput = document.getElementById('scheduleOutput');
    scheduleOutput.innerHTML = '<div class="info-message">Submitting preferences and generating your optimized schedule...</div>';
    
    // Close dialog
    cancelPreferences();
    
    // Generate optimized schedule 
    setTimeout(() => {
        generateOptimizedSchedule();
    }, 300);
}

// --- UPDATED generateOptimizedSchedule ---
// --- UPDATED generateOptimizedSchedule ---
function generateOptimizedSchedule() {
    const scheduleOutput = document.getElementById('scheduleOutput');
    setLoadingState('cooking');
    
    fetch('/generate-optimized-schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            schedule: currentSchedule,
            preferences: userPreferences
        }),
    })
    .then(response => {
        if (!response.ok) throw new Error(`HTTP error ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (!data.schedule) throw new Error('No schedule data received');
        currentSchedule = data.schedule;
        localStorage.setItem('currentSchedule', JSON.stringify(currentSchedule));
        // redirect to standalone schedule view
        window.location.href = '/schedule-only';
    })
    .catch(error => {
        console.error('Error:', error);
        scheduleOutput.innerHTML = `<div class="error-message">Error generating schedule: ${error.message}</div>`;
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
    if (!isFinite(minTime)) [minTime, maxTime] = [9,17];
    const startHour = Math.floor(minTime);
    const endHour   = Math.ceil(maxTime);
  
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
      });
    }
  
    // 5) events - Create events and position them correctly with CSS grid
    days.forEach((day, di) => {
      const dayEvents = schedule.generated_calendar[day] || [];
      
      dayEvents.forEach(ev => {
        // Parse times
        const [sh, sm] = ev.start_time.split(':').map(Number);
        const [eh, em] = ev.end_time.split(':').map(Number);
        
        // Calculate grid row positions
        const startRow = (sh - startHour) + (sm / 60) + 2;
        const endRow = (eh - startHour) + (em / 60) + 2;
        
        // Format time for display
        const startLabel = formatTime(ev.start_time).replace(':00','').replace(' ','');
        const endLabel = formatTime(ev.end_time).replace(':00','').replace(' ','');
        const title = `${startLabel}–${endLabel}`;
        
        // Get simplified event description
        const simpleDescription = getSimpleEventType(ev);
        
        // Create the event element
        const eventElement = document.createElement('div');
        eventElement.className = 'event-block';
        
        // Add event type as a class if available
        if (ev.type) {
          eventElement.classList.add(ev.type.toLowerCase());
        }
        
        // Build the HTML content
        eventElement.innerHTML = `
          <div><strong>${title}</strong></div>
          <div>${simpleDescription}</div>
          ${ev.course_code ? `<div class="course-code">${ev.course_code}</div>` : ''}
        `;
        
        // Position using grid
        eventElement.style.gridColumnStart = di + 2; // +2 for time label column
        eventElement.style.gridColumnEnd = di + 3;
        eventElement.style.gridRowStart = startRow;
        eventElement.style.gridRowEnd = endRow;
        
        // Add to the container
        container.appendChild(eventElement);
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
      .calendar-container .event-block {
        position: relative !important;
        background: rgba(51, 153, 255, 0.1);
        border-left: 4px solid #3399ff;
        border-radius: 6px;
        padding: 10px 12px;
        font-size: 0.9rem;
        color: #333;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        margin: 2px;
        z-index: 10;
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

// --- ORIGINAL createPreferenceInput FUNCTION ---
// This function is kept unchanged from your version.
function createPreferenceInput(question) {
    let inputHtml = '';
    
    switch (question.type) {
        case 'time':
            // Convert default value (if any) to input format
            let defaultTime = question.default || '';
            if (defaultTime && defaultTime.includes(':')) {
                const [hours, minutes] = defaultTime.split(':');
                defaultTime = `${hours.padStart(2, '0')}:${minutes.padStart(2, '0')}`;
            }
            
            inputHtml = `
                <div class="form-group">
                    <label for="${question.id}">${question.text}</label>
                    <input type="time" id="${question.id}" name="${question.id}" value="${defaultTime}">
                </div>
            `;
            break;
            
        case 'single_choice':
            inputHtml = `
                <div class="form-group">
                    <label>${question.text}</label>
                    <select id="${question.id}" name="${question.id}">
                        ${question.options.map(option => 
                            `<option value="${option.value}" ${question.default === option.value ? 'selected' : ''}>${option.text}</option>`
                        ).join('')}
                    </select>
                </div>
            `;
            break;
            
        case 'boolean':
            inputHtml = `
                <div class="form-group">
                    <label>${question.text}</label>
                    <div class="radio-group">
                        <label>
                            <input type="radio" name="${question.id}" value="true" ${question.default ? 'checked' : ''}>
                            Yes
                        </label>
                        <label>
                            <input type="radio" name="${question.id}" value="false" ${!question.default ? 'checked' : ''}>
                            No
                        </label>
                    </div>
                </div>
            `;
            break;
            
        case 'number':
            inputHtml = `
                <div class="form-group">
                    <label for="${question.id}">${question.text}</label>
                    <input type="number" id="${question.id}" name="${question.id}" 
                        min="${question.min || 0}" max="${question.max || 100}" value="${question.default || ''}">
                </div>
            `;
            break;
            
        default:
            inputHtml = `
                <div class="form-group">
                    <label for="${question.id}">${question.text}</label>
                    <input type="text" id="${question.id}" name="${question.id}" value="${question.default || ''}">
                </div>
            `;
    }
    
    return inputHtml;
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
    
    // If no specific type, extract a short description from the event's description field
    if (event.description) {
        // Get first word if it's a short description
        const firstWord = event.description.split(' ')[0];
        if (firstWord.length < 10) return firstWord;
        
        // Or return first 10 chars if it's a long word/phrase
        return event.description.substring(0, 10) + '...';
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
