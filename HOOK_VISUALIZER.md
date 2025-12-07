# Hook Message Visualizer

## Overview

The `HookMessageVisualizer` is a specialized visualizer that works with the separate message files created by `MessageHookProvider`. Unlike the standard `ConversationVisualizer` which expects a single JSON file with all messages, this visualizer:

1. **Finds and consolidates** separate message files (one per message)
2. **Sorts messages** by message number extracted from filenames
3. **Creates a JSON array** of all messages
4. **Uses the same visualization logic** as `ConversationVisualizer` to generate interactive HTML graphs

## Message File Format

MessageHookProvider creates files with the format:
```
{timestamp}-{agent_name}-msg{number}-{role}.json
```

Example:
- `20251207092953789343-FileReportAgentWithHooks-msg1-user.json`
- `20251207092955819317-FileReportAgentWithHooks-msg2-assistant.json`
- `20251207092955886093-FileReportAgentWithHooks-msg3-user.json`

Each file contains a single message object (the same format as messages in a conversation array).

## Usage

### Command Line

#### Visualize from Directory

The simplest way is to point the visualizer at a directory containing message files:

```bash
python visualizer/generate_hook_report.py conversations/
```

This will:
- Find all `*-msg*.json` files in the directory
- Sort them by message number
- Consolidate them into a conversation
- Generate an HTML visualization

#### Filter by Agent Name

If you have multiple agents' messages in the same directory:

```bash
python visualizer/generate_hook_report.py conversations/ --agent-name FileReportAgentWithHooks
```

#### Create Consolidated JSON

You can also create a consolidated JSON file (compatible with the standard visualizer):

```bash
python visualizer/generate_hook_report.py conversations/ \
    --consolidate-json conversations/consolidated.json
```

### Python API

```python
from visualizer import HookMessageVisualizer

# Create visualizer
visualizer = HookMessageVisualizer(output_dir="visualizations")

# Option 1: Visualize from directory
output_path = visualizer.visualize_from_directory(
    directory="conversations",
    agent_name="FileReportAgentWithHooks",  # Optional
)

# Option 2: Visualize from specific files
message_files = [
    "conversations/20251207092953789343-FileReportAgentWithHooks-msg1-user.json",
    "conversations/20251207092955819317-FileReportAgentWithHooks-msg2-assistant.json",
    # ... more files
]
output_path = visualizer.visualize_from_files(message_files)

# Option 3: Create consolidated JSON
json_path = visualizer.create_consolidated_json(
    message_files,
    output_path="conversations/consolidated.json"
)
```

## How It Works

1. **File Discovery**: Uses glob patterns to find message files matching the format
2. **Sorting**: Extracts message numbers from filenames (e.g., `msg1`, `msg2`) and sorts files accordingly
3. **Consolidation**: Loads each message file and combines them into a single array
4. **Visualization**: Reuses `ConversationVisualizer` logic to parse messages and generate the HTML graph

## Output

The visualizer generates the same interactive HTML visualization as `ConversationVisualizer`:
- Interactive directed graph showing conversation flow
- Clickable nodes to view message content
- Two-column layout with messages panel and graph panel
- Color-coded nodes by message type

## Differences from ConversationVisualizer

| Feature | ConversationVisualizer | HookMessageVisualizer |
|---------|----------------------|---------------------|
| Input | Single JSON file with message array | Multiple files (one per message) |
| File Discovery | Manual file selection | Automatic discovery from directory |
| Sorting | N/A (already sorted in file) | Sorts by message number from filename |
| Consolidation | N/A | Consolidates multiple files into array |

## Example Workflow

1. **Run agent with MessageHookProvider**:
   ```python
   from conversation_manager import MessageHookProvider
   from strands.agent import Agent
   
   message_hook = MessageHookProvider(
       storage_type="local",
       storage_path="conversations",
   )
   
   agent = Agent(
       name="MyAgent",
       model=model,
       hooks=[message_hook],
   )
   
   result = agent("Hello!")
   ```

2. **Visualize the conversation**:
   ```bash
   python visualizer/generate_hook_report.py conversations/ --agent-name MyAgent
   ```

3. **Open the HTML file** in your browser to view the interactive graph.

