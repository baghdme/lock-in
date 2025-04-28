# Lock-in: Productivity at Your Fingertips

## Overview
Lock-in is an intelligent scheduling application designed specifically for students. It transforms scattered thoughts into a personalized, conflict-free, Google-integrated weekly schedule in seconds. Developed by Mohamad Baghdadi and Reind Ballout for EECE 503N.

## Problem Statement
Students often struggle with time management, especially during critical periods:
- Exam preparation
- Last-minute panic
- Missed deadlines

Lock-in addresses these challenges by providing an intelligent, cognitive science-based scheduling system.

## Features
- **Instant Schedule Generation**: Convert unstructured text into optimized weekly schedules
- **Google Calendar Integration**: Import existing events and export generated schedules
- **Cognitive Science-Based Scheduling**: Applies proven principles for optimal task allocation
- **Chatbot Interface**: Natural language interactions to adjust and refine schedules
- **Personalization**: Adapts to individual productivity patterns and preferences

## Architecture
Lock-in follows a microservices architecture with the following components:

### UI (User Interface)
- Schedule inputs and visualization
- Calendar and list views
- Interactive follow-up questions
- User authentication and preference management

### EEP1 (Orchestrator)
- Central scheduling orchestration service
- Identifies missing information and generates follow-up questions
- Applies scheduling business logic and validation rules
- Manages schedule state and data persistence

### IEP1 (Parser)
- Parses user's schedule text into structured data
- Extracts meetings, tasks, and course information
- Analyzes scheduling constraints
- Processes various time formats

### IEP2 (Scheduler)
- Generates optimized weekly schedules
- Applies cognitive science principles for task allocation
- Balances task priorities, durations, and constraints
- Respects user preferences and productivity patterns

### IEP3 (Google Calendar)
- Implements OAuth authorization flow
- Imports existing calendar events as fixed commitments
- Exports generated schedules to Google Calendar

### IEP4 (Chatbot)
- Enables natural language instructions to adjust schedules
- Maintains conversational context for follow-up commands
- Persists user edits and preferences for future personalization
- Provides each user with a personalized experience

## Deployment
The application is containerized using Docker with the following setup:
- Docker Compose for orchestrating services
- Monitoring with Grafana and Prometheus
- SQLite Cloud for database storage
- MiniKube for Kubernetes deployment

## Getting Started
1. Clone the repository
2. Set up environment variables:
   - `OPENAI_API_KEY`: For IEP1 parser service
   - `ANTHROPIC_API_KEY`: For IEP2 scheduler and IEP4 chatbot services
   - `LLM_MODEL`: Model selection for LLM-based services (defaults to claude-3-7-sonnet)
3. Run `docker-compose up` to start all services
4. Access the web interface at http://localhost:5002

## Testing
The application includes:
- API testing
- Health check endpoints
- Debug logging
- Unit testing
- Integration testing

## Comparison with Other Tools
Unlike general workspace tools like Notion, Lock-in is:
- Specialized for scheduling (vs. general workspace management)
- Targeted specifically at students
- Focused on cognitive preference adaptation
- Designed for intelligently optimized schedules using LLMs
- Deeply integrated with Google Calendar

## Project Status
This project was developed as part of EECE 503N coursework. 