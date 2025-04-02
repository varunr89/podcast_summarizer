"""
Test script for the refactored command creator GUI and its components.
"""
import tkinter as tk
from .param_frame import ParamFrame
from .service_bus_frame import ServiceBusFrame
from .command_creator_gui import CommandCreator
from .command_processor import build_test_command, build_request_payload, send_request
from .gui_wrapper import GUIWrapper

def test_param_frame():
    """Test the ParamFrame component."""
    root = tk.Tk()
    frame = ParamFrame(root, "test-param", "Test Parameter", "default")
    frame.pack()
    frame.set_enabled(True)
    assert frame.get_value() == ("test-param", "default")
    root.destroy()

def test_command_generation():
    """Test command generation functionality."""
    enabled_params = [
        ("feed-url", "https://example.com/feed.xml"),
        ("limit-episodes", "2")
    ]
    command = build_test_command("process", enabled_params, "", "local_source")
    assert "python src/api_test.py --test-process" in command
    assert "--feed-url https://example.com/feed.xml" in command
    assert "--limit-episodes 2" in command

def test_request_payload():
    """Test request payload building."""
    params = {
        "feed_url": "https://example.com/feed.xml",
        "limit_episodes": "2"
    }
    payload = build_request_payload("process", params)
    assert payload["target_path"] == "/process-podcast"
    assert payload["feed_url"] == "https://example.com/feed.xml"
    assert payload["limit_episodes"] == 2

def test_gui_wrapper():
    """Test the GUI wrapper functionality."""
    wrapper = GUIWrapper()
    wrapper.set_environment("local_source")
    wrapper.set_test_type("process")
    wrapper.set_parameter("feed-url", "https://example.com/feed.xml")
    wrapper.set_parameter("limit-episodes", "2")
    command = wrapper.get_generated_command()
    assert "python src/api_test.py --test-process" in command
    assert "--feed-url https://example.com/feed.xml" in command
    assert "--limit-episodes 2" in command

if __name__ == "__main__":
    print("Running tests...")
    test_param_frame()
    test_command_generation()
    test_request_payload()
    test_gui_wrapper()
    print("All tests passed!")