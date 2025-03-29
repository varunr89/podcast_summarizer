"""
GUI interface for podcast summarizer with cloud functionality.
"""
import tkinter as tk
import requests
from tkinter import ttk, messagebox
from concurrent.futures import ThreadPoolExecutor
import threading
import queue

BASE_URL = "https://podcast-summarizer-app.whitedesert-b2508737.westus.azurecontainerapps.io"

def parse_episode_indices(indices_arg):
    """Parse episode indices, supporting ranges."""
    if not indices_arg:
        return None

    result = []
    parts = indices_arg.replace(',', ' ').split()
    for part in parts:
        if '-' in str(part):
            try:
                start, end = map(int, str(part).split('-'))
                if start <= end:
                    result.extend(range(start, end + 1))
                else:
                    print(f"Warning: Invalid range '{part}' (start > end), skipping")
            except ValueError:
                print(f"Warning: Could not parse range '{part}', skipping")
        else:
            try:
                result.append(int(part))
            except ValueError:
                print(f"Warning: '{part}' is not a valid episode index, skipping")
    unique = sorted(set(result))
    return unique if unique else None

class PodcastSummarizerFrame(ttk.Frame):
    """Frame-based version of the podcast summarizer GUI."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # Thread pool for parallel API calls
        self.executor = ThreadPoolExecutor(max_workers=5)

        # Shared task queue for API requests
        self.task_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self.process_task_queue, daemon=True)
        self.worker_thread.start()

        # Notebook for multiple tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True)

        # Create all tabs
        self.upsert_tab = ttk.Frame(self.notebook)
        self.process_tab = ttk.Frame(self.notebook)
        self.summarize_tab = ttk.Frame(self.notebook)
        self.episodes_tab = ttk.Frame(self.notebook)
        self.user_email_tab = ttk.Frame(self.notebook)  # New tab for user emails
        self.episode_email_tab = ttk.Frame(self.notebook)  # New tab for episode emails

        # Add tabs to notebook
        self.notebook.add(self.upsert_tab, text="Upsert Podcast")
        self.notebook.add(self.process_tab, text="Process Podcast")
        self.notebook.add(self.summarize_tab, text="Summarize Episode")
        self.notebook.add(self.episodes_tab, text="Episodes")
        self.notebook.add(self.user_email_tab, text="User Email")
        self.notebook.add(self.episode_email_tab, text="Episode Email")

        # Build all tabs
        self._build_upsert_tab()
        self._build_process_tab()
        self._build_summarize_tab()
        self._build_episodes_tab()
        self._build_user_email_tab()
        self._build_episode_email_tab()

        # Configure tab frames for resizing
        for tab in [self.upsert_tab, self.process_tab, self.summarize_tab, 
                   self.episodes_tab, self.user_email_tab, self.episode_email_tab]:
            tab.grid_rowconfigure(1, weight=1)
            tab.grid_columnconfigure(1, weight=1)

    def process_task_queue(self):
        """Process tasks from the queue."""
        while True:
            func, args = self.task_queue.get()
            try:
                self.executor.submit(func, *args)
            finally:
                self.task_queue.task_done()

    # --------------------------------------------------------------------------
    # 1) Upsert Podcast
    # --------------------------------------------------------------------------
    def _build_upsert_tab(self):
        frame = self.upsert_tab
        
        # Input frame
        input_frame = ttk.Frame(frame)
        input_frame.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        
        tk.Label(input_frame, text="Feed URL:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.upsert_feed_url = tk.Entry(input_frame, width=80)
        self.upsert_feed_url.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        
        tk.Label(input_frame, text="Parser Type:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.upsert_parser_type = tk.StringVar(value="auto")
        parser_type_cb = ttk.Combobox(input_frame, textvariable=self.upsert_parser_type, 
                                     values=["auto", "rss", "crawler"], width=20)
        parser_type_cb.grid(row=1, column=1, sticky='w', padx=5, pady=5)
        
        tk.Label(input_frame, text="Description (optional):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.upsert_desc = tk.Entry(input_frame, width=80)
        self.upsert_desc.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
        
        btn_upsert = tk.Button(input_frame, text="Upsert Podcast", command=self.handle_upsert_podcast)
        btn_upsert.grid(row=3, column=1, pady=10, sticky="e")
        
        # Output frame
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        output_frame.grid_columnconfigure(0, weight=1)
        output_frame.grid_rowconfigure(0, weight=1)
        
        self.upsert_output = tk.Text(output_frame, height=20, width=100)
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.upsert_output.yview)
        self.upsert_output.configure(yscrollcommand=scrollbar.set)
        
        self.upsert_output.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
    
    def handle_upsert_podcast(self):
        feed_url = self.upsert_feed_url.get().strip()
        parser_type = self.upsert_parser_type.get().strip()
        description = self.upsert_desc.get().strip()
        payload = {"feed_url": feed_url, "parser_type": parser_type}
        if description:
            payload["description"] = description
        url = f"{BASE_URL}/upsert-podcast"
        self.upsert_output.delete("1.0", tk.END)
        self.upsert_output.insert(tk.END, f"Enqueuing: POST {url}\nPayload: {payload}\n\n")
        self.task_queue.put((self.request_upsert_podcast, (url, payload)))

    def request_upsert_podcast(self, url, payload):
        try:
            resp = requests.post(url, json=payload)
            self.after(0, self.display_upsert_result, resp)
        except Exception as e:
            self.after(0, self.display_upsert_error, e)

    def display_upsert_result(self, resp):
        self.upsert_output.insert(tk.END, f"Status Code: {resp.status_code}\nResponse: {resp.text}\n")

    def display_upsert_error(self, err):
        self.upsert_output.insert(tk.END, f"Error: {str(err)}\n")

    # --------------------------------------------------------------------------
    # 2) Process Podcast
    # --------------------------------------------------------------------------
    def _build_process_tab(self):
        frame = self.process_tab
        
        # Input frame
        input_frame = ttk.Frame(frame)
        input_frame.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        
        tk.Label(input_frame, text="Feed URL:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.process_feed_url = tk.Entry(input_frame, width=80)
        self.process_feed_url.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        
        tk.Label(input_frame, text="Limit Episodes:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.limit_episodes = tk.Entry(input_frame, width=20)
        self.limit_episodes.insert(0, "1")
        self.limit_episodes.grid(row=1, column=1, sticky='w', padx=5, pady=5)
        
        tk.Label(input_frame, text="Episode Indices (e.g. 1,2 or 1-3):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.episode_indices = tk.Entry(input_frame, width=40)
        self.episode_indices.grid(row=2, column=1, sticky='w', padx=5, pady=5)
        
        tk.Label(input_frame, text="Split size (MB):").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.split_size = tk.Entry(input_frame, width=20)
        self.split_size.insert(0, "25.0")
        self.split_size.grid(row=3, column=1, sticky='w', padx=5, pady=5)
        
        self.include_transcription_var = tk.BooleanVar(value=True)
        tk.Checkbutton(input_frame, text="Include Transcription", 
                      variable=self.include_transcription_var).grid(row=4, column=1, sticky="w")
        
        btn_process = tk.Button(input_frame, text="Process Podcast", command=self.handle_process_podcast)
        btn_process.grid(row=5, column=1, pady=10, sticky="e")
        
        # Output frame
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        output_frame.grid_columnconfigure(0, weight=1)
        output_frame.grid_rowconfigure(0, weight=1)
        
        self.process_output = tk.Text(output_frame, height=20, width=100)
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.process_output.yview)
        self.process_output.configure(yscrollcommand=scrollbar.set)
        
        self.process_output.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')

    def handle_process_podcast(self):
        feed_url = self.process_feed_url.get().strip()
        limit_ep = int(self.limit_episodes.get())
        indices = self.episode_indices.get().strip()
        split_size_mb = float(self.split_size.get())
        include_trans = self.include_transcription_var.get()
        parsed_indices = parse_episode_indices(indices) if indices else None
        url = f"{BASE_URL}/process-podcast"
        
        self.process_output.delete("1.0", tk.END)
        if parsed_indices and len(parsed_indices) > 1:
            self.process_output.insert(tk.END, "Detected multiple episode indices. Queueing one request per index...\n\n")
            base_payload = {
                "feed_url": feed_url,
                "limit_episodes": 0,
                "split_size_mb": split_size_mb,
                "include_transcription": include_trans
            }
            for idx in parsed_indices:
                single_payload = dict(base_payload)
                single_payload["episode_indices"] = [idx]
                self.process_output.insert(tk.END, f"Enqueued: POST {url} with Payload: {single_payload}\n")
                self.task_queue.put((self.request_process_podcast, (url, single_payload)))
        else:
            if parsed_indices and len(parsed_indices) == 1:
                payload = {
                    "feed_url": feed_url,
                    "limit_episodes": 0,
                    "split_size_mb": split_size_mb,
                    "include_transcription": include_trans,
                    "episode_indices": parsed_indices
                }
            else:
                payload = {
                    "feed_url": feed_url,
                    "limit_episodes": limit_ep,
                    "split_size_mb": split_size_mb,
                    "include_transcription": include_trans
                }
            self.process_output.insert(tk.END, f"Enqueued: POST {url}\nPayload: {payload}\n\n")
            self.task_queue.put((self.request_process_podcast, (url, payload)))

    def request_process_podcast(self, url, payload):
        try:
            resp = requests.post(url, json=payload)
            self.after(0, self.display_process_result, resp)
        except Exception as e:
            self.after(0, self.display_process_error, e)

    def display_process_result(self, resp):
        self.process_output.insert(tk.END, f"Status Code: {resp.status_code}\nResponse: {resp.text}\n\n")

    def display_process_error(self, err):
        self.process_output.insert(tk.END, f"Error: {str(err)}\n\n")

    # --------------------------------------------------------------------------
    # 3) Summarize Episode
    # --------------------------------------------------------------------------
    def _build_summarize_tab(self):
        frame = self.summarize_tab
        
        # Input frame
        input_frame = ttk.Frame(frame)
        input_frame.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        
        tk.Label(input_frame, text="Episode ID:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.summarize_episode_id = tk.Entry(input_frame, width=80)
        self.summarize_episode_id.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        
        tk.Label(input_frame, text="Custom Prompt:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.custom_prompt = tk.Entry(input_frame, width=80)
        self.custom_prompt.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        
        tk.Label(input_frame, text="Chunk Size:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.chunk_size = tk.Entry(input_frame, width=20)
        self.chunk_size.insert(0, "4000")
        self.chunk_size.grid(row=2, column=1, sticky='w', padx=5, pady=5)
        
        tk.Label(input_frame, text="Chunk Overlap:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.chunk_overlap = tk.Entry(input_frame, width=20)
        self.chunk_overlap.insert(0, "200")
        self.chunk_overlap.grid(row=3, column=1, sticky='w', padx=5, pady=5)
        
        tk.Label(input_frame, text="Method:").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.method = tk.Entry(input_frame, width=20)
        self.method.insert(0, "auto")
        self.method.grid(row=4, column=1, sticky='w', padx=5, pady=5)
        
        tk.Label(input_frame, text="Detail Level:").grid(row=5, column=0, sticky="e", padx=5, pady=5)
        self.detail_level = tk.Entry(input_frame, width=20)
        self.detail_level.insert(0, "standard")
        self.detail_level.grid(row=5, column=1, sticky='w', padx=5, pady=5)
        
        tk.Label(input_frame, text="Temperature:").grid(row=6, column=0, sticky="e", padx=5, pady=5)
        self.temperature = tk.Entry(input_frame, width=20)
        self.temperature.insert(0, "0.5")
        self.temperature.grid(row=6, column=1, sticky='w', padx=5, pady=5)
        
        tk.Label(input_frame, text="User ID (Optional):").grid(row=7, column=0, sticky="e", padx=5, pady=5)
        self.user_id = tk.Entry(input_frame, width=80)
        self.user_id.grid(row=7, column=1, sticky='ew', padx=5, pady=5)
        
        btn_summarize = tk.Button(input_frame, text="Summarize Episode", command=self.handle_summarize_episode)
        btn_summarize.grid(row=8, column=1, pady=10, sticky="e")
        
        # Output frame
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        output_frame.grid_columnconfigure(0, weight=1)
        output_frame.grid_rowconfigure(0, weight=1)
        
        self.summarize_output = tk.Text(output_frame, height=20, width=100)
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.summarize_output.yview)
        self.summarize_output.configure(yscrollcommand=scrollbar.set)
        
        self.summarize_output.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')

    def handle_summarize_episode(self):
        episode_id = self.summarize_episode_id.get().strip()
        custom_prompt = self.custom_prompt.get().strip()
        chunk_size = int(self.chunk_size.get())
        chunk_overlap = int(self.chunk_overlap.get())
        method = self.method.get().strip()
        detail_level = self.detail_level.get().strip()
        temperature = float(self.temperature.get())
        user_id = self.user_id.get().strip() or None
        payload = {
            "episode_id": episode_id,
            "custom_prompt": custom_prompt if custom_prompt else None,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "method": method,
            "detail_level": detail_level,
            "temperature": temperature
        }
        if user_id:
            payload["user_id"] = user_id
        url = f"{BASE_URL}/summarize-episode"
        self.summarize_output.delete("1.0", tk.END)
        self.summarize_output.insert(tk.END, f"Enqueuing: POST {url}\nPayload: {payload}\n\n")
        self.task_queue.put((self.request_summarize_episode, (url, payload)))

    def request_summarize_episode(self, url, payload):
        try:
            resp = requests.post(url, json=payload)
            self.after(0, self.display_summarize_result, resp)
        except Exception as e:
            self.after(0, self.display_summarize_error, e)

    def display_summarize_result(self, resp):
        self.summarize_output.insert(tk.END, f"Status Code: {resp.status_code}\nResponse: {resp.text}\n")

    def display_summarize_error(self, err):
        self.summarize_output.insert(tk.END, f"Error: {str(err)}\n")

    # --------------------------------------------------------------------------
    # 4) Episodes
    # --------------------------------------------------------------------------
    def _build_episodes_tab(self):
        frame = self.episodes_tab
        
        # Input frame
        input_frame = ttk.Frame(frame)
        input_frame.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        
        tk.Label(input_frame, text="Podcast ID (optional):").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.episodes_podcast_id = tk.Entry(input_frame, width=80)
        self.episodes_podcast_id.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        
        tk.Label(input_frame, text="Transcribed Only?").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.transcribed_only_var = tk.BooleanVar(value=False)
        tk.Checkbutton(input_frame, variable=self.transcribed_only_var).grid(row=1, column=1, sticky="w")
        
        btn_fetch = tk.Button(input_frame, text="Fetch Episodes", command=self.handle_get_episodes)
        btn_fetch.grid(row=2, column=1, pady=10, sticky="e")
        
        # Output frame
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        output_frame.grid_columnconfigure(0, weight=1)
        output_frame.grid_rowconfigure(0, weight=1)
        
        self.episodes_output = tk.Text(output_frame, height=20, width=100)
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.episodes_output.yview)
        self.episodes_output.configure(yscrollcommand=scrollbar.set)
        
        self.episodes_output.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')

    def handle_get_episodes(self):
        podcast_id = self.episodes_podcast_id.get().strip()
        transcribed_only = self.transcribed_only_var.get()
        url = f"{BASE_URL}/episodes/transcribed" if transcribed_only else f"{BASE_URL}/episodes"
        params = {}
        if podcast_id:
            params["podcast_id"] = podcast_id
        self.episodes_output.delete("1.0", tk.END)
        self.episodes_output.insert(tk.END, f"GET {url}\nParams: {params}\n\n")
        self.executor.submit(self.request_get_episodes, url, params)

    def request_get_episodes(self, url, params):
        try:
            resp = requests.get(url, params=params)
            self.after(0, self.display_episodes_result, resp)
        except Exception as e:
            self.after(0, self.display_episodes_error, e)

    def display_episodes_result(self, resp):
        self.episodes_output.insert(tk.END, f"Status Code: {resp.status_code}\nResponse: {resp.text}\n")

    def display_episodes_error(self, err):
        self.episodes_output.insert(tk.END, f"Error: {str(err)}\n")

    # --------------------------------------------------------------------------
    # 5) User Email
    # --------------------------------------------------------------------------
    def _build_user_email_tab(self):
        frame = self.user_email_tab
        
        # Input frame
        input_frame = ttk.Frame(frame)
        input_frame.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        
        tk.Label(input_frame, text="User ID:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.user_email_id = tk.Entry(input_frame, width=80)
        self.user_email_id.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        
        btn_send = tk.Button(input_frame, text="Send User Email", command=self.handle_user_email)
        btn_send.grid(row=1, column=1, pady=10, sticky="e")
        
        # Output frame
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        output_frame.grid_columnconfigure(0, weight=1)
        output_frame.grid_rowconfigure(0, weight=1)
        
        self.user_email_output = tk.Text(output_frame, height=20, width=100)
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.user_email_output.yview)
        self.user_email_output.configure(yscrollcommand=scrollbar.set)
        
        self.user_email_output.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')

    def handle_user_email(self):
        user_id = self.user_email_id.get().strip()
        url = f"{BASE_URL}/send-user-emails/{user_id}"
        
        self.user_email_output.delete("1.0", tk.END)
        self.user_email_output.insert(tk.END, f"Enqueuing: POST {url}\n\n")
        self.task_queue.put((self.request_user_email, (url,)))

    def request_user_email(self, url):
        try:
            resp = requests.post(url)
            self.after(0, self.display_user_email_result, resp)
        except Exception as e:
            self.after(0, self.display_user_email_error, e)

    def display_user_email_result(self, resp):
        self.user_email_output.insert(tk.END, f"Status Code: {resp.status_code}\nResponse: {resp.text}\n")

    def display_user_email_error(self, err):
        self.user_email_output.insert(tk.END, f"Error: {str(err)}\n")

    # --------------------------------------------------------------------------
    # 6) Episode Email
    # --------------------------------------------------------------------------
    def _build_episode_email_tab(self):
        frame = self.episode_email_tab
        
        # Input frame
        input_frame = ttk.Frame(frame)
        input_frame.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        
        tk.Label(input_frame, text="User ID:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.episode_email_user_id = tk.Entry(input_frame, width=80)
        self.episode_email_user_id.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        
        tk.Label(input_frame, text="Episode ID:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.episode_email_ep_id = tk.Entry(input_frame, width=80)
        self.episode_email_ep_id.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        
        btn_send = tk.Button(input_frame, text="Send Episode Email", command=self.handle_episode_email)
        btn_send.grid(row=2, column=1, pady=10, sticky="e")
        
        # Output frame
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        output_frame.grid_columnconfigure(0, weight=1)
        output_frame.grid_rowconfigure(0, weight=1)
        
        self.episode_email_output = tk.Text(output_frame, height=20, width=100)
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.episode_email_output.yview)
        self.episode_email_output.configure(yscrollcommand=scrollbar.set)
        
        self.episode_email_output.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')

    def handle_episode_email(self):
        user_id = self.episode_email_user_id.get().strip()
        episode_id = self.episode_email_ep_id.get().strip()
        url = f"{BASE_URL}/send-episode-summary/{user_id}/{episode_id}"
        
        self.episode_email_output.delete("1.0", tk.END)
        self.episode_email_output.insert(tk.END, f"Enqueuing: POST {url}\n\n")
        self.task_queue.put((self.request_episode_email, (url,)))

    def request_episode_email(self, url):
        try:
            resp = requests.post(url)
            self.after(0, self.display_episode_email_result, resp)
        except Exception as e:
            self.after(0, self.display_episode_email_error, e)

    def display_episode_email_result(self, resp):
        self.episode_email_output.insert(tk.END, f"Status Code: {resp.status_code}\nResponse: {resp.text}\n")

    def display_episode_email_error(self, err):
        self.episode_email_output.insert(tk.END, f"Error: {str(err)}\n")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Podcast Summarizer API Tester")
    frame = PodcastSummarizerFrame(root)
    frame.pack(fill='both', expand=True)
    root.mainloop()