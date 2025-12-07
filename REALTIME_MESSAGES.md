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
4. Supports both local filesystem and S3 storage
5. Saves each message to a separate file to avoid duplicates

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

## Message File Format

Each message is saved to a separate file with the format:
```
{timestamp}-{agent_name}-msg{number}-{role}.json
```

Example files:
- `20251207092953789343-MyAgent-msg1-user.json`
- `20251207092955819317-MyAgent-msg2-assistant.json`
- `20251207092955886093-MyAgent-msg3-user.json`

Each file contains a single message object. The visualizer can consolidate these files into a conversation for visualization.

## Key Features

- **Real-time capture**: Messages are saved immediately when added to the conversation
- **Duplicate prevention**: Tracks message signatures to avoid saving duplicates
- **Separate files**: Each message is saved to its own file for easy tracking
- **Storage options**: Supports both local filesystem and S3 storage

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
3. **`sample_agents/file_report_agent_with_hooks.py`** - File report agent example with hooks
4. **`conversation_manager/__init__.py`** - Updated to export `MessageHookProvider`
5. **`visualizer/hook_message_visualizer.py`** - Visualizer for hook message files
6. **`visualizer/generate_hook_report.py`** - CLI script for hook message visualization

## Testing

Run the example:

```bash
python sample_agents/example_agent_with_hooks.py
```

You should see messages being saved in real-time as the conversation progresses, with each message saved to a separate file.

## Visualization

To visualize messages from hook files, use the `HookMessageVisualizer`:

```bash
# Visualize all messages from a directory
python visualizer/generate_hook_report.py conversations/

# Filter by agent name
python visualizer/generate_hook_report.py conversations/ --agent-name MyAgent
```

See `HOOK_VISUALIZER.md` for more details on visualizing hook message files.

