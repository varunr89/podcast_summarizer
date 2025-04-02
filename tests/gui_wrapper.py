"""
GUI Wrapper for Podcast Summarizer Testing.
Provides a wrapper around the command creator GUI for automated testing.
"""
from .command_creator_gui import CommandCreator
from .command_processor import build_test_command, build_request_payload, send_request

class GUIWrapper:
    """Wrapper class for automated testing of the CommandCreator GUI."""
    def __init__(self):
        self.app = CommandCreator()
    
    def set_environment(self, env_type: str):
        """Set the test environment type."""
        if env_type in ["local_source", "docker", "cloud", "service_bus"]:
            self.app.env_var.set(env_type)
            self.app.on_env_change()
    
    def set_test_type(self, test_type: str):
        """Set the test type and update parameter visibility."""
        if test_type in ["process", "summarize", "upsert", "email", "episode_email"]:
            self.app.test_type_var.set(test_type)
            self.app.on_test_type_change()
    
    def set_parameter(self, param_name: str, value: str, enabled: bool = True):
        """Set a parameter's value and enabled state."""
        if param_name in self.app.params:
            param_frame = self.app.params[param_name]
            param_frame.set_enabled(enabled)
            param_frame.entry.delete(0, 'end')
            param_frame.entry.insert(0, value)
    
    def set_extra_params(self, params: str):
        """Set additional command-line parameters."""
        self.app.extra_params.delete(0, 'end')
        self.app.extra_params.insert(0, params)
    
    def get_generated_command(self) -> str:
        """Generate and return the command without copying to clipboard."""
        # Collect enabled parameters
        enabled_params = []
        for param in self.app.params.values():
            result = param.get_value()
            if result:
                enabled_params.append(result)
        
        # Build and return the command
        return build_test_command(
            self.app.test_type_var.get(),
            enabled_params,
            self.app.extra_params.get().strip(),
            self.app.env_var.get()
        )
    
    def send_service_bus_request(self) -> tuple:
        """Send a request through the service bus and return the response."""
        # Collect parameters
        params = {}
        for param in self.app.params.values():
            result = param.get_value()
            if result:
                name, value = result
                params[name.replace("-", "_")] = value
        
        # Build payload and send request
        payload = build_request_payload(
            self.app.test_type_var.get(),
            params,
            self.app.extra_params.get().strip()
        )
        
        if payload is not None:
            return send_request(payload)
        return None, "Failed to build payload"
    
    def run(self):
        """Start the GUI application."""
        self.app.run()

# Example usage
if __name__ == "__main__":
    # Create wrapper instance
    wrapper = GUIWrapper()
    
    # Configure test parameters
    wrapper.set_environment("local_source")
    wrapper.set_test_type("process")
    wrapper.set_parameter("feed-url", "https://example.com/feed.xml")
    wrapper.set_parameter("limit-episodes", "2")
    
    # Generate command
    command = wrapper.get_generated_command()
    print(f"Generated Command: {command}")
    
    # Or run the GUI
    wrapper.run()