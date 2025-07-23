"""
Container-based test execution for podcast summarizer.
Constructs and executes Docker commands that run api_test.py inside a container.
"""
import subprocess
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

def build_api_test_command(test_type: str, **kwargs) -> str:
    """
    Build the api_test.py command string with appropriate arguments.
    
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
            cmd.extend(["--feed-url", f'"{str(kwargs["feed_url"])}"'])
        if "limit_episodes" in kwargs:
            cmd.extend(["--limit-episodes", str(kwargs["limit_episodes"])])
        if "episode_indices" in kwargs:
            cmd.extend(["--episode-indices", f'"{str(kwargs["episode_indices"])}"'])
        if "split_size_mb" in kwargs:
            cmd.extend(["--split-size-mb", str(kwargs["split_size_mb"])])
        if "include_transcription" in kwargs:
            if kwargs["include_transcription"]:
                cmd.append("--include-transcription")
                
    elif test_type == "summarize":
        cmd.append("--test-summarize")
        if "episode_id" in kwargs:
            cmd.extend(["--episode-id", f'"{str(kwargs["episode_id"])}"'])
        if "custom_prompt" in kwargs:
            cmd.extend(["--custom-prompt", f'"{str(kwargs["custom_prompt"])}"'])
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
            cmd.extend(["--feed-url", f'"{str(kwargs["feed_url"])}"'])
        if "description" in kwargs:
            cmd.extend(["--description", f'"{str(kwargs["description"])}"'])
        if "parser_type" in kwargs:
            cmd.extend(["--parser-type", str(kwargs["parser_type"])])
            
    elif test_type == "email":
        cmd.append("--test-email")
        
    elif test_type == "episode_email":
        cmd.append("--test-episode-email")
    
    # Add common parameters
    if "user_id" in kwargs:
        cmd.extend(["--user-id", f'"{str(kwargs["user_id"])}"'])
    if "episode_id" in kwargs and test_type != "summarize":  # Already added for summarize
        cmd.extend(["--episode-id", f'"{str(kwargs["episode_id"])}"'])
        
    return " ".join(cmd)

def build_docker_command(api_test_cmd: str, env_path: Path) -> str:
    """
    Build the complete Docker command that executes api_test.py in a container.
    
    Args:
        api_test_cmd: The api_test.py command string
        env_path: Path to the .env file
        
    Returns:
        Complete Docker command string
    """
    # Convert Windows path to proper format and escape spaces
    env_file_path = str(env_path).replace('\\', '/')
    if ' ' in env_file_path:
        env_file_path = f'"{env_file_path}"'

    docker_cmd = [
        "docker", "run", "-it", "--rm",
        "--env-file", env_file_path,
        "podcast_summarizer",
        "bash", "-c",
        f"uvicorn src.podcast_summarizer.api.main:app --host 0.0.0.0 --port 80 & sleep 3 && {api_test_cmd}"
    ]
    return " ".join(docker_cmd)

def run_test(test_type: str, environment: str = "docker", **kwargs) -> Tuple[bool, Optional[str]]:
    """
    Run a test in the specified container environment.
    
    Args:
        test_type: Type of test to run
        environment: Environment to run the test in ("docker" or "cloud")
        **kwargs: Test parameters
        
    Returns:
        Tuple of (success: bool, output: Optional[str])
    """
    try:
        # Validate environment
        env_valid, env_error = validate_environment()
        if not env_valid:
            return False, env_error
            
        env_path = Path(__file__).parent.parent / 'src' / '.env.example'
        
        # Build the api_test.py command
        api_test_cmd = build_api_test_command(test_type, **kwargs)
        
        if environment == "docker":
            # Build the complete Docker command
            cmd = build_docker_command(api_test_cmd, env_path)
            
            # Print the commands that will be executed
            print("\n=== Container Test Commands ===")
            print("API Test Command:")
            print(api_test_cmd)
            print("\nDocker Command:")
            print(cmd)
            print("============================\n")
            
            # Execute the Docker command
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
            
        elif environment == "cloud":
            print("\n=== Cloud Container Test (Not Implemented) ===")
            print("Would execute command:")
            print(api_test_cmd)
            print("=========================================\n")
            return False, "Cloud container testing not implemented yet"
            
        else:
            return False, f"Unknown environment: {environment}"
            
    except Exception as e:
        return False, f"Error executing command: {str(e)}"

def validate_environment() -> Tuple[bool, Optional[str]]:
    """
    Validate that the container environment is properly configured.
    
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
            
        # Check if Docker is available
        result = subprocess.run(["docker", "--version"], 
                             capture_output=True, 
                             text=True)
        if result.returncode != 0:
            return False, "Docker is not available or not running"
            
        return True, None
        
    except Exception as e:
        return False, f"Environment validation failed: {str(e)}"