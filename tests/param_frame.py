"""
GUI Parameter Frame Component for Podcast Summarizer Testing.
Provides a reusable frame containing a checkbox and entry field for parameters.
"""
import tkinter as tk
from tkinter import ttk

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