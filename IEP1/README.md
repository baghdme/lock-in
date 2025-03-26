# IEP1 - Task Parser Service

A Flask-based service that uses OpenAI's GPT-3.5 to parse natural language task descriptions into structured data. Part of the Intelligent Educational Planner (IEP) project, this service (IEP1) extracts tasks, meetings, course codes, and other relevant information from text input.

## Features

- Natural language task parsing
- Automatic extraction of:
  - Tasks with priorities and categories
  - Meetings with locations and durations
  - Course codes
  - Time and duration information
- RESTful API endpoint
- Web-based testing interface

## Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- OpenAI API key

### Environment Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

### Running with Docker

1. Build and start the container:
   ```bash
   docker-compose up --build -d
   ```

2. The service will be available at:
   - API: http://localhost:5000
   - Test Interface: http://localhost:5000/test-interface

### Running Tests

Inside the Docker container:
```bash
docker exec iep1-parser-1 run-tests
```

## API Usage

### Parse Tasks Endpoint

```bash
POST /parse-tasks
Content-Type: application/json

{
    "text": "Your task description here"
}
```

Example response:
```json
{
    "tasks": [
        {
            "description": "task description",
            "priority": "high/medium/low",
            "time": "HH:MM",
            "duration_minutes": 60,
            "category": "category",
            "is_fixed_time": false,
            "location": "location",
            "prerequisites": [],
            "course_code": "EECE503"
        }
    ],
    "meetings": [...],
    "course_codes": [...],
    "topics": [...]
}
```

### Health Check

```bash
GET /health
```

## Time Format Requirements

- All times are in 24-hour format with leading zeros (HH:MM)
- Examples:
  - "9am" → "09:00"
  - "2:30pm" → "14:30"
  - "noon" → "12:00"
  - "midnight" → "00:00"

## Duration Format

- All durations are converted to integer minutes
- Examples:
  - "1 hour" → 60
  - "2.5 hours" → 150
  - "45 mins" → 45
  - "1 hour 30 mins" → 90

## Development

### Project Structure

```
IEP1/                 # Root directory
├── parser.py         # Main parser implementation
├── requirements.txt  # Python dependencies
├── Dockerfile       # Docker configuration
├── docker-compose.yml # Docker Compose configuration
├── tests/          # Test suite
└── test-interface/ # Web-based testing interface
```

### Adding New Features to IEP1

1. Update the parser system message in `parser.py`
2. Add corresponding test cases in `tests/test_parser.py`
3. Update the test interface if needed

## Contributing to IEP1

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request 