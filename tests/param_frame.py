"""
Parameter frame component for GUI interfaces.
Provides a frame with checkbox and entry field for parameter input.
"""
import tkinter as tk
from tkinter import ttk

class ParamFrame(ttk.Frame):
    """A frame containing a checkbox and entry field for a parameter."""
    def __init__(self, parent, param_name, label_text, default_value=""):
        """Initialize the parameter frame.
        
        Args:
            parent: Parent widget
            param_name: Name of the parameter (used in API calls)
            label_text: Display text for the checkbox
            default_value: Optional default value for the entry field
        """
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
        """Set the enabled state of the checkbox.
        
        Args:
            enabled: True to check the box, False to uncheck
        """
        self.enabled.set(enabled)
            
    def get_value(self):
        """Get the parameter value if enabled.
        
        Returns:
            Tuple of (param_name, value) if enabled and has value, None otherwise
        """
        if self.enabled.get():
            value = self.entry.get().strip()
            if value:
                return (self.param_name, value)
        return None