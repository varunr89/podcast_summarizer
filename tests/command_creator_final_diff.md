# Diff Instructions for Final Updates to Command Creator

Below are the modifications to add "test email" and "test user email" options and to pre-check required parameters based on the selected test type. These changes should be applied to the command creator implementation (in tests/command_creator.py).

---

## 1. Add Test Email and Test Episode Email Options

- **GUI Test Type Selection:**
  - Extend the list of test types in the GUI to include "email" and "episode_email".  
    Example list becomes: `["process", "summarize", "upsert", "email", "episode_email"]`.

- **Parameter Pre-checks:**
  - When a specific test type is selected, pre-check the parameters that are required for that test:
    - **Upsert Test:** Automatically check the "feed-url" parameter.  
      *Implementation:* In the section where test type is handled (e.g., using an event handler for changes in the test type radio buttons), if the selected test type is "upsert", set the checkbox for "feed-url" to checked.
    - **Email Test (User Email):** When test type is "email", pre-check the parameters that must be passed, such as "user-id".
    - **Episode Email Test:** When test type is "episode_email", pre-check parameters like "user-id" and "episode-id".

  - These changes require adding a callback to the test type selection widget to update the state of the parameter check boxes accordingly.

---

## 2. Modify Parameter Retrieval

- When building the API test command (inside the `build_api_test_command` or similar routine in the command creator),
  ensure that parameters selected via checkboxes are included only if they are checked.  
  The new options for test email and episode email should follow the same format:
  - For "email": Append `--test-email`.
  - For "episode_email": Append `--test-episode-email`.

---

## 3. Ensure Consistent Formatting

- For Docker commands, ensure that the generated string does not include extra quotes around parameter values.  
  The final command should be formatted as:
  ```
  docker run -it --rm --env-file "src/.env" podcast_summarizer bash -c "uvicorn src.podcast_summarizer.api.main:app --host 0.0.0.0 --port 80 & sleep 3 && python src/api_test.py --test-upsert --feed-url https://example.com/feed.rss"
  ```
  Not:
  ```
  ... --feed-url "https://example.com/feed.rss"
  ```
- Adjust the parameter concatenation logic so that values are appended without additional quotes in this Docker context.

---

## 4. Summary

- Update the test type radio buttons to include "email" and "episode_email".
- Create an event callback to automatically check required parameter checkboxes based on the selected test type:
  - For "upsert": Automatically check "feed-url".
  - For "email": Automatically check "user-id".
  - For "episode_email": Automatically check both "user-id" and "episode-id".
- Verify that when generating the final command, the extra pre-checked parameters are included and no extra quotes are added for Docker commands.

Apply these changes to the code in `tests/command_creator.py` accordingly. This updated diff should resolve the issues and meet the user's requirements.