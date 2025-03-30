"""
GUI wrapper for podcast_summarizer test functionality.
Uses Tkinter for the interface and executes tests through command-line interface.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import sys
import os
from typing import Dict, Any, Optional
from pathlib import Path

# Add src to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
# Load the .env file from src directory
env_path = Path(__file__).parent.parent / 'src' / '.env'
load_dotenv(dotenv_path=env_path)

# Import local modules
import tests.local_tests as local_tests
import tests.container_tests as container_tests

class TestRunner:
    """Manages test execution and threading."""
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.queue = Queue()
        self.running = False

    def start(self):
        """Start processing the test queue."""
        self.running = True
        while self.running:
            try:
                test_func, args, kwargs, callback = self.queue.get(timeout=1)
                future = self.executor.submit(test_func, *args, **kwargs)
                future.add_done_callback(lambda f: callback(f.result()))
                self.queue.task_done()
            except:
                pass

    def stop(self):
        """Stop processing the test queue."""
        self.running = False
        self.executor.shutdown(wait=False)

    def add_test(self, test_func, callback, *args, **kwargs):
        """Add a test to the queue."""
        self.queue.put((test_func, args, kwargs, callback))

class TestGUI:
    """Main GUI interface for podcast summarizer testing."""
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Podcast Summarizer Test Suite")
        
        # Validate environment before setting up GUI
        env_valid, env_error = local_tests.validate_environment()
        if not env_valid:
            messagebox.showerror("Environment Error", 
                               f"Environment validation failed:\n{env_error}")
            self.root.quit()
            return
            
        self.setup_gui()
        self.runner = TestRunner()
        self.test_thread = threading.Thread(target=self.runner.start, daemon=True)
        self.test_thread.start()

    def setup_gui(self):
        """Setup the GUI components."""
        # Main container with scrollbar
        main_canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        # Environment Info Frame
        env_frame = ttk.LabelFrame(scrollable_frame, text="Environment", padding="5")
        env_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(env_frame, 
                 text=f"Using .env from: {env_path}").pack(anchor="w")

        # Environment Selection Frame
        env_select_frame = ttk.LabelFrame(scrollable_frame, text="Test Environment", padding="5")
        env_select_frame.pack(fill="x", padx=5, pady=5)

        self.env_var = tk.StringVar(value="local_source")
        environments = [
            ("Local Source Code", "local_source"),
            ("Local Container", "docker"),
            ("Cloud Container", "cloud")
        ]
        for text, value in environments:
            ttk.Radiobutton(env_select_frame, text=text, 
                          variable=self.env_var, value=value).pack(anchor="w")

        # Test Selection Frame
        test_frame = ttk.LabelFrame(scrollable_frame, text="Test Selection", padding="5")
        test_frame.pack(fill="x", padx=5, pady=5)

        self.test_vars = {
            'process': tk.BooleanVar(value=False),
            'summarize': tk.BooleanVar(value=False),
            'upsert': tk.BooleanVar(value=False),
            'email': tk.BooleanVar(value=False),
            'episode_email': tk.BooleanVar(value=False)
        }

        for test, var in self.test_vars.items():
            ttk.Checkbutton(test_frame, text=test.replace('_', ' ').title(), 
                           variable=var).pack(anchor="w")

        # Parameters Frame
        param_frame = ttk.LabelFrame(scrollable_frame, text="Parameters", padding="5")
        param_frame.pack(fill="x", padx=5, pady=5)

        # Common Parameters
        common_frame = ttk.LabelFrame(param_frame, text="Common", padding="5")
        common_frame.pack(fill="x", padx=5, pady=5)

        self.params = {}
        common_params = [
            ('feed_url', 'Feed URL'),
            ('user_id', 'User ID', 'c4859aa4-50f7-43bd-9ff2-16efed5bf133'),
            ('episode_id', 'Episode ID')
        ]
        self._add_parameters(common_frame, common_params)

        # Process Parameters
        process_frame = ttk.LabelFrame(param_frame, text="Process Options", padding="5")
        process_frame.pack(fill="x", padx=5, pady=5)

        process_params = [
            ('episode_indices', 'Episode Indices (e.g., 1,2,3-5)'),
            ('limit_episodes', 'Limit Episodes', '1'),
            ('split_size_mb', 'Split Size (MB)', '25.0')
        ]
        self._add_parameters(process_frame, process_params)
        self.params['include_transcription'] = tk.BooleanVar(value=True)
        ttk.Checkbutton(process_frame, text="Include Transcription", 
                       variable=self.params['include_transcription']).pack(anchor="w")

        # Summarization Parameters
        summarize_frame = ttk.LabelFrame(param_frame, text="Summarization Options", padding="5")
        summarize_frame.pack(fill="x", padx=5, pady=5)

        summarize_params = [
            ('custom_prompt', 'Custom Prompt'),
            ('chunk_size', 'Chunk Size', '4000'),
            ('chunk_overlap', 'Chunk Overlap', '200'),
            ('temperature', 'Temperature', '0.5')
        ]
        self._add_parameters(summarize_frame, summarize_params)

        # Method dropdown
        ttk.Label(summarize_frame, text="Method:").pack(anchor="w")
        self.params['method'] = ttk.Combobox(summarize_frame, 
                                           values=['auto', 'langchain', 'llamaindex', 'spacy', 'ensemble'])
        self.params['method'].set('auto')
        self.params['method'].pack(fill="x", padx=5, pady=2)

        # Detail level dropdown
        ttk.Label(summarize_frame, text="Detail Level:").pack(anchor="w")
        self.params['detail_level'] = ttk.Combobox(summarize_frame, 
                                                  values=['brief', 'standard', 'detailed'])
        self.params['detail_level'].set('standard')
        self.params['detail_level'].pack(fill="x", padx=5, pady=2)

        # Upsert Parameters
        upsert_frame = ttk.LabelFrame(param_frame, text="Upsert Options", padding="5")
        upsert_frame.pack(fill="x", padx=5, pady=5)

        upsert_params = [
            ('description', 'Description', 'Custom description for testing purposes')
        ]
        self._add_parameters(upsert_frame, upsert_params)

        # Parser type dropdown
        ttk.Label(upsert_frame, text="Parser Type:").pack(anchor="w")
        self.params['parser_type'] = ttk.Combobox(upsert_frame, 
                                                 values=['auto', 'rss', 'crawler'])
        self.params['parser_type'].set('auto')
        self.params['parser_type'].pack(fill="x", padx=5, pady=2)

        # Output Frame
        output_frame = ttk.LabelFrame(scrollable_frame, text="Output", padding="5")
        output_frame.pack(fill="x", padx=5, pady=5)

        self.output = scrolledtext.ScrolledText(output_frame, height=15, width=80)
        self.output.pack(fill="both", expand=True)

        # Control Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill="x", pady=5)

        ttk.Button(button_frame, text="Run Tests", 
                  command=self.run_tests).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Clear Output", 
                  command=self.clear_output).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Quit", 
                  command=self.quit).pack(side="left", padx=5)

        # Pack the scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        main_canvas.pack(side="left", fill="both", expand=True)

    def _add_parameters(self, parent, params):
        """Helper method to add parameter fields."""
        for param in params:
            name, label = param[:2]
            default = param[2] if len(param) > 2 else ''
            
            ttk.Label(parent, text=label).pack(anchor="w")
            entry = ttk.Entry(parent)
            entry.insert(0, default)
            entry.pack(fill="x", padx=5, pady=2)
            self.params[name] = entry

    def log(self, message: str):
        """Add message to output text widget."""
        self.output.insert(tk.END, f"{message}\n")
        self.output.see(tk.END)

    def get_params(self) -> Dict[str, Any]:
        """Get parameters from entry fields."""
        params = {}
        for name, widget in self.params.items():
            if isinstance(widget, (ttk.Entry, ttk.Combobox)):
                params[name] = widget.get()
            elif isinstance(widget, tk.BooleanVar):
                params[name] = widget.get()
        return params

    def handle_test_result(self, test_name: str, result: Any):
        """Handle test completion and update GUI."""
        if isinstance(result, tuple):
            success, output = result
            status = "Success" if success else "Failed"
            self.log(f"\n{test_name}: {status}")
            if output:
                self.log(output)
        else:
            self.log(f"\n{test_name}: {'Success' if result else 'Failed'}")

    def run_tests(self):
        """Execute selected tests."""
        params = self.get_params()
        environment = self.env_var.get()
        self.log(f"\n=== Starting Tests (Environment: {environment}) ===")

        def run_test_wrapper(test_type: str, **kwargs):
            if environment == "local_source":
                return local_tests.run_test(test_type, **kwargs)
            else:
                return container_tests.run_test(test_type, environment, **kwargs)

        if self.test_vars['process'].get():
            process_params = {
                'feed_url': params['feed_url'],
                'limit_episodes': int(params['limit_episodes']),
                'episode_indices': params['episode_indices'],
                'split_size_mb': float(params['split_size_mb']),
                'include_transcription': params['include_transcription']
            }
            self.runner.add_test(
                run_test_wrapper,
                lambda r: self.handle_test_result("Process Podcast", r),
                "process",
                **process_params
            )

        if self.test_vars['summarize'].get():
            summarize_params = {
                'episode_id': params['episode_id'],
                'custom_prompt': params['custom_prompt'],
                'chunk_size': int(params['chunk_size']),
                'chunk_overlap': int(params['chunk_overlap']),
                'method': params['method'],
                'detail_level': params['detail_level'],
                'temperature': float(params['temperature']),
                'user_id': params['user_id']
            }
            self.runner.add_test(
                run_test_wrapper,
                lambda r: self.handle_test_result("Summarize Episode", r),
                "summarize",
                **summarize_params
            )

        if self.test_vars['upsert'].get():
            upsert_params = {
                'feed_url': params['feed_url'],
                'description': params['description'],
                'parser_type': params['parser_type']
            }
            self.runner.add_test(
                run_test_wrapper,
                lambda r: self.handle_test_result("Upsert Podcast", r),
                "upsert",
                **upsert_params
            )

        if self.test_vars['email'].get():
            self.runner.add_test(
                run_test_wrapper,
                lambda r: self.handle_test_result("Send User Emails", r),
                "email",
                user_id=params['user_id']
            )

        if self.test_vars['episode_email'].get():
            self.runner.add_test(
                run_test_wrapper,
                lambda r: self.handle_test_result("Send Episode Email", r),
                "episode_email",
                user_id=params['user_id'],
                episode_id=params['episode_id']
            )

    def clear_output(self):
        """Clear the output text widget."""
        self.output.delete(1.0, tk.END)

    def quit(self):
        """Clean up and close the application."""
        self.runner.stop()
        self.root.quit()

    def run(self):
        """Start the GUI application."""
        self.root.mainloop()

if __name__ == "__main__":
    gui = TestGUI()
    gui.run()