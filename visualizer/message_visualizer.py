"""HTML visualizer for agent conversations from MessageHookProvider output files.

This visualizer works with the separate message files created by MessageHookProvider,
where each message is saved to its own file. It consolidates these files into a
conversation array and creates interactive HTML visualizations.
"""

import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class MessageVisualizer:
    """Creates interactive HTML visualizations from MessageHookProvider message files.
    
    This class handles finding message files, consolidating them into conversations,
    and generating interactive HTML visualizations.
    """
    
    def __init__(self, output_dir: str = "visualizations"):
        """Initialize the visualizer.
        
        Args:
            output_dir: Directory to save generated HTML files
        """
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
    
    def find_message_files(
        self,
        directory: str,
        agent_name: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> List[str]:
        """Find all message files in a directory.
        
        Args:
            directory: Directory to search for message files
            agent_name: Optional agent name to filter by (if None, finds all agents)
            pattern: Optional glob pattern to match files (default: *-msg*.json)
        
        Returns:
            List of file paths to message files, sorted by message number
        """
        directory_path = Path(directory)
        if not directory_path.exists():
            raise ValueError(f"Directory does not exist: {directory}")
        
        # Default pattern matches MessageHookProvider filename format
        if pattern is None:
            if agent_name:
                # Filter by agent name
                safe_agent_name = "".join(c for c in agent_name if c.isalnum() or c in ("-", "_"))
                pattern = f"*-{safe_agent_name}-msg*.json"
            else:
                pattern = "*-msg*.json"
        
        # Find all matching files
        message_files = list(directory_path.glob(pattern))
        
        # Sort by message number extracted from filename
        def extract_message_number(filepath: Path) -> int:
            """Extract message number from filename.
            
            Format: <timestamp>-<agent_name>-msg<number>-<role>.json
            """
            filename = filepath.name
            # Match pattern: -msg<number>-
            match = re.search(r'-msg(\d+)-', filename)
            if match:
                return int(match.group(1))
            # Fallback: use timestamp if message number not found
            # Extract timestamp (first part before first dash)
            timestamp_match = re.match(r'^(\d+)', filename)
            if timestamp_match:
                return int(timestamp_match.group(1))
            return 0
        
        # Sort by message number
        message_files.sort(key=extract_message_number)
        
        return [str(f) for f in message_files]
    
    def consolidate_messages(self, message_files: List[str]) -> Dict[str, Any]:
        """Consolidate multiple message files into a single conversation.
        
        Args:
            message_files: List of paths to individual message JSON files
        
        Returns:
            Dictionary containing consolidated conversation data and metadata
        """
        if not message_files:
            raise ValueError("No message files provided")
        
        messages = []
        agent_name = None
        timestamps = []
        
        # Load all messages
        for file_path in message_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    message = json.load(f)
                    messages.append(message)
                
                # Extract metadata from filename
                filename = Path(file_path).name
                # Format: <timestamp>-<agent_name>-msg<number>-<role>.json
                parts = filename.replace(".json", "").split("-")
                
                # Extract timestamp (first part)
                if parts:
                    timestamp_str = parts[0]
                    timestamps.append(timestamp_str)
                
                # Extract agent name (everything between timestamp and "msg")
                # Find the index of the part that starts with "msg"
                msg_index = None
                for i, part in enumerate(parts):
                    if part.startswith("msg"):
                        msg_index = i
                        break
                
                if msg_index and msg_index > 1:
                    # Agent name is between timestamp (index 0) and msg part
                    agent_parts = parts[1:msg_index]
                    if agent_parts and not agent_name:
                        agent_name = "-".join(agent_parts)
                
            except Exception as e:
                print(f"Warning: Failed to load message file {file_path}: {e}")
                continue
        
        if not messages:
            raise ValueError("No valid messages could be loaded from files")
        
        # Use earliest timestamp as conversation timestamp
        timestamps.sort()
        conversation_timestamp = timestamps[0] if timestamps else "unknown"
        
        # Default agent name if not found
        if not agent_name:
            # Try to extract from first filename
            first_filename = Path(message_files[0]).name
            parts = first_filename.replace(".json", "").split("-")
            if len(parts) > 1:
                # Find msg index
                msg_index = None
                for i, part in enumerate(parts):
                    if part.startswith("msg"):
                        msg_index = i
                        break
                if msg_index and msg_index > 1:
                    agent_parts = parts[1:msg_index]
                    agent_name = "-".join(agent_parts)
                else:
                    agent_name = "UnknownAgent"
            else:
                agent_name = "UnknownAgent"
        
        return {
            "messages": messages,
            "agent_name": agent_name,
            "timestamp": conversation_timestamp,
            "file_path": message_files[0],  # Use first file as reference
            "filename": f"{conversation_timestamp}-{agent_name}.json",  # Synthetic filename
            "message_count": len(messages),
            "source_files": message_files,
        }
    
    def visualize_from_directory(
        self,
        directory: str,
        agent_name: Optional[str] = None,
        output_filename: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> str:
        """Visualize messages from a directory containing MessageHookProvider output files.
        
        Args:
            directory: Directory containing message files
            agent_name: Optional agent name to filter by (if None, uses first agent found)
            output_filename: Output HTML filename (auto-generated if None)
            pattern: Optional glob pattern to match files
        
        Returns:
            Path to generated HTML file
        """
        # Find message files
        message_files = self.find_message_files(directory, agent_name, pattern)
        
        if not message_files:
            raise ValueError(
                f"No message files found in {directory}"
                + (f" for agent '{agent_name}'" if agent_name else "")
            )
        
        print(f"Found {len(message_files)} message file(s)")
        
        # Consolidate messages
        conversation = self.consolidate_messages(message_files)
        
        print(f"Consolidated {conversation['message_count']} messages from agent '{conversation['agent_name']}'")
        
        # Create visualization
        return self.create_visualization(
            messages=conversation["messages"],
            agent_name=conversation["agent_name"],
            timestamp=conversation["timestamp"],
            output_filename=output_filename,
        )
    
    def visualize_from_files(
        self,
        message_files: List[str],
        output_filename: Optional[str] = None,
    ) -> str:
        """Visualize messages from a list of message file paths.
        
        Args:
            message_files: List of paths to individual message JSON files
            output_filename: Output HTML filename (auto-generated if None)
        
        Returns:
            Path to generated HTML file
        """
        if not message_files:
            raise ValueError("No message files provided")
        
        # Consolidate messages
        conversation = self.consolidate_messages(message_files)
        
        print(f"Consolidated {conversation['message_count']} messages from agent '{conversation['agent_name']}'")
        
        # Create visualization
        return self.create_visualization(
            messages=conversation["messages"],
            agent_name=conversation["agent_name"],
            timestamp=conversation["timestamp"],
            output_filename=output_filename,
        )
    
    def create_consolidated_json(
        self,
        message_files: List[str],
        output_path: Optional[str] = None,
    ) -> str:
        """Create a consolidated JSON file from message files.
        
        This creates a simple JSON array containing all messages.
        
        Args:
            message_files: List of paths to individual message JSON files
            output_path: Output JSON file path (auto-generated if None)
        
        Returns:
            Path to generated JSON file
        """
        conversation = self.consolidate_messages(message_files)
        
        # Create output path if not provided
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            safe_agent_name = "".join(
                c for c in conversation["agent_name"] if c.isalnum() or c in ("-", "_")
            )
            output_path = os.path.join(
                self.output_dir,
                f"{timestamp}-{safe_agent_name}-consolidated.json",
            )
        
        # Write consolidated messages as JSON array
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(conversation["messages"], f, indent=2, ensure_ascii=False)
        
        print(f"Consolidated JSON saved to: {output_path}")
        return output_path
    
    def create_visualization(
        self,
        messages: List[Dict[str, Any]],
        agent_name: str,
        timestamp: str,
        output_filename: Optional[str] = None
    ) -> str:
        """Create HTML visualization from messages.
        
        Args:
            messages: List of conversation messages
            agent_name: Name of the agent
            timestamp: Timestamp string
            output_filename: Optional output filename
        
        Returns:
            Path to generated HTML file
        """
        # Parse messages into graph structure
        graph = self.parse_messages(messages)
        
        # Create metadata
        metadata = {
            "agent_name": agent_name,
            "timestamp": timestamp,
            "message_count": len(messages),
            "node_count": len(graph["nodes"])
        }
        
        # Complete data structure
        viz_data = {
            "metadata": metadata,
            "nodes": graph["nodes"],
            "edges": graph["edges"]
        }
        
        # Generate HTML
        if output_filename is None:
            timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
            output_filename = f"conversation_visualization_{timestamp_str}.html"
        
        output_path = os.path.join(self.output_dir, output_filename)
        html_content = self._generate_html(viz_data)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return output_path
    
    def parse_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse messages into a simple node structure.
        
        Returns a graph structure with nodes and edges:
        - Each node represents an assistant response + user response pair
        - Tool executions are included within the node
        """
        nodes = []
        edges = []
        i = 0
        node_index = 0
        
        while i < len(messages):
            msg = messages[i]
            role = msg.get("role", "unknown")
            
            if role == "user" and i == 0:
                # First user message - standalone node
                node = {
                    "id": f"node_{node_index}",
                    "type": "user_initial",
                    "content": self._extract_text(msg.get("content", [])),
                    "raw_message": msg
                }
                nodes.append(node)
                
                # Add edge to next node
                if i + 1 < len(messages):
                    edges.append({
                        "from": f"node_{node_index}",
                        "to": f"node_{node_index + 1}"
                    })
                
                node_index += 1
                i += 1
                
            elif role == "assistant":
                # Check if this has tool use
                has_tool_use = self._has_tool_use(msg)
                
                if has_tool_use and i + 1 < len(messages):
                    next_msg = messages[i + 1]
                    if next_msg.get("role") == "user":
                        # Assistant request + user response (tool execution cycle)
                        tool_executions = self._extract_tool_executions(msg, next_msg)
                        
                        node = {
                            "id": f"node_{node_index}",
                            "type": "tool_execution",
                            "assistant_content": self._extract_text(msg.get("content", [])),
                            "tool_executions": tool_executions,
                            "raw_messages": [msg, next_msg]
                        }
                        nodes.append(node)
                        
                        # Add edge to next node
                        if i + 2 < len(messages):
                            edges.append({
                                "from": f"node_{node_index}",
                                "to": f"node_{node_index + 1}"
                            })
                        
                        node_index += 1
                        i += 2
                        continue
                
                # Assistant standalone response
                node = {
                    "id": f"node_{node_index}",
                    "type": "assistant_final",
                    "content": self._extract_text(msg.get("content", [])),
                    "raw_message": msg
                }
                nodes.append(node)
                
                # Add edge to next node
                if i + 1 < len(messages):
                    edges.append({
                        "from": f"node_{node_index}",
                        "to": f"node_{node_index + 1}"
                    })
                
                node_index += 1
                i += 1
        
        return {
            "nodes": nodes,
            "edges": edges
        }
    
    def _has_tool_use(self, msg: Dict[str, Any]) -> bool:
        """Check if message has tool use."""
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and "toolUse" in block:
                    return True
        return False
    
    def _extract_tool_executions(self, assistant_msg: Dict[str, Any], user_msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tool executions from assistant and user messages."""
        tool_executions = []
        
        # Extract tool calls from assistant message
        assistant_content = assistant_msg.get("content", [])
        tool_calls = {}
        if isinstance(assistant_content, list):
            for block in assistant_content:
                if isinstance(block, dict) and "toolUse" in block:
                    tool_use = block["toolUse"]
                    tool_use_id = tool_use.get("toolUseId")
                    if tool_use_id:
                        tool_calls[tool_use_id] = {
                            "name": tool_use.get("name", "unknown_tool"),
                            "input": tool_use.get("input", {}),
                            "toolUseId": tool_use_id,
                        }
        
        # Extract tool results from user message
        user_content = user_msg.get("content", [])
        if isinstance(user_content, list):
            for block in user_content:
                if isinstance(block, dict) and "toolResult" in block:
                    tool_result = block["toolResult"]
                    tool_use_id = tool_result.get("toolUseId")
                    if tool_use_id and tool_use_id in tool_calls:
                        tool_call = tool_calls[tool_use_id]
                        result_content = tool_result.get("content", [])
                        result_text = ""
                        if isinstance(result_content, list) and len(result_content) > 0:
                            if "text" in result_content[0]:
                                result_text = result_content[0]["text"]
                                # Try to convert Python dict strings to proper JSON
                                result_text = self._normalize_json_string(result_text)
                            else:
                                result_text = json.dumps(result_content, indent=2)
                        
                        tool_executions.append({
                            "tool_name": tool_call["name"],
                            "toolUseId": tool_use_id,
                            "tool_input": tool_call["input"],
                            "tool_result": result_text,
                            "tool_status": tool_result.get("status", "unknown"),
                        })
        
        return tool_executions
    
    def _normalize_json_string(self, text: str) -> str:
        """Try to normalize Python dict strings to valid JSON.
        
        Converts single quotes to double quotes if it looks like a Python dict.
        """
        if not text:
            return text
        
        # Try to parse as Python literal (handles single quotes)
        try:
            import ast
            # Try to evaluate as Python literal
            parsed = ast.literal_eval(text)
            # Convert to proper JSON string
            return json.dumps(parsed, indent=4, ensure_ascii=False)
        except (ValueError, SyntaxError):
            # Not a Python literal, return as-is
            return text
    
    def _extract_text(self, content: Any) -> str:
        """Extract text from content blocks."""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict):
                    if "text" in block:
                        texts.append(block["text"])
                    elif "toolUse" in block:
                        tool_use = block["toolUse"]
                        tool_name = tool_use.get("name", "unknown_tool")
                        texts.append(f"[Tool: {tool_name}]")
                    elif "toolResult" in block:
                        tool_result = block["toolResult"]
                        status = tool_result.get("status", "unknown")
                        texts.append(f"[Result: {status}]")
                elif isinstance(block, str):
                    texts.append(block)
            return "\n".join(texts)
        return str(content)
    
    def _generate_html(self, viz_data: Dict[str, Any]) -> str:
        """Generate HTML with embedded visualization data."""
        # Convert data to JSON string
        data_json = json.dumps(viz_data, indent=2, ensure_ascii=False)
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Conversation Visualization - {viz_data['metadata']['agent_name']}</title>
    <!-- Marked.js for markdown rendering -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            height: 100vh;
            overflow: hidden;
        }}

        .container {{
            display: flex;
            height: 100vh;
        }}

        .graph-panel {{
            flex: 0 0 30%;
            background: white;
            padding: 20px;
            overflow: auto;
            min-width: 200px;
        }}

        .graph-panel:focus {{
            outline: none;
        }}

        .resize-handle {{
            width: 4px;
            background: #ddd;
            cursor: col-resize;
            flex-shrink: 0;
            position: relative;
            transition: background 0.2s;
        }}

        .resize-handle:hover {{
            background: #999;
        }}

        .resize-handle::before {{
            content: '';
            position: absolute;
            left: -2px;
            top: 0;
            width: 8px;
            height: 100%;
            cursor: col-resize;
        }}

        .details-panel {{
            flex: 0 0 70%;
            background: #f5f5f5;
            padding: 20px;
            overflow-y: auto;
            min-width: 200px;
        }}

        .header {{
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #333;
        }}

        .node-details {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .node-details h3 {{
            margin-bottom: 10px;
            color: #333;
        }}

        .content-block {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 4px;
            margin: 10px 0;
            word-wrap: break-word;
            font-size: 13px;
            line-height: 1.6;
        }}

        .content-block pre {{
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
            margin: 10px 0;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
            font-size: 13px;
            line-height: 1.5;
            tab-size: 2;
            -moz-tab-size: 2;
        }}

        .content-block code {{
            background: #e0e0e0;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
            font-size: 12px;
        }}

        .content-block pre code {{
            background: transparent;
            padding: 0;
            color: #f8f8f2;
            font-size: 13px;
            white-space: pre;
        }}

        .content-block h1, .content-block h2, .content-block h3 {{
            margin-top: 15px;
            margin-bottom: 10px;
        }}

        .content-block ul, .content-block ol {{
            margin-left: 20px;
            margin-top: 5px;
            margin-bottom: 5px;
        }}

        .content-block p {{
            margin: 8px 0;
        }}

        .content-block blockquote {{
            border-left: 3px solid #ccc;
            padding-left: 10px;
            margin: 10px 0;
            color: #666;
        }}

        .tool-execution {{
            background: #fff3e0;
            border-left: 3px solid #ff9800;
            padding: 10px;
            margin: 10px 0;
        }}

        .tool-name {{
            font-weight: bold;
            color: #e65100;
        }}

        .tool-input-box {{
            background: #e3f2fd;
            border-left: 3px solid #2196F3;
            padding: 5px;
            border-radius: 4px;
            margin: 10px 0;
        }}

        .tool-input-box .content-block {{
            background: #f5f5f5;
        }}

        .tool-result-box {{
            background: #f1f8e9;
            border-left: 3px solid #4CAF50;
            padding: 5px;
            border-radius: 4px;
            margin: 10px 0;
        }}

        .tool-result-box .content-block {{
            background: #fafafa;
        }}

        /* Graph visualization */
        .graph {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 30px;
            padding: 40px;
            max-width: 800px;
            margin: 0 auto;
        }}

        .graph-row {{
            display: flex;
            flex-direction: row;
            align-items: center;
            gap: 20px;
            width: 100%;
            justify-content: center;
        }}

        .graph-node {{
            min-width: 200px;
            max-width: 500px;
            padding: 15px 20px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            position: relative;
            word-wrap: break-word;
        }}

        .graph-node:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}

        .graph-node.active {{
            border: 3px solid #2196F3;
            box-shadow: 0 4px 12px rgba(33, 150, 243, 0.4);
        }}

        .node-user-initial {{
            background: #E3F2FD;
            border: 2px solid #2196F3;
        }}

        .node-tool-execution {{
            background: #FFF3E0;
            border: 2px solid #FF9800;
        }}

        .node-assistant-final {{
            background: #E8F5E9;
            border: 2px solid #4CAF50;
        }}

        .node-label {{
            font-weight: bold;
            margin-bottom: 8px;
        }}

        .tool-count {{
            font-size: 11px;
            color: #666;
            margin-top: 5px;
        }}

        /* Tool boxes within nodes */
        .tool-boxes-container {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 10px;
        }}

        .tool-box {{
            background: white;
            border: 2px solid #FF6F00;
            border-radius: 4px;
            padding: 8px 12px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 13px;
        }}

        .tool-box:hover {{
            background: #FFF8E1;
            border-color: #E65100;
            transform: translateX(3px);
        }}

        .tool-box.active {{
            background: #FFE0B2;
            border-color: #E65100;
            border-width: 3px;
            font-weight: bold;
        }}

        .node-tool-execution.has-multiple-tools {{
            min-width: 300px;
            max-width: 600px;
        }}

        .arrow-horizontal {{
            width: 40px;
            height: 2px;
            background: #999;
            position: relative;
            margin: 0 10px;
            flex-shrink: 0;
        }}

        .arrow-horizontal::after {{
            content: '';
            position: absolute;
            right: 0;
            top: -4px;
            width: 0;
            height: 0;
            border-left: 8px solid #999;
            border-top: 5px solid transparent;
            border-bottom: 5px solid transparent;
        }}

        .arrow-vertical {{
            width: 2px;
            height: 30px;
            background: #999;
            position: relative;
            margin: 0 auto;
            flex-shrink: 0;
        }}

        .arrow-vertical::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: -4px;
            width: 0;
            height: 0;
            border-top: 8px solid #999;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
        }}
    </style>
</head>
<body>
        <div class="container">
        <div class="graph-panel" id="graph-panel" tabindex="0">
            <div id="graph-container" class="graph"></div>
        </div>

        <div class="resize-handle" id="resize-handle"></div>

        <div class="details-panel" id="details-panel">
            <div class="header">
                <h1>Conversation Details</h1>
                <p><strong>Agent:</strong> <span id="agent-name"></span></p>
                <p><strong>Timestamp:</strong> <span id="timestamp"></span></p>
                <p><strong>Nodes:</strong> <span id="node-count"></span></p>
            </div>
            <div id="node-details-container">
                <p>Click a node to view details</p>
            </div>
        </div>
    </div>

    <script>
        // Embedded visualization data
        const vizData = {data_json};

        // Panel resizing functionality
        const resizeHandle = document.getElementById('resize-handle');
        const graphPanel = document.getElementById('graph-panel');
        const detailsPanel = document.getElementById('details-panel');
        const container = document.querySelector('.container');

        let isResizing = false;
        let startX = 0;
        let startGraphWidth = 0;
        let startDetailsWidth = 0;

        resizeHandle.addEventListener('mousedown', (e) => {{
            isResizing = true;
            startX = e.clientX;
            startGraphWidth = graphPanel.offsetWidth;
            startDetailsWidth = detailsPanel.offsetWidth;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        }});

        document.addEventListener('mousemove', (e) => {{
            if (!isResizing) return;

            const deltaX = e.clientX - startX;
            const containerWidth = container.offsetWidth;
            const resizeHandleWidth = resizeHandle.offsetWidth;

            // Calculate new widths
            let newGraphWidth = startGraphWidth + deltaX;
            let newDetailsWidth = startDetailsWidth - deltaX;

            // Enforce minimum widths (200px each)
            const minWidth = 200;
            if (newGraphWidth < minWidth) {{
                newGraphWidth = minWidth;
                newDetailsWidth = containerWidth - resizeHandleWidth - minWidth;
            }}
            if (newDetailsWidth < minWidth) {{
                newDetailsWidth = minWidth;
                newGraphWidth = containerWidth - resizeHandleWidth - minWidth;
            }}

            // Update panel widths
            graphPanel.style.flex = `0 0 ${{newGraphWidth}}px`;
            detailsPanel.style.flex = `0 0 ${{newDetailsWidth}}px`;

            e.preventDefault();
        }});

        document.addEventListener('mouseup', () => {{
            if (isResizing) {{
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }}
        }});

        // Track current node and tool index for keyboard navigation
        let currentNodeIndex = 0;
        let currentToolIndex = 0;

        // Initialize
        document.getElementById('agent-name').textContent = vizData.metadata.agent_name;
        document.getElementById('timestamp').textContent = vizData.metadata.timestamp;
        document.getElementById('node-count').textContent = vizData.metadata.node_count;

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowDown') {{
                e.preventDefault();
                if (currentNodeIndex < vizData.nodes.length - 1) {{
                    currentNodeIndex++;
                    currentToolIndex = 0;
                    const node = vizData.nodes[currentNodeIndex];
                    showNodeDetails(node, node.type === 'tool_execution' ? 0 : undefined);
                    scrollToNode(currentNodeIndex);
                    updateActiveToolBox();
                }}
            }} else if (e.key === 'ArrowUp') {{
                e.preventDefault();
                if (currentNodeIndex > 0) {{
                    currentNodeIndex--;
                    currentToolIndex = 0;
                    const node = vizData.nodes[currentNodeIndex];
                    showNodeDetails(node, node.type === 'tool_execution' ? 0 : undefined);
                    scrollToNode(currentNodeIndex);
                    updateActiveToolBox();
                }}
            }} else if (e.key === 'ArrowRight') {{
                e.preventDefault();
                const node = vizData.nodes[currentNodeIndex];
                if (node.type === 'tool_execution' && node.tool_executions.length > 1) {{
                    if (currentToolIndex < node.tool_executions.length - 1) {{
                        currentToolIndex++;
                        showNodeDetails(node, currentToolIndex);
                        updateActiveToolBox();
                    }}
                }}
            }} else if (e.key === 'ArrowLeft') {{
                e.preventDefault();
                const node = vizData.nodes[currentNodeIndex];
                if (node.type === 'tool_execution' && node.tool_executions.length > 1) {{
                    if (currentToolIndex > 0) {{
                        currentToolIndex--;
                        showNodeDetails(node, currentToolIndex);
                        updateActiveToolBox();
                    }}
                }}
            }}
        }});

        // Scroll node into view
        function scrollToNode(index) {{
            const node = document.querySelector(`[data-node-id="${{vizData.nodes[index].id}}"]`);
            if (node) {{
                node.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
        }}

        // Update active tool box highlighting
        function updateActiveToolBox() {{
            // Remove all active classes from tool boxes
            document.querySelectorAll('.tool-box').forEach(box => {{
                box.classList.remove('active');
            }});

            // Add active class to current tool box
            const activeBox = document.querySelector(
                `.tool-box[data-node-index="${{currentNodeIndex}}"][data-tool-index="${{currentToolIndex}}"]`
            );
            if (activeBox) {{
                activeBox.classList.add('active');
            }}
        }}

        // Render graph
        function renderGraph() {{
            const container = document.getElementById('graph-container');
            container.innerHTML = '';

            vizData.nodes.forEach((node, index) => {{
                // Create a row for each node
                const row = document.createElement('div');
                row.className = 'graph-row';

                // Create node element
                const nodeEl = document.createElement('div');
                nodeEl.className = `graph-node node-${{node.type}}`;
                nodeEl.dataset.nodeId = node.id;
                nodeEl.dataset.nodeIndex = index;

                const label = document.createElement('div');
                label.className = 'node-label';

                if (node.type === 'user_initial') {{
                    label.textContent = 'Initial Request';
                    nodeEl.appendChild(label);

                    // Add click handler
                    nodeEl.addEventListener('click', () => {{
                        currentNodeIndex = index;
                        currentToolIndex = 0;
                        showNodeDetails(node);
                    }});
                }} else if (node.type === 'tool_execution') {{
                    const toolNames = node.tool_executions.map(t => t.tool_name);

                    if (toolNames.length === 1) {{
                        label.textContent = toolNames[0];
                        nodeEl.appendChild(label);

                        // Add click handler
                        nodeEl.addEventListener('click', () => {{
                            currentNodeIndex = index;
                            currentToolIndex = 0;
                            showNodeDetails(node, 0);
                        }});
                    }} else {{
                        // Multiple tools - create tool boxes
                        label.textContent = 'Multiple Tools';
                        nodeEl.appendChild(label);
                        nodeEl.classList.add('has-multiple-tools');

                        const toolCount = document.createElement('div');
                        toolCount.className = 'tool-count';
                        toolCount.textContent = `${{toolNames.length}} tools`;
                        nodeEl.appendChild(toolCount);

                        const toolBoxesContainer = document.createElement('div');
                        toolBoxesContainer.className = 'tool-boxes-container';

                        node.tool_executions.forEach((tool, toolIdx) => {{
                            const toolBox = document.createElement('div');
                            toolBox.className = 'tool-box';
                            toolBox.textContent = tool.tool_name;
                            toolBox.dataset.nodeIndex = index;
                            toolBox.dataset.toolIndex = toolIdx;

                            // Add click handler for each tool box
                            toolBox.addEventListener('click', (e) => {{
                                e.stopPropagation();
                                currentNodeIndex = index;
                                currentToolIndex = toolIdx;
                                showNodeDetails(node, toolIdx);

                                // Update active tool box
                                toolBoxesContainer.querySelectorAll('.tool-box').forEach(box => {{
                                    box.classList.remove('active');
                                }});
                                toolBox.classList.add('active');
                            }});

                            toolBoxesContainer.appendChild(toolBox);
                        }});

                        nodeEl.appendChild(toolBoxesContainer);

                        // Add click handler for node (not tool boxes)
                        nodeEl.addEventListener('click', (e) => {{
                            // Only if clicking the node itself, not a tool box
                            if (!e.target.classList.contains('tool-box')) {{
                                currentNodeIndex = index;
                                currentToolIndex = 0;
                                showNodeDetails(node, 0);
                            }}
                        }});
                    }}
                }} else if (node.type === 'assistant_final') {{
                    label.textContent = 'Final Response';
                    nodeEl.appendChild(label);

                    // Add click handler
                    nodeEl.addEventListener('click', () => {{
                        currentNodeIndex = index;
                        currentToolIndex = 0;
                        showNodeDetails(node);
                    }});
                }}

                row.appendChild(nodeEl);
                container.appendChild(row);

                // Add vertical arrow if not last node
                if (index < vizData.nodes.length - 1) {{
                    const arrow = document.createElement('div');
                    arrow.className = 'arrow-vertical';
                    container.appendChild(arrow);
                }}
            }});

            // Show first node by default
            if (vizData.nodes.length > 0) {{
                currentNodeIndex = 0;
                currentToolIndex = 0;
                const firstNode = vizData.nodes[0];
                showNodeDetails(firstNode, firstNode.type === 'tool_execution' ? 0 : undefined);
                updateActiveToolBox();
            }}
        }}

        // Focus the graph panel when clicked so arrow keys work
        graphPanel.addEventListener('click', () => {{
            graphPanel.focus();
        }});

        function showNodeDetails(node, toolIndex) {{
            // Update active state
            document.querySelectorAll('.graph-node').forEach(el => {{
                el.classList.remove('active');
            }});
            document.querySelector(`[data-node-id="${{node.id}}"]`).classList.add('active');

            // Render details
            const container = document.getElementById('node-details-container');
            let html = '';

            if (node.type === 'user_initial') {{
                html += `
                    <div class="node-details">
                        <h3>Initial User Request</h3>
                        <div class="content-block">${{renderMarkdown(node.content)}}</div>
                    </div>
                `;
            }} else if (node.type === 'tool_execution') {{
                html += `
                    <div class="node-details">
                        <h3>Assistant Request</h3>
                        <div class="content-block">${{renderMarkdown(node.assistant_content)}}</div>
                    </div>
                `;

                // Tool executions - show only specific tool if toolIndex is provided
                const toolsToShow = toolIndex !== undefined
                    ? [{{ tool: node.tool_executions[toolIndex], idx: toolIndex }}]
                    : node.tool_executions.map((tool, idx) => ({{ tool, idx }}));

                toolsToShow.forEach(({{ tool, idx }}) => {{
                    const displayNumber = node.tool_executions.length > 1 ? `${{idx + 1}}. ` : '';
                    html += `
                        <div class="node-details tool-execution">
                            <h3>${{displayNumber}}<span class="tool-name">${{escapeHtml(tool.tool_name)}}</span></h3>
                            <p><strong>Status:</strong> ${{tool.tool_status}}</p>

                            <div class="tool-input-box">
                                <p><strong>Input:</strong></p>
                                <div class="content-block"><pre><code>${{escapeHtml(JSON.stringify(tool.tool_input, null, 4))}}</code></pre></div>
                            </div>

                            <div class="tool-result-box">
                                <p><strong>Result:</strong></p>
                                <div class="content-block">${{renderContent(tool.tool_result)}}</div>
                            </div>
                        </div>
                    `;
                }});

                // Add navigation hint if multiple tools
                if (node.tool_executions.length > 1) {{
                    html += `
                        <div class="node-details" style="background: #e3f2fd; border: 2px solid #2196F3;">
                            <p style="margin: 0; font-size: 12px; color: #1976D2;">
                                <strong>Navigation:</strong> Use ← → arrow keys to navigate between tools (${{toolIndex + 1}} of ${{node.tool_executions.length}})
                            </p>
                        </div>
                    `;
                }}
            }} else if (node.type === 'assistant_final') {{
                html += `
                    <div class="node-details">
                        <h3>Final Assistant Response</h3>
                        <div class="content-block">${{renderMarkdown(node.content)}}</div>
                    </div>
                `;
            }}

            container.innerHTML = html;
        }}

        function renderContent(text) {{
            if (!text) return '';

            // Try to parse as JSON first
            try {{
                const parsed = JSON.parse(text);
                // If successful, format as JSON with 4-space indentation
                return '<pre><code>' + escapeHtml(JSON.stringify(parsed, null, 4)) + '</code></pre>';
            }} catch (e) {{
                // Not JSON, try markdown
                return renderMarkdown(text);
            }}
        }}

        function renderMarkdown(text) {{
            if (!text) return '';
            // Use marked.js to render markdown
            if (typeof marked !== 'undefined') {{
                try {{
                    return marked.parse(text);
                }} catch (e) {{
                    console.error('Markdown parsing error:', e);
                    return escapeHtml(text);
                }}
            }}
            return escapeHtml(text);
        }}

        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        // Initial render
        renderGraph();
        
        // Focus the graph panel so arrow keys work immediately
        graphPanel.focus();
    </script>
</body>
</html>"""
        
        return html

