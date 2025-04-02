"""
GUI Service Bus Frame Component for Podcast Summarizer Testing.
Provides a frame for sending requests through the service bus with parallel processing.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
import json

from .param_frame import ParamFrame
from .command_processor import build_request_payload, send_request

class ServiceBusFrame(ttk.Frame):
    """Frame for sending requests through the service bus with parallel processing."""
    def __init__(self, parent):
        super().__init__(parent)
        
        # Initialize thread pool and task queue for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.task_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self.process_task_queue, daemon=True)
        self.worker_thread.start()
        
        self._init_gui()
        self.on_test_type_change()
    
    def _init_gui(self):
        """Initialize the GUI components."""
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
        type_frame = self._create_test_type_frame(scrollable_frame)
        type_frame.pack(fill="x", padx=5, pady=5)
        
        # Parameters Frame
        param_frame = self._create_param_frame(scrollable_frame)
        param_frame.pack(fill="x", padx=5, pady=5)
        
        # Extra Parameters Frame
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
    
    def _create_test_type_frame(self, parent):
        """Create the test type selection frame."""
        frame = ttk.LabelFrame(parent, text="Test Type", padding="5")
        
        test_types = ["process", "summarize", "upsert", "email", "episode_email"]
        self.test_type_var = tk.StringVar(value=test_types[0])
        for test_type in test_types:
            ttk.Radiobutton(frame, text=test_type.title(), 
                          variable=self.test_type_var, 
                          value=test_type,
                          command=self.on_test_type_change).pack(anchor="w")
        
        return frame
    
    def _create_param_frame(self, parent):
        """Create the parameters frame with all parameter entries."""
        frame = ttk.LabelFrame(parent, text="Parameters", padding="5")
        self.params = {}
        
        # Create parameter entries
        self._create_common_params(frame)
        self._create_process_params(frame)
        self._create_summarize_params(frame)
        
        return frame
    
    def _create_common_params(self, parent):
        """Create common parameter entries."""
        common_params = [
            ("user-id", "User ID", "c4859aa4-50f7-43bd-9ff2-16efed5bf133"),
            ("episode-id", "Episode ID"),
            ("feed-url", "Feed URL")
        ]
        for param_name, label, *default in common_params:
            default_value = default[0] if default else ""
            frame = ParamFrame(parent, param_name, label, default_value)
            frame.pack(fill="x", padx=5, pady=2)
            self.params[param_name] = frame
    
    def _create_process_params(self, parent):
        """Create process-specific parameter entries."""
        process_frame = ttk.LabelFrame(parent, text="Process Options", padding="5")
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
    
    def _create_summarize_params(self, parent):
        """Create summarize-specific parameter entries."""
        summarize_frame = ttk.LabelFrame(parent, text="Summarization Options", padding="5")
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
    
    def process_task_queue(self):
        """Process tasks from the queue using thread pool."""
        while True:
            func, args = self.task_queue.get()
            try:
                self.executor.submit(func, *args)
            finally:
                self.task_queue.task_done()
    
    def perform_request(self, payload):
        """Execute the service bus request (called by worker thread)."""
        status_code, response_text = send_request(payload)
        if status_code is not None:
            message = f"\nStatus Code: {status_code}\nResponse:\n{response_text}\n"
        else:
            message = f"\nError sending request: {response_text}\n"
        self.after(0, lambda: self.output.insert(tk.END, message))
    
    def send_request(self):
        """Enqueue a service bus request for parallel processing."""
        self.output.delete(1.0, tk.END)
        
        # Build the request payload
        test_type = self.test_type_var.get()
        params = {}
        for param in self.params.values():
            result = param.get_value()
            if result:
                name, value = result
                params[name.replace("-", "_")] = value
                
        payload = build_request_payload(test_type, params, self.extra_params.get().strip())
        if payload is None:
            return
        
        self.output.insert(tk.END, f"Payload:\n{json.dumps(payload, indent=2)}\n\nEnqueuing request...\n")
        # Enqueue the request to be processed by the worker thread
        self.task_queue.put((self.perform_request, (payload,)))