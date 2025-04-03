# Lock-in: Schedule Generator & Course Buddy

A microservices-based application that helps students manage their academic schedules and course-related tasks.

## Architecture

The application consists of the following microservices:

- **UI**: User interface for interacting with the system
- **EEP1**: Schedule Generator API (endpoints: /parse-tasks, /compile-schedule, /sync-calendar)
- **IEP1**: Task Parser and Modification Processor
- **IEP2**: Schedule Compiler and Prioritizer
- **Calendar Sync**: External Calendar System Integration

## Prerequisites

- Docker and Docker Compose
- OpenAI API Key
- Google Calendar API Key (optional)
- Outlook API Key (optional)

## Setup

1. Clone the repository
2. Create a `.env` file with the required API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key
   GOOGLE_CALENDAR_API_KEY=your_google_calendar_api_key
   OUTLOOK_API_KEY=your_outlook_api_key
   ```
3. Build and run the services:
   ```bash
   docker-compose up --build
   ```

## Services

### UI (Port 3000)
The main user interface for interacting with the system.

### EEP1 (Port 5000)
Schedule Generator API with endpoints:
- `/parse-tasks`: Parse free-form text into structured tasks
- `/compile-schedule`: Generate optimized schedules
- `/sync-calendar`: Sync with external calendars

### IEP1 (Port 5001)
Task Parser service that:
- Extracts tasks, meetings, and course codes
- Processes modification prompts
- Maintains the latest schedule state

### IEP2 (Port 5002)
Schedule Compiler that:
- Generates optimized, time-ordered schedules
- Incorporates MCQ feedback
- Handles schedule modifications

### Calendar Sync (Port 5003)
Handles synchronization with external calendar systems:
- Google Calendar
- Outlook Calendar
- iCloud Calendar

### Monitoring
- Prometheus (Port 9090)
- Grafana (Port 3001)

## Testing

Each service includes its own test suite. Run tests for individual services:

```bash
# For IEP1
cd IEP1 && python -m pytest tests/

# For IEP2
cd IEP2 && python -m pytest tests/

# For Calendar Sync
cd CalendarSync && python -m pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License
