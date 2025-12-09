"""Repository analysis agent that analyzes GitHub repositories.

This agent:
1. Takes a GitHub repo URL as input
2. Clones the repo into a temporary directory
3. Uses Strands default tools (editor, file_read, shell) to explore the repository
4. Creates a high-level profile including architecture and main components
5. Studies git history to identify patterns and conventions
6. Saves analysis to llm_analysis/ directory in the repository
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Optional

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

# Set BYPASS_TOOL_CONSENT to allow all tools to run without permission prompts
# This enables automatic tool execution without user confirmation
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Add parent directory to path to import message hook provider
sys.path.insert(0, str(Path(__file__).parent.parent))

from hooks import MessageHookProvider, CachePointHookProvider

try:
    from strands.agent import Agent
    from strands.models.anthropic import AnthropicModel
    from strands.tools.decorator import tool
    from strands.types.content import SystemContentBlock
except ImportError:
    raise ImportError(
        "Could not import Strands Agent, AnthropicModel, or tool decorator. "
        "Please ensure strands-agents is installed: pip install strands-agents"
    )

# Import Strands default tools
try:
    from strands_tools import editor, file_read, shell
except ImportError:
    raise ImportError(
        "Could not import Strands default tools (editor, file_read, shell). "
        "Please ensure strands-agents-tools is installed: pip install strands-agents-tools"
    )


@tool
def clone_repository(repo_url: str, target_dir: str) -> dict:
    """Clone a GitHub repository to a target directory.
    
    Args:
        repo_url: GitHub repository URL (e.g., https://github.com/user/repo.git)
        target_dir: Directory path where the repository should be cloned
    
    Returns:
        Dictionary with status and information about the cloned repository
    """
    import subprocess
    
    target_path = Path(target_dir)
    
    # Remove target directory if it exists
    if target_path.exists():
        shutil.rmtree(target_path)
    
    target_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Clone the repository
        result = subprocess.run(
            ["git", "clone", repo_url, str(target_path)],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr,
                "stdout": result.stdout,
            }
        
        # Get repository information
        repo_name = target_path.name
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        
        return {
            "success": True,
            "repo_url": repo_url,
            "target_dir": str(target_path),
            "repo_name": repo_name,
            "message": f"Repository cloned successfully to {target_path}",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Repository clone timed out after 5 minutes",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@tool
def get_git_log(repo_dir: str, max_commits: int = 100) -> dict:
    """Get git commit history for a repository.
    
    Args:
        repo_dir: Path to the repository directory
        max_commits: Maximum number of commits to retrieve (default: 100)
    
    Returns:
        Dictionary containing commit history information
    """
    import subprocess
    
    repo_path = Path(repo_dir)
    
    if not repo_path.exists() or not (repo_path / ".git").exists():
        return {
            "success": False,
            "error": f"Repository directory {repo_dir} does not exist or is not a git repository",
        }
    
    try:
        # Get commit log with detailed information
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "log",
                f"--max-count={max_commits}",
                "--pretty=format:%H|%an|%ae|%ad|%s",
                "--date=iso",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr,
            }
        
        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|", 4)
                if len(parts) == 5:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "date": parts[3],
                        "message": parts[4],
                    })
        
        # Get file change statistics
        stats_result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "log",
                f"--max-count={max_commits}",
                "--stat",
                "--format=",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        return {
            "success": True,
            "commits": commits,
            "total_commits": len(commits),
            "stats": stats_result.stdout if stats_result.returncode == 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Git log command timed out",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def create_repo_analysis_agent(
    anthropic_api_key: str = None,
    model: str = "claude-sonnet-4-5",
    max_tokens: int = 32000,
    storage_type: str = "local",
    storage_path: str = "conversations",
    s3_bucket: str = None,
    use_realtime_hooks: bool = True,
    enable_cache_points: bool = True,
):
    """Create an agent that analyzes GitHub repositories.
    
    Args:
        anthropic_api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        model: Anthropic model ID (default: "claude-sonnet-4-5" - Claude Sonnet 4.5)
        max_tokens: Maximum tokens for model responses (default: 8192)
        storage_type: Storage backend type ('local' or 's3')
        storage_path: Local directory path or S3 prefix
        s3_bucket: S3 bucket name (required if storage_type is 's3')
        use_realtime_hooks: Whether to use real-time message hooks (default: True)
        enable_cache_points: Whether to add cachePoint to (n-2)nd messages (default: True)
    
    Returns:
        Configured Agent instance with repository analysis tools and real-time message capture
    """
    # Get API key from parameter or environment
    api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "Anthropic API key is required. "
            "Set ANTHROPIC_API_KEY environment variable or pass it as a parameter."
        )
    
    # Initialize Anthropic LLM with specified model (using Sonnet for better analysis)
    llm = AnthropicModel(
        client_args={"api_key": api_key},
        model_id=model,
        max_tokens=max_tokens,
    )
    
    # Create system prompt with prompt caching enabled
    # Prompt caching reduces token usage by caching the system prompt across requests
    system_prompt_content = [
        SystemContentBlock(
            text=(
                "You are an expert codebase analysis agent. Your role is to analyze GitHub repositories "
                "by exploring their structure, understanding their architecture, and identifying patterns "
                "and conventions. Use the available tools (clone_repository, get_git_log, file_read, editor, shell) "
                "to thoroughly explore repositories and create comprehensive analysis documents."
            )
        ),
        SystemContentBlock(cachePoint={"type": "default"}),  # Enable prompt caching
    ]
    
    # Create hooks list
    hooks = []
    
    # Add cache point hook provider to optimize token usage
    if enable_cache_points:
        cache_point_hook = CachePointHookProvider(enabled=True)
        hooks.append(cache_point_hook)
    
    # Add real-time message hook provider if requested
    if use_realtime_hooks:
        message_hook = MessageHookProvider(
            storage_type=storage_type,
            storage_path=storage_path,
            s3_bucket=s3_bucket,
            agent_name="RepoAnalysisAgent",
        )
        hooks.append(message_hook)
    
    # Create agent with custom tools and Strands default tools (editor, file_read, shell)
    # Imported from strands_tools package - see https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/
    agent = Agent(
        name="RepoAnalysisAgent",
        model=llm,
        system_prompt=system_prompt_content,  # Use system prompt with caching enabled
        tools=[
            clone_repository,  # Custom tool for cloning repositories
            get_git_log,       # Custom tool for git history analysis
            editor,            # Strands default tool for file editing
            file_read,         # Strands default tool for reading files
            shell,             # Strands default tool for shell commands
        ],
        hooks=hooks,  # Pass hooks for real-time message capture
    )
    
    return agent


def analyze_repository(
    repo_url: str,
    agent: Optional[Agent] = None,
    temp_dir: Optional[str] = None,
    cleanup: bool = True,
) -> dict:
    """Analyze a GitHub repository and create analysis files.
    
    Args:
        repo_url: GitHub repository URL to analyze
        agent: Optional pre-configured agent (if None, creates a new one)
        temp_dir: Optional temporary directory for cloning (if None, uses system temp)
        cleanup: Whether to clean up the temporary directory after analysis (default: True)
    
    Returns:
        Dictionary with analysis results and file paths
    """
    # Create agent if not provided
    if agent is None:
        agent = create_repo_analysis_agent()
    
    # Create temporary directory for cloning
    if temp_dir is None:
        temp_base = tempfile.gettempdir()
        temp_dir = os.path.join(temp_base, f"repo_analysis_{os.getpid()}")
    
    temp_path = Path(temp_dir)
    temp_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Create the analysis prompt
        prompt = f"""
Analyze the GitHub repository at: {repo_url}

Your task is to:
1. Clone the repository to {temp_dir} using the clone_repository tool
2. Explore the repository structure using Strands default tools (file_read, editor, shell)
3. Study the git history using the get_git_log tool
4. Create a comprehensive analysis with two parts:

PART 1: High-Level Architecture and Components
Create a file called 'architecture.md' in the llm_analysis directory that includes:
- Overall architecture of the codebase
- Main implementation components and their roles
- Technology stack and key dependencies
- Directory structure and organization
- Key modules and their relationships

PART 2: Patterns and Conventions
Create a file called 'patterns_and_conventions.md' in the llm_analysis directory that includes:
- Coding patterns identified from the codebase
- Naming conventions (files, functions, classes, variables)
- Code organization patterns
- Architectural patterns and design principles
- Evolution patterns from git history analysis
- Style conventions and best practices observed

WORKFLOW:
1. First, clone the repository using clone_repository tool with URL: {repo_url} and target_dir: {temp_dir}
2. Use shell commands to explore the directory structure (ls, find, etc.)
3. Read key files using file_read tool (README, setup files, main entry points, etc.)
4. Use get_git_log tool to analyze commit history and understand evolution
5. Explore important directories and files to understand the codebase
6. Create the llm_analysis directory in the repository root
7. Use the editor tool to create and write architecture.md with your findings
8. Use the editor tool to create and write patterns_and_conventions.md with your findings

IMPORTANT:
- Be thorough and systematic in your exploration
- Read configuration files, README files, and main entry points first
- Use shell commands strategically to find important files
- Analyze multiple commits to identify patterns over time
- Write clear, well-structured markdown documents
- The llm_analysis directory should be created at: {temp_dir}/<repo_name>/llm_analysis/
"""
        
        print(f"Starting repository analysis for: {repo_url}")
        print(f"Temporary directory: {temp_dir}\n")
        
        # Run the agent
        result = agent(prompt)
        
        # Extract response
        message = result.message
        content_blocks = message.get("content", [])
        response_texts = []
        for block in content_blocks:
            if "text" in block:
                response_texts.append(block["text"])
        response = " ".join(response_texts) if response_texts else str(result)
        
        # Find the cloned repository directory
        repo_dirs = [d for d in temp_path.iterdir() if d.is_dir() and (d / ".git").exists()]
        repo_path = repo_dirs[0] if repo_dirs else None
        
        # Check if analysis files were created
        analysis_dir = None
        architecture_file = None
        patterns_file = None
        
        if repo_path:
            analysis_dir = repo_path / "llm_analysis"
            if analysis_dir.exists():
                architecture_file = analysis_dir / "architecture.md"
                patterns_file = analysis_dir / "patterns_and_conventions.md"
        
        return {
            "success": True,
            "repo_url": repo_url,
            "repo_path": str(repo_path) if repo_path else None,
            "analysis_dir": str(analysis_dir) if analysis_dir else None,
            "architecture_file": str(architecture_file) if architecture_file and architecture_file.exists() else None,
            "patterns_file": str(patterns_file) if patterns_file and patterns_file.exists() else None,
            "response": response,
            "temp_dir": temp_dir,
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "temp_dir": temp_dir,
        }
    
    finally:
        # Cleanup if requested
        if cleanup and temp_path.exists():
            try:
                shutil.rmtree(temp_path)
                print(f"\nCleaned up temporary directory: {temp_dir}")
            except Exception as e:
                print(f"\nWarning: Could not clean up temporary directory: {e}")


def main():
    """Run the repository analysis agent."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze a GitHub repository and create architecture and patterns documentation"
    )
    parser.add_argument(
        "repo_url",
        type=str,
        help="GitHub repository URL to analyze (e.g., https://github.com/user/repo.git)",
    )
    parser.add_argument(
        "--temp-dir",
        type=str,
        default=None,
        help="Temporary directory for cloning (default: system temp)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't clean up temporary directory after analysis",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-5",
        help="Anthropic model to use (default: claude-sonnet-4-5)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8192,
        help="Maximum tokens for model responses (default: 8192)",
    )
    
    args = parser.parse_args()
    
    print("Creating repository analysis agent...")
    
    try:
        # Create agent
        agent = create_repo_analysis_agent(
            model=args.model,
            max_tokens=args.max_tokens,
        )
        
        print("\nAgent created successfully!")
        print("Real-time message capture is enabled.")
        print("Messages will be saved immediately as they're added to the conversation.\n")
        
        # Analyze repository
        result = analyze_repository(
            repo_url=args.repo_url,
            agent=agent,
            temp_dir=args.temp_dir,
            cleanup=not args.no_cleanup,
        )
        
        if result["success"]:
            print("\n" + "=" * 80)
            print("ANALYSIS COMPLETE")
            print("=" * 80)
            print(f"Repository: {result['repo_url']}")
            if result["repo_path"]:
                print(f"Repository path: {result['repo_path']}")
            if result["analysis_dir"]:
                print(f"Analysis directory: {result['analysis_dir']}")
            if result["architecture_file"]:
                print(f"✓ Architecture file: {result['architecture_file']}")
            if result["patterns_file"]:
                print(f"✓ Patterns file: {result['patterns_file']}")
            
            if not args.no_cleanup:
                print("\nNote: Temporary directory has been cleaned up.")
                print("If you want to keep the files, use --no-cleanup flag.")
            else:
                print(f"\nRepository files preserved at: {result['temp_dir']}")
        else:
            print(f"\nError: {result.get('error', 'Unknown error')}")
            sys.exit(1)
        
        print("\nConversation completed!")
        print(f"Messages have been saved in real-time to the 'conversations' directory.")
        print("Check the directory for files named: <timestamp>-RepoAnalysisAgent-msg<number>-<role>.json")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

