"""
Launcher script for the Podcast Summarizer Test Interface.
"""
from .command_creator_gui import CommandCreator

if __name__ == "__main__":
    app = CommandCreator()
    app.run()