# Podcast Summarizer Test Package

A comprehensive test package for the podcast summarizer, supporting both local and container-based testing with a GUI interface.

## Features

### Test Environments
- **Local Source Code:** Direct testing using Python source code
- **Local Container:** Testing using Docker container
- **Cloud Container:** Testing using cloud-based container (future implementation)

### Test Types
1. **Process Podcast**
   - Process podcasts from RSS feed
   - Configure episode limits and indices
   - Set split size and transcription options

2. **Summarize Episode**
   - Test episode summarization
   - Multiple summarization methods
   - Configurable chunk sizes and overlap
   - Adjustable detail levels

3. **Upsert Podcast**
   - Test podcast creation/update
   - Multiple parser types
   - Custom descriptions

4. **Email Tests**
   - User email summaries
   - Individual episode summaries

### Parameters
#### Common Parameters
- `feed_url`: RSS feed URL
- `user_id`: User identifier
- `episode_id`: Specific episode identifier

#### Process Options
- `episode_indices`: Specify episodes (e.g., "1,2,3-5")
- `limit_episodes`: Maximum episodes to process
- `split_size_mb`: Split size in megabytes
- `include_transcription`: Enable/disable transcription

#### Summarization Options
- `custom_prompt`: Custom summarization prompt
- `chunk_size`: Text chunk size
- `chunk_overlap`: Overlap between chunks
- `method`: Summarization method (auto/langchain/llamaindex/spacy/ensemble)
- `detail_level`: Summary detail (brief/standard/detailed)
- `temperature`: LLM temperature parameter

#### Upsert Options
- `description`: Podcast description
- `parser_type`: Parser selection (auto/rss/crawler)

## Environment Setup

1. **Required Environment Variables**
   Create a `.env` file in the `src` directory with:

   ```ini
   # Azure Whisper API Configuration
   WHISPER_API_KEY=your_whisper_api_key
   WHISPER_ENDPOINT=your_whisper_endpoint
   WHISPER_DEPLOYMENT_NAME=your_deployment_name
   WHISPER_API_VERSION=your_api_version

   # Supabase Configuration
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key

   # DeepSeek Configuration
   DEEPSEEK_API_KEY=your_deepseek_api_key
   DEEPSEEK_ENDPOINT=your_deepseek_endpoint
   DEEPSEEK_MODEL=your_model_name
   DEEPSEEK_API_VERSION=your_api_version

   # Azure Storage Configuration
   AZURE_STORAGE_CONNECTION_STRING=your_storage_connection_string
   AZURE_STORAGE_CONTAINER_NAME=your_container_name
   AZURECONNECTIONSTRING=your_connection_string

   # Email Configuration
   SENDER_EMAIL=your_sender_email
   RECEIVER_EMAIL=your_receiver_email

   # Embeddings Configuration
   EMBEDDINGS_API_KEY=your_embeddings_api_key
   EMBEDDINGS_ENDPOINT=your_embeddings_endpoint
   EMBEDDINGS_MODEL=your_embeddings_model
   ```

2. **Dependencies**
   - Python 3.8+
   - Docker (for container testing)
   - Required Python packages (install via requirements.txt)

## Usage

### GUI Interface

```bash
python -m tests.gui_wrapper
```

1. **Select Test Environment**
   - Choose between Local Source, Local Container, or Cloud API
   - Environment validation occurs automatically

2. **Select Tests**
   - Check the tests you want to run
   - Multiple tests can be selected

3. **Configure Parameters**
   - Fill in relevant parameters for selected tests
   - Default values are provided where applicable

4. **Run Tests**
   - Click "Run Tests" to execute
   - Results appear in the output window
   - Tests run in parallel when possible

### Programmatic Usage

```python
from tests import TestGUI, run_local_test, run_container_test

# Using the GUI
gui = TestGUI()
gui.run()

# Running local tests
success, result = run_local_test(
    test_type="summarize",
    episode_id="your-episode-id",
    user_id="your-user-id",
    method="auto",
    detail_level="standard"
)

# Running container tests
success, result = run_container_test(
    test_type="process",
    environment="docker",
    feed_url="your-feed-url",
    limit_episodes=5,
    episode_indices="1-3,5,7"
)
```

## Error Handling

- Environment validation before test execution
- Detailed error reporting for missing variables
- Input validation for numeric fields
- Graceful failure handling

## Threading

- Parallel test execution using ThreadPoolExecutor
- Real-time GUI updates
- Safe thread termination on exit

## Troubleshooting

1. **Environment Issues**
   - Verify all required variables in src/.env
   - Check for proper formatting
   - Ensure no trailing whitespace

2. **Docker Issues**
   - Verify Docker is running
   - Check image is built correctly
   - Verify .env file mounting

3. **GUI Issues**
   - Check Python version compatibility
   - Verify tkinter installation
   - Check file permissions

4. **Test Execution Issues**
   - Verify network connectivity
   - Check API endpoint accessibility
   - Validate input parameters