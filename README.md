# Trajectory Visualizer for Strands Agents

A comprehensive toolkit for capturing, storing, and visualizing conversations from [Strands Agents](https://strandsagents.com/). This project includes:

1. **Custom Conversation Manager**: Extends Strands' `SlidingWindowConversationManager` to automatically capture and store agent messages
2. **Message Hook Provider**: Real-time message capture using Strands hooks - saves each message immediately as it's added
3. **Example Agents**: Demonstrates how to use both conversation managers and hooks with Anthropic's Claude
4. **HTML Visualizers**: Creates interactive directed graphs of agent conversations with clickable nodes to view message contents

## Features

- ✅ Automatic message capture and storage
- ✅ Real-time message capture with hooks (saves messages immediately)
- ✅ Local filesystem storage (default)
- ✅ S3 bucket storage support
- ✅ Interactive HTML visualizations
- ✅ Support for multiple conversation files
- ✅ Support for separate message files (from hooks)
- ✅ Color-coded message roles
- ✅ Clickable nodes to view full message content

## Installation

1. Clone this repository:
```bash
git clone https://github.com/ruchith/strands-transcript-visualizer.git
cd trajectory_visualizer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

## Quick Start

### 1. Using the Example Agent

Run the example agent to generate conversation files:

```bash
python sample_agents/example_agent.py
```

This will:
- Create an agent using Anthropic's Claude
- Run example conversations
- Save conversation files to the `conversations/` directory in the format: `<timestamp>-ExampleAgent.json`

### 2. Visualizing Conversations

Generate an HTML visualization from message files:

```bash
# Visualize all messages from a directory
python visualizer/generate_report.py conversations/

# Filter by agent name
python visualizer/generate_report.py conversations/ --agent-name MyAgent

# Specify output filename
python visualizer/generate_report.py conversations/ -o my_visualization.html
```

The visualization will be saved to the `visualizations/` directory and includes:
- **Markdown rendering** for message content
- **JSON formatting** for tool inputs/results
- **Color-coded boxes** for inputs (blue) and results (green)
- **Interactive graph** showing conversation flow

## Usage

### Custom Conversation Manager

The `CustomConversationManager` extends Strands' `SlidingWindowConversationManager` and automatically saves messages after each update.

#### Local Storage (Default)

```python
from conversation_manager import CustomConversationManager
from strands.agent import Agent
from strands.models.anthropic import AnthropicModel

# Create conversation manager with local storage
conversation_manager = CustomConversationManager(
    window_size=40,
    storage_type="local",
    storage_path="conversations",  # Directory to save files
)

# Create agent
llm = AnthropicModel(
    client_args={"api_key": os.getenv("ANTHROPIC_API_KEY")},
    model_id="claude-3-5-haiku-20241022",
    max_tokens=4096,  # Set max_tokens for response length
)
agent = Agent(
    name="MyAgent",
    model=llm,
    conversation_manager=conversation_manager,
)

# Use the agent - messages will be automatically saved
# Agent is callable - use agent(prompt) to invoke
result = agent("Hello!")
# Extract text from AgentResult.message.content
message = result.message
content_blocks = message.get("content", [])
response = " ".join(block.get("text", "") for block in content_blocks if "text" in block)
```

#### S3 Storage

```python
from conversation_manager import CustomConversationManager

# Create conversation manager with S3 storage
conversation_manager = CustomConversationManager(
    window_size=40,
    storage_type="s3",
    storage_path="conversations",  # S3 prefix
    s3_bucket="my-bucket-name",
)

# Ensure AWS credentials are configured (via environment variables, IAM role, etc.)
# The manager will use boto3 to save files to S3
```

### Message Hook Provider (Real-Time Capture)

The `MessageHookProvider` uses Strands' hooks system to capture messages in real-time, saving each message immediately when it's added to the conversation. Each message is saved to a separate file.

#### Local Storage (Default)

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

#### S3 Storage

```python
from conversation_manager import MessageHookProvider

# Create hook provider with S3 storage
message_hook = MessageHookProvider(
    storage_type="s3",
    storage_path="conversations",  # S3 prefix
    s3_bucket="my-bucket-name",
)

# Create agent with the hook
agent = Agent(
    name="MyAgent",
    model=model,
    hooks=[message_hook],
)
```

#### Message File Format

Each message is saved to a separate file:
- Format: `{timestamp}-{agent_name}-msg{number}-{role}.json`
- Example: `20251207092953789343-MyAgent-msg1-user.json`
- Each file contains a single message object

See `REALTIME_MESSAGES.md` for more details on real-time message capture.

### Example Agent

The example agent demonstrates how to integrate the custom conversation manager:

```python
from sample_agents.example_agent import create_example_agent

# Create agent with local storage
agent = create_example_agent(
    storage_type="local",
    storage_path="conversations",
)

# Or with S3 storage
agent = create_example_agent(
    storage_type="s3",
    storage_path="conversations",
    s3_bucket="my-bucket",
)

# Use the agent
result = agent("What is machine learning?")
# Extract text from AgentResult.message.content
message = result.message
content_blocks = message.get("content", [])
response = " ".join(block.get("text", "") for block in content_blocks if "text" in block)
```

### Visualizer

#### Using the CLI

```bash
# Visualize all messages from a directory
python visualizer/generate_report.py conversations/

# Filter by agent name
python visualizer/generate_report.py conversations/ --agent-name MyAgent

# Specify output filename
python visualizer/generate_report.py conversations/ -o my_visualization.html

# Specify output directory
python visualizer/generate_report.py conversations/ --output-dir my_visualizations
```

#### Using the Python API

```python
from visualizer import ConversationVisualizer, HookMessageVisualizer

# Option 1: Visualize from hook message files (separate message files)
hook_viz = HookMessageVisualizer(output_dir="visualizations")

# Find and consolidate messages
message_files = hook_viz.find_message_files("conversations", agent_name="MyAgent")
conversation = hook_viz.consolidate_messages(message_files)

# Create visualization
visualizer = ConversationVisualizer(output_dir="visualizations")
output_path = visualizer.create_visualization(
    messages=conversation["messages"],
    agent_name=conversation["agent_name"],
    timestamp=conversation["timestamp"],
)

print(f"Visualization saved to: {output_path}")
```

## File Format

Conversation files are stored in JSON format with the following structure:

```json
[
  {
    "role": "user",
    "content": "Hello, how can you help me?"
  },
  {
    "role": "assistant",
    "content": "I'm here to help! What would you like to know?"
  }
]
```

Files are named using the format: `<timestamp>-<agent_name>.json`

Example: `20250107143022-ExampleAgent.json`

## Configuration

### Environment Variables

Create a `.env` file (see `.env.example`) with:

- `ANTHROPIC_API_KEY`: Your Anthropic API key (required)
- `AWS_ACCESS_KEY_ID`: AWS access key (required for S3 storage)
- `AWS_SECRET_ACCESS_KEY`: AWS secret key (required for S3 storage)
- `AWS_DEFAULT_REGION`: AWS region (optional, defaults to us-east-1)

### Conversation Manager Options

- `window_size`: Maximum number of messages in the sliding window (default: 40)
- `should_truncate_results`: Whether to truncate when window is exceeded (default: True)
- `storage_type`: Storage backend - `"local"` or `"s3"` (default: `"local"`)
- `storage_path`: Local directory or S3 prefix (default: `"conversations"`)
- `s3_bucket`: S3 bucket name (required if `storage_type` is `"s3"`)

## Visualization Features

The HTML visualizer provides:

- **Horizontal Graph Flow**: Conversation nodes displayed left-to-right showing progression
- **Color Coding**:
  - Blue nodes: Initial user requests
  - Orange nodes: Tool executions (showing tool names)
  - Green nodes: Final assistant responses
- **Detailed Side Panel**: Click any node to view:
  - Full message content with **markdown rendering**
  - Tool inputs (blue boxes) with **JSON formatting**
  - Tool results (green boxes) with **JSON formatting** or markdown
- **Interactive Navigation**: Click nodes in the graph or details panel to explore the conversation
- **No External Dependencies**: Self-contained HTML with only marked.js from CDN

## Project Structure

```
trajectory_visualizer/
├── conversation_manager/
│   ├── __init__.py
│   ├── custom_conversation_manager.py
│   └── message_hook_provider.py
├── sample_agents/
│   ├── __init__.py
│   ├── example_agent.py
│   ├── example_agent_with_hooks.py
│   └── file_report_agent_with_hooks.py
├── visualizer/
│   ├── __init__.py
│   ├── conversation_visualizer.py
│   ├── hook_message_visualizer.py
│   └── generate_report.py
├── requirements.txt
├── README.md
├── REALTIME_MESSAGES.md
└── .env.example
```

## Dependencies

- `strands-agents`: Strands Agents SDK
- `anthropic`: Anthropic SDK for Claude
- `boto3`: AWS SDK for S3 support
- `python-dotenv`: Environment variable management

**Note**: The visualizer uses only pure Python with no additional dependencies. The generated HTML includes marked.js from CDN for markdown rendering.

## Troubleshooting

### Import Errors

If you encounter import errors for Strands classes, ensure you have the latest version:

```bash
pip install --upgrade strands-agents
```

The import paths may vary depending on the Strands version. The code includes fallback import attempts.

### S3 Storage Issues

Ensure AWS credentials are properly configured:

```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret

# Option 2: AWS credentials file
aws configure

# Option 3: IAM role (if running on EC2)
```

### Visualization Not Displaying

The visualization is a self-contained HTML file. Simply open it in any modern web browser. No additional dependencies are required.

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## References

- [Strands Agents Documentation](https://strandsagents.com/latest/)
- [Strands Agents GitHub](https://github.com/strands-agents/sdk-python)
- [Anthropic API Documentation](https://docs.anthropic.com/)

