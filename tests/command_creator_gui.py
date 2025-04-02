"""
Main GUI application for Podcast Summarizer Testing.
Creates terminal commands for local/docker tests, embeds the cloud interface,
and provides a Cloud Service Bus tab for parallel request processing.
"""
import tkinter as tk
from tkinter import ttk

from .param_frame import ParamFrame
from .service_bus_frame import ServiceBusFrame
from .command_processor import build_test_command
from ..podcast_summarizer_gui import PodcastSummarizerFrame

class CommandCreator:
    """Main GUI class for creating test commands and running cloud tests."""
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Podcast Summarizer Test Interface")
        
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill='both', expand=True)
        
        # Create the interface components
        self._create_env_selection(main_frame)
        self._create_notebook(main_frame)
        
        # Set default tab based on environment
        self.on_env_change()
    
    def _create_env_selection(self, parent):
        """Create the environment selection frame."""
        env_frame = ttk.LabelFrame(parent, text="Test Environment", padding="5")
        env_frame.pack(fill="x", padx=5, pady=5)
        
        self.env_var = tk.StringVar(value="local_source")
        environments = [
            ("Local Source", "local_source"),
            ("Local Container", "docker"),
            ("Cloud", "cloud"),
            ("Cloud Service Bus", "service_bus")
        ]
        
        for text, value in environments:
            ttk.Radiobutton(env_frame, text=text, 
                          variable=self.env_var, 
                          value=value,
                          command=self.on_env_change).pack(side=tk.LEFT, padx=5)
    
    def _create_notebook(self, parent):
        """Create the notebook with all tabs."""
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Command Generation tab
        self.cmd_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.cmd_tab, text="Generate Command")
        self._build_command_tab()
        
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
    
    def _build_command_tab(self):
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
        type_frame = self._create_test_type_frame(scrollable_frame)
        type_frame.pack(fill="x", padx=5, pady=5)
        
        # Parameters Frame
        param_frame = self._create_param_frame(scrollable_frame)
        param_frame.pack(fill="x", padx=5, pady=5)
        
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
        
        self.output = tk.Text(output_frame, width=80, height=10, wrap=tk.WORD)
        self.output.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Pack the scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Initialize parameter states
        self.on_test_type_change()
    
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
        
        # Create parameter entries
        self.params = {}
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
    
    def generate_and_copy_command(self):
        """Generate the command and copy it to clipboard."""
        # Collect enabled parameters
        enabled_params = []
        for param in self.params.values():
            result = param.get_value()
            if result:
                enabled_params.append(result)
        
        # Build the command
        command = build_test_command(
            self.test_type_var.get(),
            enabled_params,
            self.extra_params.get().strip(),
            self.env_var.get()
        )
        
        # Display the command and success message
        self.output.delete(1.0, tk.END)
        self.output.insert(tk.END, f"{command}\n\nCommand copied to clipboard!")
        
        # Copy to clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(command)
    
    def on_env_change(self):
        """Handle environment selection changes."""
        env = self.env_var.get()
        if env == "cloud":
            self.notebook.select(self.cloud_tab)
        elif env == "service_bus":
            self.notebook.select(self.service_bus_tab)
        else:
            self.notebook.select(self.cmd_tab)
    
    def run(self):
        """Start the GUI."""
        self.root.mainloop()

if __name__ == "__main__":
    app = CommandCreator()
    app.run()