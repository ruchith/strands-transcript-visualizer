# Trajectory Visualizer for Strands Agents

A comprehensive toolkit for capturing, storing, and visualizing conversations from [Strands Agents](https://strandsagents.com/). This project includes:

1. **Custom Conversation Manager**: Extends Strands' `SlidingWindowConversationManager` to automatically capture and store agent messages
2. **Example Agent**: Demonstrates how to use the custom conversation manager with Anthropic's Claude
3. **HTML Visualizer**: Creates interactive directed graphs of agent conversations with clickable nodes to view message contents

## Features

- ✅ Automatic message capture and storage
- ✅ Local filesystem storage (default)
- ✅ S3 bucket storage support
- ✅ Interactive HTML visualizations
- ✅ Support for multiple conversation files
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

Generate an HTML visualization from conversation files:

```bash
python visualizer/generate_report.py conversations/*.json
```

Or specify individual files:

```bash
python visualizer/generate_report.py conversations/20250107143022-ExampleAgent.json
```

The visualization will be saved to the `visualizations/` directory.

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
# Visualize a single conversation
python visualizer/generate_report.py conversations/20250107143022-ExampleAgent.json

# Visualize multiple conversations
python visualizer/generate_report.py conversations/*.json

# Specify output filename
python visualizer/generate_report.py conversations/*.json -o my_visualization.html

# Specify output directory
python visualizer/generate_report.py conversations/*.json --output-dir my_visualizations
```

#### Using the Python API

```python
from visualizer.conversation_visualizer import ConversationVisualizer

# Create visualizer
visualizer = ConversationVisualizer(output_dir="visualizations")

# Visualize conversation files
output_path = visualizer.visualize(
    conversation_files=[
        "conversations/20250107143022-ExampleAgent.json",
        "conversations/20250107143023-ExampleAgent.json",
    ],
    output_filename="my_report.html",
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

- **Directed Graph**: Messages are shown as nodes connected in chronological order
- **Color Coding**: Different colors for user (blue), assistant (green), system (red), and tool (orange) messages
- **Interactive Nodes**: Click on any node to view the full message content in a popup viewer
- **Multiple Conversations**: Visualize multiple conversation files in a single graph
- **Timeline View**: Messages are arranged to show the conversation flow

## Project Structure

```
trajectory_visualizer/
├── conversation_manager/
│   ├── __init__.py
│   └── custom_conversation_manager.py
├── sample_agents/
│   ├── __init__.py
│   └── example_agent.py
├── visualizer/
│   ├── __init__.py
│   ├── conversation_visualizer.py
│   └── generate_report.py
├── requirements.txt
├── README.md
└── .env.example
```

## Dependencies

- `strands-agents`: Strands Agents SDK
- `anthropic`: Anthropic SDK for Claude
- `boto3`: AWS SDK for S3 support
- `networkx`: Graph structure library
- `pyvis`: Interactive network visualization
- `python-dotenv`: Environment variable management

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

Make sure you have all visualization dependencies:

```bash
pip install networkx pyvis
```

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## References

- [Strands Agents Documentation](https://strandsagents.com/latest/)
- [Strands Agents GitHub](https://github.com/strands-agents/sdk-python)
- [Anthropic API Documentation](https://docs.anthropic.com/)

