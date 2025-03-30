# Updated Architecture (v2) for Test Execution

This document describes the revised design for executing tests for the podcast summarizer. In this approach, the test wrappers (for both local source code and container tests) will be simplified. The wrapper will:

1. **Construct a Full Command String:**
   - **Local Source Tests:**  
     Build a command string that directly invokes `python src/api_test.py` with all the necessary command-line flags and parameters.
     
     *Example Command:*  
     ```
     python src/api_test.py --test-episode-email --user-id YOUR_USER_ID --episode-id YOUR_EPISODE_ID [other flags...]
     ```

   - **Local Container Tests:**  
     Build a Docker command string that mounts the `.env` file, starts the container, and then runs the same command inside the container.  
     
     *Example Command:*  
     ```
     docker run -it --rm --env-file src/.env podcast_summarizer /bin/bash -c "uvicorn src.podcast_summarizer.api.main:app --host 0.0.0.0 --port 80 & sleep 3 && python src/api_test.py --test-episode-email --user-id YOUR_USER_ID --episode-id YOUR_EPISODE_ID [other flags...]"
     ```

2. **Execution and Logging:**
   - **Print the Full Command:**  
     Before execution, the wrapper will print the full command string to the terminal. This makes it explicit what will be executed and aids debugging.
     
   - **Execute the Command:**  
     The wrapper will then use a method such as `subprocess.run` or `os.system` to execute the constructed command. Command execution should capture both standard output and standard error.
     
   - **Log Output and Errors:**  
     After execution, the wrapper will print the captured standard output and error logs to the terminal. This enables developers to see why a test may have failed.

3. **Error Handling:**
   - If the command fails (non-zero exit code) or an exception occurs during execution, the wrapper will log:
     - The full command that was attempted,
     - The error message (from standard error or exception details),
     - Any additional context to aid in debugging.
     
4. **Unified Behavior Across Environments:**
   - The same parameter set and command-building logic will be used for both local source execution and container tests. The only difference is that for container tests, the command string is wrapped in a Docker command.
   - This ensures consistent behavior and reduces variance between environments.

## Advantages of the Revised Design

- **Transparency:**  
  Developers can see the exact command being executed, which helps in diagnosing issues.

- **Simplification:**  
  By eliminating additional layers of function calls, the approach is simpler and less prone to internal errors.

- **Consistent Logging:**  
  Both successful executions and errors are logged with full details, allowing quick troubleshooting.

- **Ease of Maintenance:**  
  With a single method to build command strings and execute them, future changes to test parameters or execution logic can be easily integrated.

## Implementation Guidelines

- **For Local Source Tests:**
  - Gather parameters from the GUI or input source.
  - Construct the command string (e.g., `python src/api_test.py --...`).
  - Print the command string to the console.
  - Execute the command using `subprocess.run(..., capture_output=True, text=True)`.
  - Print the output and error streams.

- **For Local Container Tests:**
  - Follow the same steps to construct the command for `api_test.py`.
  - Wrap this command inside a Docker run command that mounts the `.env` file.
  - Print the full Docker command.
  - Execute the Docker command and capture its output.
  - Print the resulting logs.

## Conclusion

This updated architecture (v2) ensures that:
- The execution process is fully transparent,
- Errors are logged in detail,
- Both local and container-based testing share identical behavior apart from the environment-specific command prefixes,
- Developers can easily debug issues by reviewing the printed command and output logs.

Implementing this architecture will involve updating the test wrapper modules (`tests/local_tests.py` and `tests/container_tests.py`) to follow the guidelines above.