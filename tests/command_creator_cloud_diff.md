# Diff Instructions for Integrating Cloud Interface and Email Routes in Command Creator

The following changes should be applied to `tests/command_creator.py` to meet the new requirements. These instructions describe the modifications to embed the cloud interface (previously launched as a separate GUI from `src/podcast_summarizer_gui.py`) into a Notebook tab, as well as to add two new tabs for email routes ("User Email" and "Episode Email") using the payload and route details from the email endpoints (see `src/podcast_summarizer/api/endpoints/email_routes.py`).

---

## 1. Remove Separate Launch of PodcastSummarizerGUI

- **Before:**  
  The code imports and instantiates `PodcastSummarizerGUI` as a standalone Tk window (or uses its components in a way that launches a separate interface).

- **After:**  
  Remove any code that calls `mainloop()` on PodcastSummarizerGUI or creates a separate window. Instead, embed its components inside a Frame that can be placed within the main Notebook.

---

## 2. Update Notebook Organization in CommandCreator

- **Add a New Top-Level Notebook:**  
  Modify the main interface so that it contains a Notebook with at least two tabs:
  - **Tab 1:** "Generate Command"  
    (This tab remains for local_source and docker environments.)
  - **Tab 2:** "Cloud Interface"  
    (This tab will embed the cloud UI.)

- **Implement Environment Switching Callback:**  
  In the environment selection radio buttons (which should now include three values: "local_source", "docker", and "cloud"), add an `on_env_change()` callback that automatically switches the Notebook tab:
  - If environment is "cloud", select the "Cloud Interface" tab.
  - Otherwise, select the "Generate Command" tab.

---

## 3. Embed Cloud Interface in "Cloud Interface" Tab

- **Create a CloudFrame Class (if not already implemented):**  
  This class should inherit from `ttk.Frame` and be used for the Cloud Interface tab content.
  
- **Integrate PodcastSummarizerGUI Components:**  
  Instead of launching PodcastSummarizerGUI as a separate window, modify its code to allow its core GUI components (e.g. the tabs for Upsert, Process, Summarize, and Episodes) to be inserted into a Frame. For example:
  - In CloudFrame, instantiate a modified version of PodcastSummarizerGUI (or extract its widget-building functions), and assign its tab frames to the CloudFrame’s Notebook.
  
- **New Tabs for Email Routes:**  
  Within the CloudFrame, add two additional tabs to the Notebook specifically for email functionality:
  - **User Email Tab:**  
    - Contains an entry for "User ID".
    - Has a button (e.g., "Send User Email") that, when clicked, sends a POST request to the user email endpoint.  
    - Use the route and payload format defined in `src/podcast_summarizer/api/endpoints/email_routes.py`.
  
  - **Episode Email Tab:**  
    - Contains entries for "User ID" and "Episode ID".
    - Has a button (e.g., "Send Episode Email") to send a POST request to the episode email endpoint.
  
  *Note:* You should refer to the email routes file for details on the endpoint URLs and payload formats to be used.
  
  The new email tabs can be created similarly to the existing tabs in PodcastSummarizerGUI, reusing the layout patterns used in other tabs.

---

## 4. Final Behavior Verification

- When running `python tests/command_creator.py`, the main window should display the environment radio buttons.
- Selecting "local_source" or "docker" shows the "Generate Command" tab as before.
- Selecting "cloud" automatically switches the Notebook to the "Cloud Interface" tab. In this tab:
  - The embedded cloud interface (the functionality from `src/podcast_summarizer_gui.py`) is visible.
  - In addition to the existing tabs (Upsert, Process, Summarize, Episodes), two new tabs ("User Email" and "Episode Email") are available to trigger email-related routes.
- No separate window should be launched for the cloud interface.

---

Apply these diff instructions to update the code in `tests/command_creator.py` accordingly.