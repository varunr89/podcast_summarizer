"""
Local test execution for podcast summarizer.
Constructs and executes command-line strings for api_test.py.
"""
import subprocess
import os
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

def build_command(test_type: str, **kwargs) -> str:
    """
    Build the command string for api_test.py with appropriate arguments.
    
    Args:
        test_type: Type of test to run
        **kwargs: Test parameters
        
    Returns:
        Complete command string for api_test.py
    """
    cmd = ["python", "src/api_test.py"]
    
    # Add test type flag
    if test_type == "process":
        cmd.append("--test-process")
        if "feed_url" in kwargs:
            cmd.extend(["--feed-url", str(kwargs["feed_url"])])
        if "limit_episodes" in kwargs:
            cmd.extend(["--limit-episodes", str(kwargs["limit_episodes"])])
        if "episode_indices" in kwargs:
            cmd.extend(["--episode-indices", str(kwargs["episode_indices"])])
        if "split_size_mb" in kwargs:
            cmd.extend(["--split-size-mb", str(kwargs["split_size_mb"])])
        if "include_transcription" in kwargs:
            if kwargs["include_transcription"]:
                cmd.append("--include-transcription")
                
    elif test_type == "summarize":
        cmd.append("--test-summarize")
        if "episode_id" in kwargs:
            cmd.extend(["--episode-id", str(kwargs["episode_id"])])
        if "custom_prompt" in kwargs:
            cmd.extend(["--custom-prompt", str(kwargs["custom_prompt"])])
        if "chunk_size" in kwargs:
            cmd.extend(["--chunk-size", str(kwargs["chunk_size"])])
        if "chunk_overlap" in kwargs:
            cmd.extend(["--chunk-overlap", str(kwargs["chunk_overlap"])])
        if "method" in kwargs:
            cmd.extend(["--method", str(kwargs["method"])])
        if "detail_level" in kwargs:
            cmd.extend(["--detail-level", str(kwargs["detail_level"])])
        if "temperature" in kwargs:
            cmd.extend(["--temperature", str(kwargs["temperature"])])
            
    elif test_type == "upsert":
        cmd.append("--test-upsert")
        if "feed_url" in kwargs:
            cmd.extend(["--feed-url", str(kwargs["feed_url"])])
        if "description" in kwargs:
            cmd.extend(["--description", str(kwargs["description"])])
        if "parser_type" in kwargs:
            cmd.extend(["--parser-type", str(kwargs["parser_type"])])
            
    elif test_type == "email":
        cmd.append("--test-email")
        
    elif test_type == "episode_email":
        cmd.append("--test-episode-email")
    
    # Add common parameters
    if "user_id" in kwargs:
        cmd.extend(["--user-id", str(kwargs["user_id"])])
    if "episode_id" in kwargs and test_type != "summarize":  # Already added for summarize
        cmd.extend(["--episode-id", str(kwargs["episode_id"])])
        
    return " ".join(cmd)

def run_test(test_type: str, **kwargs) -> Tuple[bool, Optional[str]]:
    """
    Run a test by constructing and executing a command string.
    
    Args:
        test_type: Type of test to run
        **kwargs: Test parameters
        
    Returns:
        Tuple of (success: bool, output: Optional[str])
    """
    try:
        # Build the command string
        cmd = build_command(test_type, **kwargs)
        
        # Print the command that will be executed
        print("\n=== Local Test Command ===")
        print(cmd)
        print("=========================\n")
        
        # Execute the command
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        
        # Prepare the output string
        output = []
        if result.stdout:
            output.append("Standard Output:")
            output.append(result.stdout)
        if result.stderr:
            output.append("Standard Error:")
            output.append(result.stderr)
            
        output_str = "\n".join(output)
        
        # Return success based on return code, and the output
        return result.returncode == 0, output_str
        
    except Exception as e:
        return False, f"Error executing command: {str(e)}"

def validate_environment() -> Tuple[bool, Optional[str]]:
    """
    Validate that the local environment is properly configured.
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        env_path = Path(__file__).parent.parent / 'src' / '.env.example'
        if not env_path.exists():
            return False, f"Environment file not found at: {env_path}"
            
        required_vars = [
            "WHISPER_API_KEY",
            "WHISPER_ENDPOINT",
            "WHISPER_DEPLOYMENT_NAME",
            "WHISPER_API_VERSION",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_ENDPOINT",
            "DEEPSEEK_MODEL",
            "DEEPSEEK_API_VERSION",
            "AZURE_STORAGE_CONNECTION_STRING",
            "AZURE_STORAGE_CONTAINER_NAME",
            "AZURECONNECTIONSTRING",
            "SENDER_EMAIL",
            "RECEIVER_EMAIL",
            "EMBEDDINGS_API_KEY",
            "EMBEDDINGS_ENDPOINT",
            "EMBEDDINGS_MODEL"
        ]
        
        with open(env_path) as f:
            env_contents = f.read()
            
        found_vars = set()
        for line in env_contents.splitlines():
            if '=' in line and not line.strip().startswith('#'):
                var_name = line.split('=')[0].strip()
                found_vars.add(var_name)
        
        missing_vars = [var for var in required_vars if var not in found_vars]
        if missing_vars:
            return False, f"Missing required variables in .env.example: {', '.join(missing_vars)}"
            
        return True, None
        
    except Exception as e:
        return False, f"Environment validation failed: {str(e)}"
            "WHISPER_API_KEY",
            "WHISPER_ENDPOINT",
            "WHISPER_DEPLOYMENT_NAME",
            "WHISPER_API_VERSION",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_ENDPOINT",
            "DEEPSEEK_MODEL",
            "DEEPSEEK_API_VERSION",
            "AZURE_STORAGE_CONNECTION_STRING",
            "AZURE_STORAGE_CONTAINER_NAME",
            "AZURECONNECTIONSTRING",
            "SENDER_EMAIL",
            "RECEIVER_EMAIL",
            "EMBEDDINGS_API_KEY",
            "EMBEDDINGS_ENDPOINT",
            "EMBEDDINGS_MODEL"
        ]
        
        with open(env_path) as f:
            env_contents = f.read()
            
        found_vars = set()
        for line in env_contents.splitlines():
            if '=' in line and not line.strip().startswith('#'):
                var_name = line.split('=')[0].strip()
                found_vars.add(var_name)
        
        missing_vars = [var for var in required_vars if var not in found_vars]
        if missing_vars:
            return False, f"Missing required variables in .env.example: {', '.join(missing_vars)}"
            
        return True, None
        
    except Exception as e:
        return False, f"Environment validation failed: {str(e)}"