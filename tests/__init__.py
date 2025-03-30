"""
Test package for podcast_summarizer.
Provides GUI and programmatic interfaces for testing both locally and in containers.
"""
from tests.gui_wrapper import TestGUI
from tests.local_tests import run_test as run_local_test
from tests.container_tests import run_test as run_container_test

__all__ = [
    'TestGUI',
    'run_local_test',
    'run_container_test'
]