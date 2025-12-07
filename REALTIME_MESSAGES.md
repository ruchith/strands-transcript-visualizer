# Real-Time Message Capture with Strands Hooks

## Summary

Yes, there **is** a way to output each LLM response and user response message pair from the Strands agent as it happens, rather than waiting for the end of the conversation.

## How It Works

Strands provides a **hooks system** that fires events during the agent's execution lifecycle. The key event for capturing messages in real-time is:

### `MessageAddedEvent`

This event is triggered whenever a message is added to the agent's conversation history. It fires:

1. **After LLM responses** - When the model generates a response (line 409 in `event_loop.py`)
2. **After tool results** - When tool execution results are added as user messages (line 515 in `event_loop.py`)

## Implementation

I've created a `MessageHookProvider` class that:

1. Implements the `HookProvider` protocol
2. Registers a callback for `MessageAddedEvent`
3. Saves messages immediately when they're added to the conversation
4. Supports both local filesystem and S3 storage (same as `CustomConversationManager`)

## Usage

### Basic Example

```python
from conversation_manager import MessageHookProvider
from strands.agent import Agent
from strands.models.anthropic import AnthropicModel

# Create the hook provider
message_hook = MessageHookProvider(
    storage_type="local",
    storage_path="conversations",
    agent_name="MyAgent",
)

# Create agent with the hook
agent = Agent(
    name="MyAgent",
    model=AnthropicModel(...),
    hooks=[message_hook],  # Pass hooks to agent
)

# Use the agent - messages will be saved in real-time
result = agent("Hello!")
```

### Combined with CustomConversationManager

You can use both together:

```python
from conversation_manager import CustomConversationManager, MessageHookProvider
from strands.agent import Agent

# Conversation manager for sliding window management
conversation_manager = CustomConversationManager(
    window_size=40,
    storage_type="local",
    storage_path="conversations",
)

# Hook provider for real-time message capture
message_hook = MessageHookProvider(
    storage_type="local",
    storage_path="conversations",
)

# Create agent with both
agent = Agent(
    name="MyAgent",
    model=model,
    conversation_manager=conversation_manager,
    hooks=[message_hook],
)
```

## Key Differences

| Approach | When Messages Are Saved | Use Case |
|----------|------------------------|----------|
| `CustomConversationManager.apply_management()` | At the end of the entire agent invocation | Batch processing, final state capture |
| `MessageHookProvider` (hooks) | Immediately when each message is added | Real-time monitoring, incremental logging |

## Events Available

Strands provides several other hook events you might find useful:

- `BeforeInvocationEvent` - Before agent starts processing
- `AfterInvocationEvent` - After agent completes
- `BeforeModelCallEvent` - Before model inference
- `AfterModelCallEvent` - After model inference (includes the message)
- `MessageAddedEvent` - When a message is added (what we use)
- `BeforeToolCallEvent` - Before tool execution
- `AfterToolCallEvent` - After tool execution

## Files Created

1. **`conversation_manager/message_hook_provider.py`** - The hook provider implementation
2. **`sample_agents/example_agent_with_hooks.py`** - Example showing how to use it
3. **`conversation_manager/__init__.py`** - Updated to export `MessageHookProvider`

## Testing

Run the example:

```bash
python sample_agents/example_agent_with_hooks.py
```

You should see messages being saved in real-time as the conversation progresses, rather than all at once at the end.

