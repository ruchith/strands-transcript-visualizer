"""Example agent using Strands with Anthropic and custom conversation manager."""

import os
import sys
from pathlib import Path

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
except ImportError:
    raise ImportError(
        "Could not import Strands Agent or AnthropicModel. "
        "Please ensure strands-agents is installed: pip install strands-agents"
    )


def create_example_agent(
    anthropic_api_key: str = None,
    model: str = "claude-3-5-haiku-20241022",
    max_tokens: int = 4096,
    storage_type: str = "local",
    storage_path: str = "conversations",
    s3_bucket: str = None,
):
    """Create an example agent with custom conversation manager.
    
    Args:
        anthropic_api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        model: Anthropic model ID (default: "claude-3-5-haiku-20241022" - Claude Haiku 3.5)
        max_tokens: Maximum tokens for model responses (default: 4096)
        storage_type: Storage backend type ('local' or 's3')
        storage_path: Local directory path or S3 prefix
        s3_bucket: S3 bucket name (required if storage_type is 's3')
    
    Returns:
        Configured Agent instance
    """
    # Get API key from parameter or environment
    api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "Anthropic API key is required. "
            "Set ANTHROPIC_API_KEY environment variable or pass it as a parameter."
        )
    
    # Initialize Anthropic LLM with specified model
    # client_args contains the API key, model_config contains model_id and max_tokens
    llm = AnthropicModel(
        client_args={"api_key": api_key},
        model_id=model,
        max_tokens=max_tokens,  # Set max_tokens for response length
    )
    
    # Initialize custom conversation manager
    conversation_manager = CustomConversationManager(
        window_size=40,
        should_truncate_results=True,
        storage_type=storage_type,
        storage_path=storage_path,
        s3_bucket=s3_bucket,
    )
    
    # Create agent (Agent takes 'model' not 'llm')
    agent = Agent(
        name="ExampleAgent",
        model=llm,
        conversation_manager=conversation_manager,
    )
    
    return agent


def main():
    """Run example agent interactions."""
    print("Creating example agent...")
    
    try:
        # Create agent with local storage
        agent = create_example_agent(storage_type="local", storage_path="conversations")
        
        print("\nAgent created successfully!")
        print("Starting example conversation...\n")
        
        # Example interactions
        questions = [
            "Hello! Can you tell me a fun fact about space?",
            "What is the capital of France?",
            "Can you explain what machine learning is in simple terms?",
        ]
        
        for i, question in enumerate(questions, 1):
            print(f"Question {i}: {question}")
            # Agent is callable - use agent(prompt) instead of agent.run(prompt)
            result = agent(question)
            # Extract text from AgentResult.message.content
            # Message.content is a list of ContentBlock objects (TypedDict)
            message = result.message
            content_blocks = message.get("content", [])
            # Extract text from content blocks
            response_texts = []
            for block in content_blocks:
                # ContentBlock is a TypedDict, access text directly
                if "text" in block:
                    response_texts.append(block["text"])
            response = " ".join(response_texts) if response_texts else str(result)
            print(f"Response: {response}\n")
        
        print("Conversation completed!")
        print(f"Messages have been saved to the 'conversations' directory.")
        print("Check the directory for files named: <timestamp>-ExampleAgent.json")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

