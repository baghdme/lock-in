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

function showQuestionDialog(questions) {
    currentQuestions = questions;
    currentQuestionIndex = 0;
    showNextQuestion();
}

function showNextQuestion() {
    if (currentQuestionIndex >= currentQuestions.length) {
        closeDialog();
        return;
    }

    const question = currentQuestions[currentQuestionIndex];
    document.getElementById('questionText').textContent = `Question ${currentQuestionIndex + 1} of ${currentQuestions.length}: ${question.question}`;
    
    const inputDiv = document.getElementById('questionInput');
    inputDiv.innerHTML = '';
    
    if (question.type === 'time') {
        inputDiv.innerHTML = '<input type="time" id="answerInput" required>';
    } else if (question.type === 'duration') {
        inputDiv.innerHTML = '<input type="number" id="answerInput" min="1" placeholder="Duration in minutes" required>';
    } else if (question.type === 'course_code') {
        inputDiv.innerHTML = '<input type="text" id="answerInput" placeholder="Enter course code (e.g. EECE503)" required pattern="[A-Z]{4}[0-9]{3}">';
    } else {
        inputDiv.innerHTML = '<input type="text" id="answerInput" placeholder="Enter your answer" required>';
    }

    document.getElementById('answerInput').focus();
    document.getElementById('questionDialog').classList.remove('hidden');
}

function submitAnswer() {
    const answerInput = document.getElementById('answerInput');
    if (!answerInput.checkValidity()) {
        if (answerInput.validity.valueMissing) {
            alert('Please provide an answer');
        } else if (answerInput.validity.patternMismatch) {
            alert('Please enter a valid course code (e.g. EECE503)');
        }
        return;
    }

    const answer = answerInput.value;
    const question = currentQuestions[currentQuestionIndex];
    let formattedAnswer = answer;
    
    if (question.type === 'time') {
        try {
            const [hours, minutes] = answer.split(':');
            const hour = parseInt(hours);
            const ampm = hour >= 12 ? 'PM' : 'AM';
            const hour12 = hour % 12 || 12;
            formattedAnswer = `${hour12}:${minutes} ${ampm}`;
        } catch (error) {
            console.error('Error formatting time:', error);
            alert('Please enter a valid time');
            return;
        }
    }

    const submitButton = document.querySelector('button[onclick="submitAnswer()"]');
    const originalText = submitButton.textContent;
    submitButton.disabled = true;
    submitButton.textContent = 'Submitting...';

    // Try to get the schedule from localStorage if currentSchedule is null
    if (!currentSchedule) {
        try {
            const storedSchedule = localStorage.getItem('currentSchedule');
            if (storedSchedule) {
                currentSchedule = JSON.parse(storedSchedule);
                console.log('Retrieved schedule from localStorage:', currentSchedule);
            }
        } catch (e) {
            console.warn('Failed to retrieve schedule from localStorage:', e);
        }
    }

    // Log the current state
    console.log('Current schedule before submit:', currentSchedule);
    console.log('Submitting answer for question:', question);

    const requestData = {
        item_id: question.target_id,
        type: question.type,
        answer: formattedAnswer,
        field: question.field,
        target: question.target,
        target_type: question.target_type,
        schedule: currentSchedule
    };

    console.log('Sending answer request:', requestData);

    fetch('http://localhost:5002/answer-question', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                try {
                    const jsonError = JSON.parse(text);
                    throw new Error(jsonError.error || jsonError.details || 'Server error');
                } catch (e) {
                    console.error('Server response:', text);
                    throw new Error('Server error - please check the logs');
                }
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Received answer response:', data);
        
        if (data.schedule) {
            currentSchedule = data.schedule;
            console.log('Updated schedule after answer:', currentSchedule);

            // Update localStorage with new schedule
            try {
                localStorage.setItem('currentSchedule', JSON.stringify(currentSchedule));
                console.log('Updated schedule in localStorage');
            } catch (e) {
                console.warn('Failed to update schedule in localStorage:', e);
            }
        }
        
        if (data.success) {
            currentQuestionIndex++;
            if (currentQuestionIndex >= currentQuestions.length) {
                closeDialog();
                displaySchedule({ schedule: currentSchedule });
            } else {
                showNextQuestion();
            }
        } else {
            throw new Error(data.error || 'Unknown error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error submitting answer: ' + error.message);
    })
    .finally(() => {
        submitButton.disabled = false;
        submitButton.textContent = originalText;
    });
}

function closeDialog() {
    document.getElementById('questionDialog').classList.add('hidden');
    currentQuestions = [];
    currentQuestionIndex = 0;
}

function generateSchedule() {
    const scheduleText = document.getElementById('scheduleText').value;
    if (!scheduleText) {
        alert('Please enter schedule details');
        return;
    }

    console.log('Sending schedule text:', scheduleText);

    fetch('http://localhost:5002/parse-schedule', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: scheduleText })
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                try {
                    const jsonError = JSON.parse(text);
                    throw new Error(jsonError.error || 'Server error');
                } catch (e) {
                    console.error('Server response:', text);
                    throw new Error('Server error - please check the logs');
                }
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Received parse response:', data);
        
        if (data.schedule) {
            currentSchedule = data.schedule;
            console.log('Stored schedule:', currentSchedule);

            // Store the schedule in localStorage as backup
            try {
                localStorage.setItem('currentSchedule', JSON.stringify(currentSchedule));
                console.log('Stored schedule in localStorage');
            } catch (e) {
                console.warn('Failed to store schedule in localStorage:', e);
            }
        } else {
            console.warn('No schedule in response');
            throw new Error('No schedule received from server');
        }
        
        if (data.questions && data.questions.length > 0) {
            console.log('Questions received:', data.questions);
            currentQuestions = data.questions;
            showQuestionDialog(data.questions);
        } else {
            console.log('No questions to answer');
            displaySchedule(data);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error generating schedule: ' + error.message);
    });
}

async function modifySchedule() {
    const scheduleText = document.getElementById('scheduleText').value;
    if (!scheduleText) {
        alert('Please enter your schedule text');
        return;
    }

    try {
        const response = await fetch('http://localhost:5002/modify-schedule', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: scheduleText })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        displaySchedule(data);
    } catch (error) {
        console.error('Error:', error);
        alert('Error modifying schedule: ' + error.message);
    }
}

async function getSchedule() {
    try {
        const response = await fetch('http://localhost:5002/get-schedule', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        displaySchedule(data);
    } catch (error) {
        console.error('Error:', error);
        alert('Error getting schedule: ' + error.message);
    }
}

function displaySchedule(data) {
    document.getElementById('scheduleOutput').innerHTML = 
        `<pre>${JSON.stringify(data, null, 2)}</pre>`;
} 