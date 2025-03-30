# Updated Architecture for Test Execution

This document outlines the new architecture for running local source code and container tests. The new approach aims to simplify the process by:

1. **Command-Line String Construction**:  
   The test wrapper will now be responsible for creating the complete command-line string based on input parameters. This string includes all necessary flags for invoking `api_test.py`.

2. **Terminal Execution**:  
   Instead of complex function calls, the wrapper will execute the constructed command directly in the terminal.  
   - For local source code tests, the command will be executed locally.
   - For local container tests, a Docker command will be built that mounts the environment file, starts the container, and then executes the constructed command inside that container.

3. **Logging and Error Visibility**:  
   The process will capture both standard output and standard error from the command execution.  
   - The complete command will be displayed in the terminal before execution.
   - Output logs will be printed to the terminal to aid in debugging failures.
   - Any errors encountered, such as failing to run the command or missing environment variables, will be logged clearly.

4. **Simplified Flow**:
   - **User Input**: The GUI or script gathers test parameters (e.g., feed URL, episode ID, user ID, etc.).
   - **Command Building**: Based on these parameters, a command-line string is created. For example:
     ```
     python src/api_test.py --test-episode-email --user-id YOUR_USER_ID --episode-id YOUR_EPISODE_ID
     ```
     and for Docker:
     ```
     docker run -it --rm --env-file src/.env podcast_summarizer /bin/bash -c "uvicorn src.podcast_summarizer.api.main:app --host 0.0.0.0 --port 80 & sleep 3 && python src/api_test.py --test-episode-email --user-id YOUR_USER_ID --episode-id YOUR_EPISODE_ID"
     ```
   - **Execution**: This string is then executed using terminal commands (e.g., using `os.system` or `subprocess.run` with logging).
   - **Feedback**: The output and error logs are directly shown in the terminal so that developers can diagnose any issues immediately.

5. **Benefits**:
   - **Simplicity**: The approach removes the extra layer of function calls, reducing potential points of failure.
   - **Transparency**: Viewing the full command line and its output helps in understanding exactly what is executed.
   - **Consistent Behavior**: Both local and container tests behave similarly, differing only in the execution environment.

## Next Steps

- **Implementation**:  
  Update the test wrapper modules (`tests/local_tests.py` and `tests/container_tests.py`) to reflect this new design.  
  Ensure that the code:
  - Constructs the command-line string based on user inputs.
  - Executes the string directly.
  - Captures and logs both standard output and errors.

- **Testing**:  
  Validate this new approach by:
  - Running tests in the local environment.
  - Running tests in the container environment via Docker.
  - Verifying that the full command and output are displayed in the terminal.
