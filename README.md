# Podcast Summarizer

This project provides a modular framework for downloading podcast episodes, transcribing audio and producing text summaries using modern LLM based techniques.  A FastAPI service exposes the core functionality while a set of utilities and test helpers assist in running the system locally or inside containers.

## Repository layout

```
├── podcast_summarizer/           # Main package
│   ├── api/                      # FastAPI application and queue processor
│   ├── core/                     # Configuration, storage and shared logic
│   ├── processors/               # Downloaders, transcription and summarization helpers
│   └── services/                 # Business level services
├── tests/                        # Test utilities and example GUI wrappers
├── api_test.py                   # Example command line client
├── podcast_summarizer_gui.py     # Optional Tkinter GUI
├── requirements.txt              # Python dependencies
└── pytest.ini                    # Test configuration
```

The package is duplicated under `src/` to support using the code as a module without changing the existing layout.

## Installation

1. Create a Python virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Create an `.env` file in the project root and provide the necessary configuration values.  The most common variables are shown below.  See `tests/README.md` for a full list.

```ini
WHISPER_API_KEY=your_whisper_api_key
WHISPER_ENDPOINT=https://your-whisper-endpoint
WHISPER_DEPLOYMENT_NAME=whisper-deployment
SUPABASE_URL=https://your-supabase
SUPABASE_KEY=your_supabase_key
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_ENDPOINT=https://your-deepseek-endpoint
DEEPSEEK_MODEL=deepseek-model
SERVICE_BUS_CONNECTION_STRING=connection_string
SERVICE_BUS_QUEUE_NAME=queue
SENDER_EMAIL=example@example.com
RECEIVER_EMAIL=receiver@example.com
```

## Running the API

Start the FastAPI application with Uvicorn:

```bash
uvicorn podcast_summarizer.api.main:app --reload
```

The service will start a queue processor using the provided Service Bus configuration and expose REST endpoints such as `/process-podcast` and `/summarize-episode`.

## Example usage

A simple command line client is provided in `api_test.py` to demonstrate the API:

```bash
python api_test.py --help
```

This script loads the environment from `.env` and sends requests to the local API.  A GUI version is available in `podcast_summarizer_gui.py` and additional helper scripts reside in the `tests/` folder.

## Development and testing

Unit tests can be executed with `pytest`:

```bash
pytest
```

Some tests require optional dependencies or local services to be running.  Refer to the documents in the `tests/` directory for more details on the testing architecture and available options.

