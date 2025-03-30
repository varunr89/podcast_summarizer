"""
GUI Command Creator for Podcast Summarizer Testing.
Creates terminal commands for local/docker tests, embeds the cloud interface,
and provides a Cloud Service Bus tab that sends requests using parallelization.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import sys
import os
import json
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading
import queue

# Add src to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import the cloud interface
from src.podcast_summarizer_gui import PodcastSummarizerFrame

# Service Bus endpoint
SERVICE_BUS_URL = "https://podcast-frontend-api.whitedesert-b2508737.westus.azurecontainerapps.io/api/forward"

# Mapping test types to their API endpoints
TARGET_PATH_MAP = {
    "upsert": "/upsert-podcast",
    "process": "/process-podcast",
    "summarize": "/summarize-episode",
    "email": "/send-user-emails",
    "episode_email": "/send-episode-summary"
}

class ParamFrame(ttk.Frame):
    """A frame containing a checkbox and entry field for a parameter."""
    def __init__(self, parent, param_name, label_text, default_value=""):
        super().__init__(parent)
        self.param_name = param_name
        self.enabled = tk.BooleanVar(value=False)
        
        # Create and pack the checkbox
        self.checkbox = ttk.Checkbutton(
            self, 
            text=label_text,
            variable=self.enabled
        )
        self.checkbox.pack(side=tk.LEFT)
        
        # Create and pack the entry field
        self.entry = ttk.Entry(self, width=50)
        self.entry.pack(side=tk.LEFT, padx=5)
        if default_value:
            self.entry.insert(0, default_value)
    
    def set_enabled(self, enabled: bool):
        """Set the enabled state of the checkbox."""
        self.enabled.set(enabled)
            
    def get_value(self):
        """Get the parameter value if enabled."""
        if self.enabled.get():
            value = self.entry.get().strip()
            if value:
                return (self.param_name, value)
        return None

class ServiceBusFrame(ttk.Frame):
    """Frame for sending requests through the service bus with parallel processing."""
    def __init__(self, parent):
        super().__init__(parent)
        
        # Initialize thread pool and task queue for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.task_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self.process_task_queue, daemon=True)
        self.worker_thread.start()
        
        # Create main scrollable area
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Test Type Selection
        type_frame = ttk.LabelFrame(scrollable_frame, text="Test Type", padding="5")
        type_frame.pack(fill="x", padx=5, pady=5)
        
        test_types = ["process", "summarize", "upsert", "email", "episode_email"]
        self.test_type_var = tk.StringVar(value=test_types[0])
        for test_type in test_types:
            ttk.Radiobutton(type_frame, text=test_type.title(), 
                          variable=self.test_type_var, 
                          value=test_type,
                          command=self.on_test_type_change).pack(anchor="w")
        
        # Parameters Frame
        param_frame = ttk.LabelFrame(scrollable_frame, text="Parameters", padding="5")
        param_frame.pack(fill="x", padx=5, pady=5)
        
        # Create parameter entries
        self.params = {}
        
        # Common Parameters
        common_params = [
            ("user-id", "User ID", "c4859aa4-50f7-43bd-9ff2-16efed5bf133"),
            ("episode-id", "Episode ID"),
            ("feed-url", "Feed URL")
        ]
        for param_name, label, *default in common_params:
            default_value = default[0] if default else ""
            frame = ParamFrame(param_frame, param_name, label, default_value)
            frame.pack(fill="x", padx=5, pady=2)
            self.params[param_name] = frame
            
        # Process Parameters
        process_frame = ttk.LabelFrame(param_frame, text="Process Options", padding="5")
        process_frame.pack(fill="x", padx=5, pady=5)
        
        process_params = [
            ("limit-episodes", "Limit Episodes", "1"),
            ("episode-indices", "Episode Indices (e.g., 1,2,3-5)"),
            ("split-size-mb", "Split Size (MB)", "25.0"),
            ("include-transcription", "Include Transcription", "true")
        ]
        for param_name, label, *default in process_params:
            default_value = default[0] if default else ""
            frame = ParamFrame(process_frame, param_name, label, default_value)
            frame.pack(fill="x", padx=5, pady=2)
            self.params[param_name] = frame
        
        # Summarization Parameters
        summarize_frame = ttk.LabelFrame(param_frame, text="Summarization Options", padding="5")
        summarize_frame.pack(fill="x", padx=5, pady=5)
        
        summarize_params = [
            ("custom-prompt", "Custom Prompt"),
            ("chunk-size", "Chunk Size", "4000"),
            ("chunk-overlap", "Chunk Overlap", "200"),
            ("method", "Method", "auto"),
            ("detail-level", "Detail Level", "standard"),
            ("temperature", "Temperature", "0.5")
        ]
        for param_name, label, *default in summarize_params:
            default_value = default[0] if default else ""
            frame = ParamFrame(summarize_frame, param_name, label, default_value)
            frame.pack(fill="x", padx=5, pady=2)
            self.params[param_name] = frame
        
        # Extra Parameters
        extra_frame = ttk.LabelFrame(scrollable_frame, text="Extra Parameters (JSON)", padding="5")
        extra_frame.pack(fill="x", padx=5, pady=5)
        
        self.extra_params = ttk.Entry(extra_frame, width=80)
        self.extra_params.pack(fill="x", padx=5, pady=5)
        
        # Send Request Button
        ttk.Button(scrollable_frame, text="Send Service Bus Request", 
                  command=self.send_request).pack(pady=10)
        
        # Output Display
        output_frame = ttk.LabelFrame(scrollable_frame, text="Service Bus Response", padding="5")
        output_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.output = scrolledtext.ScrolledText(output_frame, width=80, height=10, wrap=tk.WORD)
        self.output.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Pack the scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Initialize parameter states
        self.on_test_type_change()

    def process_task_queue(self):
        """Process tasks from the queue using thread pool."""
        while True:
            func, args = self.task_queue.get()
            try:
                self.executor.submit(func, *args)
            finally:
                self.task_queue.task_done()

    def on_test_type_change(self):
        """Handle test type changes by pre-checking required parameters."""
        test_type = self.test_type_var.get()
        
        # Reset all parameters
        for param in self.params.values():
            param.set_enabled(False)
            
        # Set required parameters based on test type
        if test_type == "upsert":
            self.params["feed-url"].set_enabled(True)
            
        elif test_type == "process":
            self.params["feed-url"].set_enabled(True)
            self.params["limit-episodes"].set_enabled(True)
            self.params["include-transcription"].set_enabled(True)
            self.params["split-size-mb"].set_enabled(True)
            
        elif test_type == "summarize":
            self.params["episode-id"].set_enabled(True)
            self.params["user-id"].set_enabled(True)
            
        elif test_type == "email":
            self.params["user-id"].set_enabled(True)
            
        elif test_type == "episode_email":
            self.params["user-id"].set_enabled(True)
            self.params["episode-id"].set_enabled(True)

    def build_request_payload(self):
        """Build the JSON payload for the service bus request."""
        test_type = self.test_type_var.get()
        payload = {}
        
        # Set the target path based on test type
        target_path = TARGET_PATH_MAP.get(test_type)
        
        # For email endpoints, include IDs in the path
        if test_type in ["email", "episode_email"]:
            uid = self.params["user-id"].entry.get().strip()
            if test_type == "email":
                target_path = f"/send-user-emails/{uid}"
            else:  # episode_email
                eid = self.params["episode-id"].entry.get().strip()
                target_path = f"/send-episode-summary/{uid}/{eid}"
        
        payload["target_path"] = target_path
        
        # Add enabled parameters
        for param in self.params.values():
            result = param.get_value()
            if result:
                name, value = result
                # Skip user-id and episode-id for email routes as they're in the path
                if test_type in ["email", "episode_email"] and name in ["user-id", "episode-id"]:
                    continue
                # Try to convert to number if possible
                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        # Convert string "true"/"false" to boolean
                        if value.lower() == "true":
                            value = True
                        elif value.lower() == "false":
                            value = False
                payload[name.replace("-", "_")] = value
        
        # For process test type, ensure include_transcription and split_size_mb are always provided
        if test_type == "process":
            if "include_transcription" not in payload:
                payload["include_transcription"] = True
            if "split_size_mb" not in payload:
                payload["split_size_mb"] = 25.0
        
        # Add any extra parameters
        extra = self.extra_params.get().strip()
        if extra:
            try:
                extra_dict = json.loads(extra)
                payload.update(extra_dict)
            except json.JSONDecodeError as e:
                self.output.insert(tk.END, f"Error parsing extra parameters JSON: {str(e)}\n")
                return None
        
        return payload

    def send_request(self):
        """Enqueue a service bus request for parallel processing."""
        self.output.delete(1.0, tk.END)
        
        # Build the request payload
        payload = self.build_request_payload()
        if payload is None:
            return
        
        self.output.insert(tk.END, f"Payload:\n{json.dumps(payload, indent=2)}\n\nEnqueuing request...\n")
        # Enqueue the request to be processed by the worker thread
        self.task_queue.put((self.perform_request, (payload,)))

    def perform_request(self, payload):
        """Execute the service bus request (called by worker thread)."""
        try:
            resp = requests.post(SERVICE_BUS_URL, 
                               json=payload,
                               headers={"Content-Type": "application/json"})
            self.after(0, lambda: self.output.insert(tk.END, 
                      f"\nStatus Code: {resp.status_code}\nResponse:\n{resp.text}\n"))
        except Exception as e:
            self.after(0, lambda: self.output.insert(tk.END, 
                      f"\nError sending request: {str(e)}\n"))

class CommandCreator:
    """Main GUI class for creating test commands and running cloud tests."""
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Podcast Summarizer Test Interface")
        
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill='both', expand=True)
        
        # Environment Selection
        env_frame = ttk.LabelFrame(main_frame, text="Test Environment", padding="5")
        env_frame.pack(fill="x", padx=5, pady=5)
        
        self.env_var = tk.StringVar(value="local_source")
        ttk.Radiobutton(env_frame, text="Local Source", 
                       variable=self.env_var, 
                       value="local_source",
                       command=self.on_env_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(env_frame, text="Local Container", 
                       variable=self.env_var, 
                       value="docker",
                       command=self.on_env_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(env_frame, text="Cloud", 
                       variable=self.env_var, 
                       value="cloud",
                       command=self.on_env_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(env_frame, text="Cloud Service Bus", 
                       variable=self.env_var, 
                       value="service_bus",
                       command=self.on_env_change).pack(side=tk.LEFT, padx=5)
        
        # Create notebook for switching between interfaces
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Command Generation tab
        self.cmd_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.cmd_tab, text="Generate Command")
        self.build_command_tab()
        
        # Cloud Interface tab with embedded PodcastSummarizerFrame
        self.cloud_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.cloud_tab, text="Cloud Interface")
        self.cloud_frame = PodcastSummarizerFrame(self.cloud_tab)
        self.cloud_frame.pack(fill='both', expand=True)
        
        # Service Bus Interface tab
        self.service_bus_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.service_bus_tab, text="Service Bus")
        self.service_bus_frame = ServiceBusFrame(self.service_bus_tab)
        self.service_bus_frame.pack(fill='both', expand=True)
        
        # Set default tab based on environment
        self.on_env_change()
    
    def on_env_change(self):
        """Handle environment selection changes."""
        env = self.env_var.get()
        if env == "cloud":
            self.notebook.select(self.cloud_tab)
        elif env == "service_bus":
            self.notebook.select(self.service_bus_tab)
        else:
            self.notebook.select(self.cmd_tab)
    
    def build_command_tab(self):
        """Build the command generation tab interface."""
        # Create scrollable frame
        canvas = tk.Canvas(self.cmd_tab)
        scrollbar = ttk.Scrollbar(self.cmd_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Test Type Selection
        type_frame = ttk.LabelFrame(scrollable_frame, text="Test Type", padding="5")
        type_frame.pack(fill="x", padx=5, pady=5)
        
        test_types = ["process", "summarize", "upsert", "email", "episode_email"]
        self.test_type_var = tk.StringVar(value=test_types[0])
        for test_type in test_types:
            ttk.Radiobutton(type_frame, text=test_type.title(), 
                          variable=self.test_type_var, 
                          value=test_type,
                          command=self.on_test_type_change).pack(anchor="w")
        
        # Parameters Frame
        param_frame = ttk.LabelFrame(scrollable_frame, text="Parameters", padding="5")
        param_frame.pack(fill="x", padx=5, pady=5)
        
        # Create parameter entries
        self.params = {}
        
        # Common Parameters
        common_params = [
            ("user-id", "User ID", "c4859aa4-50f7-43bd-9ff2-16efed5bf133"),
            ("episode-id", "Episode ID"),
            ("feed-url", "Feed URL")
        ]
        for param_name, label, *default in common_params:
            default_value = default[0] if default else ""
            frame = ParamFrame(param_frame, param_name, label, default_value)
            frame.pack(fill="x", padx=5, pady=2)
            self.params[param_name] = frame
            
        # Process Parameters
        process_frame = ttk.LabelFrame(param_frame, text="Process Options", padding="5")
        process_frame.pack(fill="x", padx=5, pady=5)
        
        process_params = [
            ("limit-episodes", "Limit Episodes", "1"),
            ("episode-indices", "Episode Indices (e.g., 1,2,3-5)"),
            ("split-size-mb", "Split Size (MB)", "25.0"),
            ("include-transcription", "Include Transcription", "true")
        ]
        for param_name, label, *default in process_params:
            default_value = default[0] if default else ""
            frame = ParamFrame(process_frame, param_name, label, default_value)
            frame.pack(fill="x", padx=5, pady=2)
            self.params[param_name] = frame
        
        # Summarization Parameters
        summarize_frame = ttk.LabelFrame(param_frame, text="Summarization Options", padding="5")
        summarize_frame.pack(fill="x", padx=5, pady=5)
        
        summarize_params = [
            ("custom-prompt", "Custom Prompt"),
            ("chunk-size", "Chunk Size", "4000"),
            ("chunk-overlap", "Chunk Overlap", "200"),
            ("method", "Method", "auto"),
            ("detail-level", "Detail Level", "standard"),
            ("temperature", "Temperature", "0.5")
        ]
        for param_name, label, *default in summarize_params:
            default_value = default[0] if default else ""
            frame = ParamFrame(summarize_frame, param_name, label, default_value)
            frame.pack(fill="x", padx=5, pady=2)
            self.params[param_name] = frame
        
        # Extra Parameters
        extra_frame = ttk.LabelFrame(scrollable_frame, text="Extra Parameters", padding="5")
        extra_frame.pack(fill="x", padx=5, pady=5)
        
        self.extra_params = ttk.Entry(extra_frame, width=80)
        self.extra_params.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(extra_frame, 
                 text="Additional command-line parameters (added as-is)").pack(anchor="w", padx=5)
        
        # Generate Button
        ttk.Button(scrollable_frame, text="Generate & Copy Command", 
                  command=self.generate_and_copy_command).pack(pady=10)
        
        # Output Display
        output_frame = ttk.LabelFrame(scrollable_frame, text="Generated Command", padding="5")
        output_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.output = scrolledtext.ScrolledText(output_frame, width=80, height=10, wrap=tk.WORD)
        self.output.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Pack the scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Initialize parameter states
        self.on_test_type_change()

    def on_test_type_change(self):
        """Handle test type changes by pre-checking required parameters."""
        test_type = self.test_type_var.get()
        
        # Reset all parameters
        for param in self.params.values():
            param.set_enabled(False)
            
        # Set required parameters based on test type
        if test_type == "upsert":
            self.params["feed-url"].set_enabled(True)
            
        elif test_type == "process":
            self.params["feed-url"].set_enabled(True)
            self.params["limit-episodes"].set_enabled(True)
            self.params["include-transcription"].set_enabled(True)
            self.params["split-size-mb"].set_enabled(True)
            
        elif test_type == "summarize":
            self.params["episode-id"].set_enabled(True)
            self.params["user-id"].set_enabled(True)
            
        elif test_type == "email":
            self.params["user-id"].set_enabled(True)
            
        elif test_type == "episode_email":
            self.params["user-id"].set_enabled(True)
            self.params["episode-id"].set_enabled(True)

    def build_api_test_command(self, test_type, params):
        """Build the api_test.py command with parameters."""
        cmd = [f"--test-{test_type}"]
        
        # Add parameters that are enabled and have values
        for param, value in params:
            cmd.append(f"--{param} {value}")
            
        # Add any extra parameters
        extra = self.extra_params.get().strip()
        if extra:
            cmd.append(extra)
            
        return " ".join(cmd)

    def generate_command(self):
        """Generate the complete command based on GUI inputs."""
        env = self.env_var.get()
        test_type = self.test_type_var.get()
        
        # Collect enabled parameters
        enabled_params = []
        for param in self.params.values():
            result = param.get_value()
            if result:
                enabled_params.append(result)
        
        # For process test type, ensure include_transcription and split_size_mb are provided
        if test_type == "process":
            has_include_trans = any(param for param, _ in enabled_params if param == "include-transcription")
            has_split_size = any(param for param, _ in enabled_params if param == "split-size-mb")
            
            if not has_include_trans:
                enabled_params.append(("include-transcription", "true"))
            if not has_split_size:
                enabled_params.append(("split-size-mb", "25.0"))
        
        # Build the api_test.py command part
        api_cmd = self.build_api_test_command(test_type, enabled_params)
        
        if env == "local_source":
            # For local source, just prepend python command
            final_cmd = f"python src/api_test.py {api_cmd}"
        else:
            # For Docker, wrap the command appropriately
            final_cmd = (
                'docker run -it --rm --env-file "src/.env" podcast_summarizer '
                'bash -c "uvicorn src.podcast_summarizer.api.main:app '
                '--host 0.0.0.0 --port 80 & sleep 3 && '
                f'python src/api_test.py {api_cmd}"'
            )
        
        return final_cmd
    
    def generate_and_copy_command(self):
        """Generate the command and copy it to clipboard."""
        command = self.generate_command()
        
        # Display the command and success message
        self.output.delete(1.0, tk.END)
        self.output.insert(tk.END, f"{command}\n\nCommand copied to clipboard!")
        
        # Copy to clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(command)
    
    def run(self):
        """Start the GUI."""
        self.root.mainloop()

if __name__ == "__main__":
    app = CommandCreator()
    app.run()