# Lock-In Scheduling Application

This project contains a microservices-based application for scheduling and time management.

## Services

The application consists of the following services:

1. **UI** - The web interface for users to interact with the application
2. **EEP1** - External Endpoint Processor 1 - Processes schedule data and coordinates with other services
3. **IEP1** - Internal Endpoint Processor 1 - Natural language processing service using OpenAI
4. **IEP2** - Internal Endpoint Processor 2 - Advanced text generation service using Anthropic Claude

## Prerequisites

- Docker and Docker Compose
- OpenAI API key
- Anthropic API key

## Getting Started

1. Clone this repository:
```bash
git clone https://github.com/yourusername/lock-in.git
cd lock-in
```

2. Edit the `.env` file to add your API keys:
```bash
# Add your API keys to .env
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

3. Build and start the services:
```bash
docker-compose up --build
```

4. Access the application at http://localhost:5002

## Development

If you need to work on a specific service, you can build and run just that service:

```bash
# Build and run only the UI service
docker-compose up --build ui

# Build and run multiple services
docker-compose up --build ui eep1 iep1
```

## API Documentation

- UI API: http://localhost:5002
- EEP1 API: http://localhost:5000
- IEP1 API: http://localhost:5001
- IEP2 API: http://localhost:5004

## Environment Variables

The application uses the following environment variables, which can be set in the `.env` file:

- `OPENAI_API_KEY` - Your OpenAI API key
- `ANTHROPIC_API_KEY` - Your Anthropic API key
- `LLM_MODEL` - The Anthropic model to use (default: claude-3-7-sonnet-20250219)
- `EEP1_URL` - URL for the EEP1 service (used by UI)
- `IEP1_URL` - URL for the IEP1 service (used by EEP1)
- `IEP2_URL` - URL for the IEP2 service (used by EEP1)

## Architecture

The application consists of the following microservices with a clear communication flow:

- **UI**: Web interface that communicates only with EEP1
- **EEP1**: Schedule Generator API that processes schedule data and communicates with both IEP1 and IEP2
- **IEP1**: OpenAI Model Gateway for text parsing and analysis
- **IEP2**: Anthropic Claude gateway for advanced schedule optimization

Communication flow:
```
User → UI → EEP1 → IEP1/IEP2
```

## Project Structure

```
lock-in/
├── EEP1/                 # Schedule Generator API
│   ├── app.py           # Main application
│   ├── Dockerfile       # Docker configuration
│   └── requirements.txt # Python dependencies
├── IEP1/                # OpenAI Model Gateway
│   ├── parser.py        # Model interface
│   ├── Dockerfile       # Docker configuration
│   └── requirements.txt # Python dependencies
├── IEP2/                # Schedule Optimizer
│   ├── app.py           # Main application
│   ├── Dockerfile       # Docker configuration
│   └── requirements.txt # Python dependencies
├── UI/                  # Flask Frontend
│   ├── app.py           # Main application
│   ├── Dockerfile       # Docker configuration
│   └── requirements.txt # Python dependencies
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
