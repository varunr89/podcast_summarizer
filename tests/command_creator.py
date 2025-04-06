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
from pathlib import Path
import queue

# Add src to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import the cloud interface and local modules
from podcast_summarizer_gui import PodcastSummarizerFrame
from .param_frame import ParamFrame
from .param_validator import ValidationError
from .command_processor import build_request_payload, send_request
from .service_bus_frame import ServiceBusFrame

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
        try:
            # Build and validate the payload first to catch any parameter issues
            params_dict = {name: value for name, value in params}
            build_request_payload(test_type, params_dict, self.extra_params.get().strip())
            
            # If validation passes, construct the command
            cmd = [f"--test-{test_type}"]
            for param, value in params:
                cmd.append(f"--{param} {value}")
            
            # Add any extra parameters
            extra = self.extra_params.get().strip()
            if extra:
                cmd.append(extra)
            
            return " ".join(cmd)
            
        except ValidationError as e:
            self.output.insert(tk.END, f"Error: {str(e)}\n")
            return None
        except Exception as e:
            self.output.insert(tk.END, f"Unexpected error: {str(e)}\n")
            return None
    
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
        
        # Build and validate the api_test.py command part
        api_cmd = self.build_api_test_command(test_type, enabled_params)
        if api_cmd is None:
            return None
        
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
        self.output.delete(1.0, tk.END)
        
        try:
            command = self.generate_command()
            if command is None:
                return
            
            # Display the command and success message
            self.output.insert(tk.END, f"{command}\n\nCommand copied to clipboard!")
            
            # Copy to clipboard
            self.root.clipboard_clear()
            self.root.clipboard_append(command)
            
        except ValidationError as e:
            self.output.insert(tk.END, f"Error: {str(e)}\n")
        except Exception as e:
            self.output.insert(tk.END, f"Unexpected error: {str(e)}\n")
    
    def run(self):
        """Start the GUI."""
        self.root.mainloop()

if __name__ == "__main__":
    app = CommandCreator()
    app.run()