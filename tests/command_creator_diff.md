# Diff Instructions for tests/command_creator.py

The following changes are recommended to remove the extra quotation marks from the generated Docker command for local container tests.

---

## Issue

When generating a command for the "Local Container" environment, the current output includes extra double quotes around parameter values, for example:

```
docker run -it --rm --env-file "src/.env" podcast_summarizer bash -c ""uvicorn src.podcast_summarizer.api.main:app --host 0.0.0.0 --port 80 & sleep 3 && python src/api_test.py --test-upsert --feed-url "https://omnycontent.com/d/playlist/...""
```

This results in an output with extra quotes around the feed URL. The desired output is:

```
docker run -it --rm --env-file "src/.env" podcast_summarizer bash -c "uvicorn src.podcast_summarizer.api.main:app --host 0.0.0.0 --port 80 & sleep 3 && python src/api_test.py --test-upsert --feed-url https://omnycontent.com/d/playlist/..."
```

---

## Proposed Changes

1. **In the Parameter Assembly:**

   - When constructing the command string in the `generate_command()` function (in tests/command_creator.py), ensure that for the Docker command, parameter values are not wrapped with extra double quotes.
   - For example, for the `--feed-url` parameter, instead of appending:
     ```
     --feed-url "{feed_url}"
     ```
     It should append:
     ```
     --feed-url {feed_url}
     ```
     (without quotes).

2. **Command Assembly Logic:**

   - Split the command assembly into two parts:
     - One for Building the base command for local source tests.
     - One for building the Docker-wrapped command for local container tests.
   - For the Docker command, start with:
     ```
     docker run -it --rm --env-file "src/.env" podcast_summarizer bash -c "uvicorn src/podcast_summarizer.api.main:app --host 0.0.0.0 --port 80 & sleep 3 && python src/api_test.py
     ```
   - Append parameters with a preceding space and without embedding additional quotes. For instance:
     ```
     if parameter is provided, add:  f' --{param_name} {value}'
     ```
     rather than:
     ```
     f' --{param_name} "{value}"'
     ```
   - Finally, close the Docker command's bash command with a single quote (or double quote) at the end.

3. **Example Correction:**

   **Before (incorrect):**
   ```python
   command += f' --feed-url "{feed_url}"'
   ```
   **After (correct):**
   ```python
   command += f' --feed-url {feed_url}'
   ```

   - Apply similar changes to all parameter concatenations within the Docker command assembly block in the `generate_command()` method.

---

## Testing the Changes

After applying these modifications to `tests/command_creator.py`, running the script and selecting "Local Container" with relevant parameters should yield the generated command that matches the desired output format without extra quotes.

---

These changes should resolve the extra quotation issue and meet the requirements provided.