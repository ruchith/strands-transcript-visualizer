"""Example agent using Strands with real-time message hooks.

This example demonstrates how to use MessageHookProvider to capture messages
as they're added to the conversation in real-time, rather than waiting for
the end of the conversation.
"""

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

# Add parent directory to path to import message hook provider
sys.path.insert(0, str(Path(__file__).parent.parent))

from conversation_manager import MessageHookProvider

try:
    from strands.agent import Agent
    from strands.models.anthropic import AnthropicModel
except ImportError:
    raise ImportError(
        "Could not import Strands Agent or AnthropicModel. "
        "Please ensure strands-agents is installed: pip install strands-agents"
    )


def create_example_agent_with_hooks(
    anthropic_api_key: str = None,
    model: str = "claude-3-5-haiku-20241022",
    max_tokens: int = 4096,
    storage_type: str = "local",
    storage_path: str = "conversations",
    s3_bucket: str = None,
    use_realtime_hooks: bool = True,
):
    """Create an example agent with real-time message hooks.
    
    Args:
        anthropic_api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        model: Anthropic model ID (default: "claude-3-5-haiku-20241022" - Claude Haiku 3.5)
        max_tokens: Maximum tokens for model responses (default: 4096)
        storage_type: Storage backend type ('local' or 's3')
        storage_path: Local directory path or S3 prefix
        s3_bucket: S3 bucket name (required if storage_type is 's3')
        use_realtime_hooks: Whether to use real-time message hooks (default: True)
    
    Returns:
        Configured Agent instance with real-time message capture
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
    
    # Create hooks list
    hooks = []
    
    # Add real-time message hook provider if requested
    if use_realtime_hooks:
        message_hook = MessageHookProvider(
            storage_type=storage_type,
            storage_path=storage_path,
            s3_bucket=s3_bucket,
            agent_name="ExampleAgentWithHooks",
        )
        hooks.append(message_hook)
    
    # Create agent with hooks only (no custom conversation manager)
    # Strands will use the default SlidingWindowConversationManager for conversation management
    agent = Agent(
        name="ExampleAgentWithHooks",
        model=llm,
        hooks=hooks,  # Pass hooks to agent for real-time message capture
    )
    
    return agent


def main():
    """Run example agent with real-time message hooks."""
    print("Creating example agent with real-time message hooks...")
    
    try:
        # Create agent with real-time hooks enabled
        agent = create_example_agent_with_hooks(
            storage_type="local",
            storage_path="conversations",
            use_realtime_hooks=True,
        )
        
        print("\nAgent created successfully!")
        print("Real-time message capture is enabled.")
        print("Messages will be saved immediately as they're added to the conversation.\n")
        print("Starting example conversation...\n")
        
        # Example interactions
        questions = [
            "Hello! Can you tell me a fun fact about space?",
            "What is the capital of France?",
        ]
        
        for i, question in enumerate(questions, 1):
            print(f"Question {i}: {question}")
            # Agent is callable - use agent(prompt) instead of agent.run(prompt)
            result = agent(question)
            # Extract text from AgentResult.message.content
            message = result.message
            content_blocks = message.get("content", [])
            # Extract text from content blocks
            response_texts = []
            for block in content_blocks:
                if "text" in block:
                    response_texts.append(block["text"])
            response = " ".join(response_texts) if response_texts else str(result)
            print(f"Response: {response}\n")
            print("(Message was saved in real-time when it was added)\n")
        
        print("Conversation completed!")
        print(f"Messages have been saved in real-time to the 'conversations' directory.")
        print("Check the directory for files named: <timestamp>-ExampleAgentWithHooks-msg<number>-<role>.json")
        print("\nNote: Each message (LLM response and tool results) was saved immediately")
        print("to a separate file when it was added to the conversation, not at the end.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

