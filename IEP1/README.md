# Task Parser (IEP1)

A natural language task parser that extracts structured information from free-form text. It identifies tasks, meetings, course codes, priorities, and deadlines.

## Features

- Extracts tasks and meetings with their priorities and times
- Identifies course codes (e.g., EECE503)
- Categorizes tasks into different types (Shopping, Cleaning, Communication, etc.)
- Performs topic analysis on tasks
- Provides a beautiful web interface for testing
- REST API endpoint for integration

## Prerequisites

- Docker and Docker Compose
- Web browser (Chrome, Firefox, Safari, or Edge)

## Quick Start

1. Clone this directory or copy all files from IEP1
2. Open a terminal in the IEP1 directory
3. Run the parser service:
   ```bash
   docker-compose up --build
   ```
4. Wait for the service to start (you'll see "Running on http://0.0.0.0:5000")
5. Open `test-interface/index.html` in your web browser
6. Start parsing tasks!

## Example Input

Try entering text like:
```
Need to finish EECE503 homework by tomorrow, attend team meeting at 3pm, 
and review ML papers before EOD. Also need to clean my room and buy groceries.
```

## Project Structure

```
IEP1/
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker Compose configuration
├── parser.py           # Main parser implementation
├── requirements.txt    # Python dependencies
└── test-interface/    # Web interface for testing
    └── index.html     # Beautiful UI for parser testing
```

## API Endpoint

The parser exposes a REST API endpoint at:
- POST `http://localhost:5000/parse-tasks`

Request body:
```json
{
    "text": "your text here"
}
```

Response format:
```json
{
    "tasks": [
        {
            "description": "task description",
            "priority": "priority level",
            "time": "deadline",
            "category": "task category"
        }
    ],
    "meetings": [
        {
            "description": "meeting description",
            "priority": "priority level",
            "time": "meeting time"
        }
    ],
    "course_codes": ["EECE503"],
    "topics": [
        {
            "id": 0,
            "terms": {"term1": 0.8, "term2": 0.6},
            "label": "Topic label"
        }
    ]
}
```

## Troubleshooting

1. If the Docker container fails to start:
   - Make sure ports 5000 is not in use
   - Try running `docker-compose down` first

2. If the web interface can't connect:
   - Verify the Docker container is running
   - Check browser console for CORS errors
   - Make sure you're using http://localhost:5000

3. If dependencies fail to install:
   - Try rebuilding with `docker-compose build --no-cache`

## Notes

- This is a development server, not suitable for production use
- The parser uses NLP techniques including:
  - Named Entity Recognition
  - Part-of-speech tagging
  - Topic modeling
  - Pattern matching 