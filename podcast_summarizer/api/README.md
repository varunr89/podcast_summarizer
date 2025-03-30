# Podcast Summarizer API

## Architecture Overview

The API is structured into several modular components for better maintainability and separation of concerns:

```
api/
├── queue_processor.py  # Azure Service Bus integration
├── handlers.py         # Message processing handlers
├── routes.py          # FastAPI route definitions
└── main.py            # Application entry point
```

The API uses configuration from the core module:
```
core/
└── config.py          # Centralized configuration using Pydantic
```

### Component Responsibilities

1. **queue_processor.py**
   - Handles Azure Service Bus queue operations
   - Implements message dispatching logic
   - Manages message processing lifecycle

3. **main.py**
   - Initializes FastAPI application
   - Sets up route handlers
   - Configures startup events
   - Initializes queue processing

4. **handlers.py**
   - Implements message processing logic
   - Contains endpoint-specific handlers
   - Processes queue messages

## Message Flow

1. Frontend API sends messages to Azure Service Bus queue
2. QueueProcessor continuously monitors the queue
3. Messages are dispatched based on their `targetEndpoint`
4. Appropriate handler processes the message
5. Results are stored/returned as needed

## Configuration

Required environment variables:
- `SERVICE_BUS_CONNECTION_STRING`: Azure Service Bus connection string
- `SERVICE_BUS_QUEUE_NAME`: Name of the queue to process

## Usage

Start the application using uvicorn:
```bash
uvicorn podcast_summarizer.api.main:app --reload
```

The application will automatically:
1. Load configuration
2. Initialize queue processing
3. Start handling messages