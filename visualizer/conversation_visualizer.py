"""Conversation visualizer that creates clean JSON for HTML/JS rendering."""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class ConversationVisualizer:
    """Creates a JSON representation for conversation visualization."""

    def __init__(self, output_dir: str = "visualizations"):
        """Initialize the visualizer.

        Args:
            output_dir: Directory to save generated HTML files
        """
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

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

        .details-panel {{
            width: 40%;
            background: #f5f5f5;
            padding: 20px;
            overflow-y: auto;
            border-right: 2px solid #ddd;
        }}

        .graph-panel {{
            width: 60%;
            background: white;
            padding: 20px;
            overflow: auto;
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
        <div class="details-panel">
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

        <div class="graph-panel">
            <div id="graph-container" class="graph"></div>
        </div>
    </div>

    <script>
        // Embedded visualization data
        const vizData = {data_json};

        // Initialize
        document.getElementById('agent-name').textContent = vizData.metadata.agent_name;
        document.getElementById('timestamp').textContent = vizData.metadata.timestamp;
        document.getElementById('node-count').textContent = vizData.metadata.node_count;

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

                const label = document.createElement('div');
                label.className = 'node-label';

                if (node.type === 'user_initial') {{
                    label.textContent = 'Initial Request';
                }} else if (node.type === 'tool_execution') {{
                    const toolNames = node.tool_executions.map(t => t.tool_name);
                    label.textContent = toolNames.length === 1 ? toolNames[0] : 'Multiple Tools';

                    if (toolNames.length > 1) {{
                        const toolCount = document.createElement('div');
                        toolCount.className = 'tool-count';
                        toolCount.textContent = `${{toolNames.length}} tool${{toolNames.length > 1 ? 's' : ''}}`;
                        nodeEl.appendChild(toolCount);
                    }}
                }} else if (node.type === 'assistant_final') {{
                    label.textContent = 'Final Response';
                }}

                nodeEl.appendChild(label);

                // Add click handler
                nodeEl.addEventListener('click', () => showNodeDetails(node));

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
                showNodeDetails(vizData.nodes[0]);
            }}
        }}

        function showNodeDetails(node) {{
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

                // Tool executions
                node.tool_executions.forEach((tool, idx) => {{
                    html += `
                        <div class="node-details tool-execution">
                            <h3>${{idx + 1}}. <span class="tool-name">${{escapeHtml(tool.tool_name)}}</span></h3>
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
    </script>
</body>
</html>"""

        return html
