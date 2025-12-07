"""Sample agent that lists files in ~/Downloads and creates a metadata report.

This agent uses file tools to get file metadata (not contents) and creates a report.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load .env file from project root
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Try loading from current directory
        load_dotenv()
except ImportError:
    # python-dotenv not installed, skip loading .env file
    pass

# Add parent directory to path to import custom conversation manager
sys.path.insert(0, str(Path(__file__).parent.parent))

from conversation_manager import CustomConversationManager

try:
    from strands.agent import Agent
    from strands.models.anthropic import AnthropicModel
    from strands.tools.decorator import tool
except ImportError:
    raise ImportError(
        "Could not import Strands Agent, AnthropicModel, or tool decorator. "
        "Please ensure strands-agents is installed: pip install strands-agents"
    )


@tool
def list_directory_files(directory_path: str) -> List[Dict[str, Any]]:
    """List all files in a directory and return their metadata.
    
    This function lists files in the specified directory and returns metadata
    including name, size, modification time, and file type. It does NOT read
    file contents - only metadata.
    
    Args:
        directory_path: Path to the directory to list files from (e.g., ~/Downloads)
    
    Returns:
        List of dictionaries containing file metadata:
        - name: File name
        - size: File size in bytes (None for directories)
        - modified: Last modification time (ISO format)
        - is_file: Boolean indicating if it's a file (True) or directory (False)
        - extension: File extension (if applicable, None for directories)
    """
    files_metadata = []
    dir_path = Path(directory_path).expanduser()
    
    if not dir_path.exists():
        return [{"error": f"Directory does not exist: {directory_path}"}]
    
    if not dir_path.is_dir():
        return [{"error": f"Path is not a directory: {directory_path}"}]
    
    try:
        for item in dir_path.iterdir():
            try:
                stat = item.stat()
                metadata = {
                    "name": item.name,
                    "size": stat.st_size if item.is_file() else None,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "is_file": item.is_file(),
                    "extension": item.suffix if item.is_file() else None,
                }
                files_metadata.append(metadata)
            except (OSError, PermissionError) as e:
                # Skip files we can't access
                files_metadata.append({
                    "name": item.name,
                    "error": f"Cannot access: {str(e)}"
                })
    except PermissionError as e:
        return [{"error": f"Permission denied: {str(e)}"}]
    
    return files_metadata


def create_file_report_agent(
    anthropic_api_key: str = None,
    model: str = "claude-3-5-haiku-20241022",
    max_tokens: int = 4096,
    storage_type: str = "local",
    storage_path: str = "conversations",
    s3_bucket: str = None,
):
    """Create an agent that can list files and create reports.
    
    Args:
        anthropic_api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        model: Anthropic model ID (default: "claude-3-5-haiku-20241022" - Claude Haiku 3.5)
        max_tokens: Maximum tokens for model responses (default: 4096)
        storage_type: Storage backend type ('local' or 's3')
        storage_path: Local directory path or S3 prefix
        s3_bucket: S3 bucket name (required if storage_type is 's3')
    
    Returns:
        Configured Agent instance with file listing tools
    """
    # Get API key from parameter or environment
    api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "Anthropic API key is required. "
            "Set ANTHROPIC_API_KEY environment variable or pass it as a parameter."
        )
    
    # Initialize Anthropic LLM with specified model
    llm = AnthropicModel(
        client_args={"api_key": api_key},
        model_id=model,
        max_tokens=max_tokens,
    )
    
    # Initialize custom conversation manager
    conversation_manager = CustomConversationManager(
        window_size=40,
        should_truncate_results=True,
        storage_type=storage_type,
        storage_path=storage_path,
        s3_bucket=s3_bucket,
    )
    
    # Create agent with the file listing tool (decorated function)
    agent = Agent(
        name="FileReportAgent",
        model=llm,
        conversation_manager=conversation_manager,
        tools=[list_directory_files],  # Pass the decorated function directly
    )
    
    return agent


def main():
    """Run the file report agent to analyze ~/Downloads directory."""
    print("Creating file report agent...")
    
    try:
        # Create agent with local storage
        agent = create_file_report_agent(
            storage_type="local",
            storage_path="conversations",
        )
        
        print("\nAgent created successfully!")
        print("Analyzing ~/Downloads directory...\n")
        
        # Get the Downloads directory path
        downloads_path = os.path.expanduser("~/Downloads")
        
        # Ask the agent to create a report
        prompt = (
            f"Please analyze the files in the {downloads_path} directory. "
            "Use the list_directory_files tool to get file metadata. "
            "Create a comprehensive report that includes: "
            "1. Total number of files and directories "
            "2. Total size of all files "
            "3. Breakdown by file type/extension "
            "4. List of the largest files "
            "5. List of the most recently modified files "
            "6. If you see any sub directories use the list_directory_files tool to get the metadata of the sub directories"
            "IMPORTANT: Do NOT read file contents - only use metadata (name, size, modification time)."
        )
        
        print(f"Prompt: {prompt}\n")
        result = agent(prompt)
        
        # Extract text from AgentResult.message.content
        message = result.message
        content_blocks = message.get("content", [])
        response = " ".join(block.get("text", "") for block in content_blocks if "text" in block)
        
        print("=" * 80)
        print("FILE REPORT")
        print("=" * 80)
        print(response)
        print("=" * 80)
        
        print("\nConversation completed!")
        print(f"Messages have been saved to the 'conversations' directory.")
        print("Check the directory for files named: <timestamp>-FileReportAgent.json")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

