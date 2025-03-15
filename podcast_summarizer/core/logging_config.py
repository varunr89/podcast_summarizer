"""
Configure logging for the podcast summarizer package.
"""
import logging
import os
import sys
from pathlib import Path
from typing import Optional

def setup_logger(
    name: str, 
    level: int = logging.INFO,
    log_dir: Optional[str] = None,
    log_to_console: bool = True,
    log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
) -> logging.Logger:
    """
    Set up a logger with file and console handlers.
    
    Args:
        name: Logger name
        level: Logging level
        log_dir: Directory for log files (None to disable file logging)
        log_to_console: Whether to log to console
        log_format: Format string for log messages
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    formatter = logging.Formatter(log_format)
    
    # Add file handler if log_dir is specified
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path / f"{name}.log")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Add console handler if requested
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger for a module, or create one if it doesn't exist.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # If logger doesn't have handlers, set it up
    if not logger.handlers:
        # Default to logs directory under the project root
        project_root = Path(__file__).parent.parent
        log_dir = project_root / "logs"
        
        return setup_logger(
            name=name,
            log_dir=str(log_dir),
            log_to_console=True
        )
    
    return logger
