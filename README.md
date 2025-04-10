# Lock-in: Schedule Generator & Course Buddy

A microservices-based application that helps students manage their academic schedules and course-related tasks.

## Architecture

The application consists of the following microservices:

- **UI**: React-based user interface for interacting with the system
- **EEP1**: Schedule Generator API (endpoints: /parse-schedule, /get-schedule)
- **IEP1**: OpenAI Model Gateway
- **IEP2**: Schedule Optimizer
- **Auth Service**: User authentication and authorization

## Prerequisites

- Docker and Docker Compose
- OpenAI API Key

## Setup

1. Clone the repository
2. Create a `.env` file with the required API key:
   ```
   OPENAI_API_KEY=your_openai_api_key
   ```
3. Build and run the services:
   ```bash
   docker-compose up --build
   ```

## Services

### UI (Port 3000)
React-based user interface that provides:
- User authentication (login/register)
- Schedule management dashboard
- Task and meeting visualization
- Schedule modification interface

### EEP1 (Port 5000)
Schedule Generator API with endpoints:
- `/parse-schedule`: Parse free-form text into structured schedule
- `/get-schedule`: Retrieve the latest stored schedule
- Handles all business logic for schedule management
- Maintains schedule state in local storage

### IEP1 (Port 5001)
OpenAI Model Gateway that:
- Provides a simple interface to OpenAI API
- Handles model calls and responses
- No business logic, only model interaction

### IEP2 (Port 5002)
Schedule Optimizer that:
- Optimizes task scheduling
- Handles task prioritization
- Manages schedule constraints

### Auth Service (Port 3002)
Authentication service that:
- Handles user registration and login
- Manages JWT tokens
- Provides protected routes

## Project Structure

```
lock-in/
├── EEP1/                 # Schedule Generator API
│   ├── app.py           # Main application
│   ├── Dockerfile.eep1  # Docker configuration
│   └── requirements.txt # Python dependencies
├── IEP1/                # OpenAI Model Gateway
│   ├── parser.py        # Model interface
│   ├── Dockerfile.iep1  # Docker configuration
│   └── requirements.txt # Python dependencies
├── IEP2/                # Schedule Optimizer
│   ├── app.py           # Main application
│   ├── optimizer.py     # Optimization logic
│   ├── scheduler.py     # Scheduling logic
│   ├── Dockerfile.iep2  # Docker configuration
│   └── requirements.txt # Python dependencies
├── UI/                  # React Frontend
│   ├── src/             # Source code
│   │   ├── components/  # React components
│   │   └── App.js       # Main application
│   ├── Dockerfile.ui    # Docker configuration
│   └── package.json     # Node dependencies
├── auth-service/        # Authentication Service
│   ├── server.js        # Main application
│   ├── Dockerfile.auth  # Docker configuration
│   └── package.json     # Node dependencies
├── docker-compose.yml   # Service orchestration
└── README.md            # Project documentation
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License
