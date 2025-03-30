# GUI Command Creator for Podcast Summarizer Testing (Updated)

This document describes the design and usage of a new GUI Command Creator tool that serves as a command generator rather than an executor. The goal is to allow you to select which parameters to include (using checkboxes) and provide values next to each parameter. The GUI will then craft a complete terminal command based on your selections and inputs. You can copy and paste the generated command into your terminal for execution.

---

## Features

- **GUI Layout Similar to Original GUI Wrapper:**  
  The interface resembles the original GUI wrapper but its sole purpose is to generate a command without executing it.

- **Parameter Selection:**  
  Next to each parameter, there is a checkbox. Only the parameters that are selected (checkbox ticked) will be included in the generated command. Each parameter also has a text field where you can provide its value. This helps in dynamically including or omitting parameters from the command.

- **Test Environment Choice:**  
  You can choose whether the command should be generated for a Local Source test (direct Python execution) or for a Local Container test (Docker execution).  
  - **Local Source:** Generates a command like:  
    ```
    python src/api_test.py --test-summarize --user-id "YOUR_USER_ID" --episode-id "YOUR_EPISODE_ID" --feed-url "YOUR_FEED_URL" [Other Flags...]
    ```
  - **Local Container:** Generates a command like:  
    ```
    docker run -it --rm --env-file "src/.env" podcast_summarizer bash -c "uvicorn src/podcast_summarizer.api.main:app --host 0.0.0.0 --port 80 & sleep 3 && python src/api_test.py --test-summarize --user-id \"YOUR_USER_ID\" --episode-id \"YOUR_EPISODE_ID\" --feed-url \"YOUR_FEED_URL\" [Other Flags...]"
    ```

- **Test Type Selection:**  
  A drop-down menu allows you to select the test type (process, summarize, upsert, email, episode_email). The appropriate test flag (e.g., `--test-summarize`) is automatically added.

- **Extra Parameters Field:**  
  In addition to standard parameters, an extra field is provided so you can manually type additional command-line flags if needed.

- **Command Preview:**  
  Once you click the "Generate Command" button, the full command string is displayed in a non-editable text area for you to copy and paste.

---

## Example Layout

Below is an outline of the GUI components:

1. **Test Environment Section:**  
   - Radio buttons for "Local Source" and "Local Container"

2. **Test Type Selection:**  
   - A drop-down to choose among: process, summarize, upsert, email, episode_email.

3. **Parameters Section:**  
   For each parameter, there are:
   - **Checkbox:** Select whether to include the parameter.
   - **Label:** Parameter name.
   - **Text Field:** Enter the value.
   
   Example parameters include:
   - **Feed URL**
   - **User ID**
   - **Episode ID**
   - _Other parameters_ (e.g., limit-episodes, episode-indices, custom-prompt, chunk-size, etc.)

4. **Extra Parameters:**  
   - A text entry field for any additional flags.

5. **Generate Command Button:**
   - On clicking, the GUI gathers all selected parameters and constructs the terminal command accordingly.

6. **Command Preview Display:**  
   - A scrollable text area shows the complete command ready to be copied.

---

## How It Works

1. **Input Collection:**  
   The GUI collects the following:
   - Selected environment (Local Source or Local Container)
   - Selected test type (with corresponding test flag)
   - For each parameter, whether its checkbox is checked and the provided value.
   - Extra parameters (if any).

2. **Command Generation:**  
   - The tool constructs the command-line string by concatenating the base command with the parameters that were checked.
   - For Local Source: The base command is `python src/api_test.py`
   - For Local Container: The base command is wrapped in a Docker command that includes launching the server and executing the command inside the container.
   - All parameter values are appropriately quoted to handle spaces.

3. **Output:**  
   - The final command is displayed in a non-editable text area.
   - You can then copy the command and run it in your terminal.

---

## Usage Instructions

1. Run the Command Creator GUI (provided as a separate Python script).
2. Select the desired test environment and test type.
3. Check the boxes for the parameters you wish to include and enter their corresponding values.
4. Optionally, add any extra parameters manually.
5. Click the **Generate Command** button.
6. Copy the displayed command and paste it into your terminal for execution.

---

This updated design streamlines the process by serving purely as a command generator, reducing complexity and allowing you full control over testing via manual command execution.

---

*End of Document*