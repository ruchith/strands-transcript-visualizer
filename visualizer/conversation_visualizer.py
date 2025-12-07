"""HTML visualizer for agent conversations with interactive directed graphs."""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

try:
    import networkx as nx
    from pyvis.network import Network
except ImportError:
    raise ImportError(
        "networkx and pyvis are required for visualization. "
        "Install them with: pip install networkx pyvis"
    )


class ConversationVisualizer:
    """Creates interactive HTML visualizations of agent conversations."""
    
    # Color mapping for different message roles
    ROLE_COLORS = {
        "user": "#4A90E2",  # Blue
        "assistant": "#50C878",  # Green
        "system": "#FF6B6B",  # Red
        "tool": "#FFA500",  # Orange
    }
    
    DEFAULT_COLOR = "#CCCCCC"  # Gray for unknown roles
    
    def __init__(self, output_dir: str = "visualizations"):
        """Initialize the visualizer.
        
        Args:
            output_dir: Directory to save generated HTML files
        """
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
    
    def load_conversation(self, file_path: str) -> Dict[str, Any]:
        """Load a conversation from a JSON file.
        
        Args:
            file_path: Path to the conversation JSON file
        
        Returns:
            Dictionary containing conversation data and metadata
        """
        with open(file_path, "r", encoding="utf-8") as f:
            messages = json.load(f)
        
        # Extract metadata from filename
        filename = os.path.basename(file_path)
        parts = filename.replace(".json", "").split("-", 1)
        timestamp = parts[0] if len(parts) > 0 else "unknown"
        agent_name = parts[1] if len(parts) > 1 else "UnknownAgent"
        
        return {
            "messages": messages,
            "agent_name": agent_name,
            "timestamp": timestamp,
            "file_path": file_path,
            "filename": filename,
        }
    
    def load_multiple_conversations(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Load multiple conversation files.
        
        Args:
            file_paths: List of paths to conversation JSON files
        
        Returns:
            List of conversation dictionaries
        """
        conversations = []
        for file_path in file_paths:
            try:
                conv = self.load_conversation(file_path)
                conversations.append(conv)
            except Exception as e:
                print(f"Warning: Failed to load {file_path}: {e}")
        return conversations
    
    def extract_text_from_content(self, content: Any) -> str:
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
                        tool_input = tool_use.get("input", {})
                        texts.append(f"[Tool Call: {tool_name}]\nInput: {json.dumps(tool_input, indent=2)}")
                    elif "toolResult" in block:
                        tool_result = block["toolResult"]
                        status = tool_result.get("status", "unknown")
                        result_content = tool_result.get("content", [])
                        if isinstance(result_content, list) and len(result_content) > 0:
                            if "text" in result_content[0]:
                                result_text = result_content[0]["text"]
                                # Do not truncate - show full content
                                texts.append(f"[Tool Result: {status}]\n{result_text}")
                            else:
                                texts.append(f"[Tool Result: {status}]\n{json.dumps(result_content, indent=2)}")
                        else:
                            texts.append(f"[Tool Result: {status}]")
                elif isinstance(block, str):
                    texts.append(block)
            return "\n\n".join(texts)
        return str(content)
    
    def parse_messages_into_pairs(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse messages into assistant request/user response pairs.
        
        Returns a list of nodes where each node represents:
        - A standalone user message (first message)
        - An assistant request + user response pair (tool invocation cycle)
        - A final assistant response
        """
        nodes = []
        i = 0
        
        while i < len(messages):
            msg = messages[i]
            role = msg.get("role", "unknown")
            content = msg.get("content", [])
            
            if role == "user" and i == 0:
                # First user message - standalone node
                node_content = self.extract_text_from_content(content)
                nodes.append({
                    "type": "user_initial",
                    "role": "user",
                    "content": node_content,
                    "message_index": i,
                    "messages": [msg],
                })
                i += 1
            
            elif role == "assistant":
                # Check if this assistant message has toolUse
                has_tool_use = False
                for block in content:
                    if isinstance(block, dict) and "toolUse" in block:
                        has_tool_use = True
                        break
                
                if has_tool_use and i + 1 < len(messages):
                    # Assistant request with tool - expect user response with toolResult
                    next_msg = messages[i + 1]
                    if next_msg.get("role") == "user":
                        # Extract assistant request (with toolUse)
                        assistant_content = self.extract_text_from_content(content)
                        # Extract user response (with toolResult)
                        user_content = self.extract_text_from_content(next_msg.get("content", []))
                        
                        nodes.append({
                            "type": "assistant_request_user_response",
                            "assistant_content": assistant_content,
                            "user_content": user_content,
                            "assistant_message": msg,
                            "user_message": next_msg,
                            "message_index": i,
                            "messages": [msg, next_msg],
                        })
                        i += 2
                    else:
                        # No matching user response, treat as standalone
                        node_content = self.extract_text_from_content(content)
                        nodes.append({
                            "type": "assistant_standalone",
                            "role": "assistant",
                            "content": node_content,
                            "message_index": i,
                            "messages": [msg],
                        })
                        i += 1
                else:
                    # Assistant response without tool - standalone
                    node_content = self.extract_text_from_content(content)
                    nodes.append({
                        "type": "assistant_standalone",
                        "role": "assistant",
                        "content": node_content,
                        "message_index": i,
                        "messages": [msg],
                    })
                    i += 1
            
            elif role == "user" and i > 0:
                # User message that's not the first - should have been handled above
                # This is a fallback
                node_content = self.extract_text_from_content(content)
                nodes.append({
                    "type": "user_standalone",
                    "role": "user",
                    "content": node_content,
                    "message_index": i,
                    "messages": [msg],
                })
                i += 1
            
            else:
                # Unknown/other role
                node_content = self.extract_text_from_content(content)
                nodes.append({
                    "type": "other",
                    "role": role,
                    "content": node_content,
                    "message_index": i,
                    "messages": [msg],
                })
                i += 1
        
        return nodes
    
    def create_graph(self, conversation: Dict[str, Any]) -> Tuple[nx.DiGraph, List[Dict[str, Any]]]:
        """Create a directed graph from conversation messages.
        
        Returns:
            Tuple of (graph, nodes_data) where nodes_data contains the parsed node information
        """
        G = nx.DiGraph()
        messages = conversation["messages"]
        
        # Parse messages into pairs
        nodes_data = self.parse_messages_into_pairs(messages)
        
        for idx, node_data in enumerate(nodes_data):
            node_id = f"node_{idx}"
            
            # Create label based on node type
            if node_data["type"] == "user_initial":
                label = "User: Initial Request"
            elif node_data["type"] == "assistant_request_user_response":
                label = "Assistant Request → User Response"
            elif node_data["type"] == "assistant_standalone":
                label = "Assistant Response"
            else:
                label = f"{node_data.get('role', 'unknown').title()}: {node_data['type']}"
            
            # Store all node data
            G.add_node(
                node_id,
                label=label,
                **node_data,  # Store all node data as node attributes
            )
            
            # Add edge from previous node
            if idx > 0:
                prev_node_id = f"node_{idx - 1}"
                G.add_edge(prev_node_id, node_id)
        
        return G, nodes_data
    
    def generate_html(
        self,
        conversations: List[Dict[str, Any]],
        output_filename: Optional[str] = None,
        height: str = "100vh",
        width: str = "100%",
    ) -> str:
        """Generate interactive HTML visualization with two-column layout.
        
        Args:
            conversations: List of conversation dictionaries
            output_filename: Output HTML filename (auto-generated if None)
            height: Height of the visualization
            width: Width of the visualization
        
        Returns:
            Path to generated HTML file
        """
        if not conversations:
            raise ValueError("No conversations provided")
        
        # Generate output filename if not provided
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            output_filename = f"conversation_visualization_{timestamp}.html"
        
        output_path = os.path.join(self.output_dir, output_filename)
        
        # For now, handle single conversation
        if len(conversations) > 1:
            print("Warning: Multiple conversations not fully supported yet. Using first conversation.")
        
        conversation = conversations[0]
        
        # Create graph and get nodes data
        G, nodes_data = self.create_graph(conversation)
        
        # Create pyvis network - use viewport height for full screen
        # Use CDN resources to avoid local file loading issues
        net = Network(
            height="100vh",  # Full viewport height
            width="100%",
            directed=True,
            notebook=False,
            cdn_resources="remote",  # Use CDN instead of local files
        )
        
        # Add nodes with styling and simplified labels
        for node_id, node_data in G.nodes(data=True):
            node_type = node_data.get("type", "unknown")
            
            # Determine color and label based on type
            if node_type == "user_initial" or node_type == "user_standalone":
                color = self.ROLE_COLORS.get("user", self.DEFAULT_COLOR)
                label = "initial"
            elif node_type == "assistant_request_user_response":
                color = self.ROLE_COLORS.get("tool", self.DEFAULT_COLOR)  # Orange for tool interactions
                label = "tool_request"
            elif node_type == "assistant_standalone":
                color = self.ROLE_COLORS.get("assistant", self.DEFAULT_COLOR)
                label = "final"
            else:
                color = self.DEFAULT_COLOR
                label = node_data.get("label", "unknown")
            
            net.add_node(
                node_id,
                label=label,
                title=node_data.get("label", label),  # Keep full description in tooltip
                color=color,
                shape="box",
            )
        
        # Add edges
        for u, v in G.edges():
            net.add_edge(u, v)
        
        # Configure hierarchical layout: left to right with wrapping
        # This will order nodes from left to right and wrap to new lines
        # Increased spacing to ensure nodes are well separated
        net.set_options("""
        {
          "layout": {
            "hierarchical": {
              "enabled": true,
              "direction": "LR",
              "sortMethod": "directed",
              "levelSeparation": 200,
              "nodeSpacing": 300,
              "treeSpacing": 300,
              "blockShifting": true,
              "edgeMinimization": true,
              "parentCentralization": true
            }
          },
          "physics": {
            "enabled": false
          }
        }
        """)
        
        # Generate HTML using pyvis
        # We'll generate the full HTML and then extract what we need
        html_content = net.generate_html()
        
        # Enhance HTML with two-column layout and message viewer
        enhanced_html = self._enhance_html(html_content, conversation, nodes_data)
        
        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(enhanced_html)
        
        return output_path
    
    def _enhance_html(self, html_content: str, conversation: Dict[str, Any], nodes_data: List[Dict[str, Any]]) -> str:
        """Enhance HTML with two-column layout and message viewer."""
        
        # Store message data as JSON - will be rendered on demand by JavaScript
        # No need to pre-render HTML
        
        # Use .format() instead of f-string to avoid brace escaping issues
        custom_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Conversation Visualization - {agent_name}</title>
            <meta charset="utf-8">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: Arial, sans-serif;
                    height: 100vh;
                    overflow: hidden;
                }}
                
                .container {{
                    display: flex;
                    height: 100vh;
                }}
                
                .messages-panel {{
                    width: 40%;
                    overflow-y: auto;
                    border-right: 2px solid #ddd;
                    padding: 20px;
                    background: #f9f9f9;
                }}
                
                .graph-panel {{
                    width: 60%;
                    height: 100vh;
                    position: relative;
                    background: white;
                    overflow: hidden;
                }}
                
                .message-item {{
                    margin-bottom: 20px;
                    padding: 15px;
                    background: white;
                    border-radius: 8px;
                    border: 1px solid #ddd;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    /* Messages are rendered on demand, so always visible when present */
                }}
                
                .message-item:hover {{
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    transform: translateY(-2px);
                }}
                
                .message-item.active {{
                    border: 2px solid #4A90E2;
                    box-shadow: 0 4px 12px rgba(74, 144, 226, 0.3);
                }}
                
                .message-header {{
                    padding: 10px;
                    border-radius: 4px;
                    margin-bottom: 10px;
                }}
                
                .user-header {{
                    background: #E3F2FD;
                    color: #1976D2;
                }}
                
                .assistant-header {{
                    background: #E8F5E9;
                    color: #388E3C;
                }}
                
                .message-content {{
                    padding: 10px;
                    /* No max-height - allow full content to be displayed */
                    overflow-y: auto;
                }}
                
                .message-content pre {{
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    font-size: 12px;
                    line-height: 1.5;
                }}
                
                .user-content {{
                    background: #F5F5F5;
                }}
                
                .assistant-content {{
                    background: #FAFAFA;
                }}
                
                #mynetwork {{
                    width: 100% !important;
                    height: 100vh !important;
                    min-height: 100vh;
                }}
            </style>
            <!-- Ensure vis.js DataSet and Network are available for pyvis BEFORE network scripts run -->
            <!-- Load vis-data which provides DataSet functionality -->
            <script src="https://unpkg.com/vis-data@latest/standalone/umd/vis-data.min.js"></script>
            <!-- Load vis-network which provides Network functionality -->
            <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/vis-network.min.js" integrity="sha512-LnvoEWDFrqGHlHmDD2101OrLcbsfkrzoSpvtSQtxK3RMnRV0eOkhhBN2dXHKRrUU8p2DGRTk35n4O8nWSVe1mQ==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
            <script>
                // Setup vis.DataSet and vis.Network before pyvis scripts run
                (function() {{
                    // Create vis namespace if it doesn't exist
                    if (typeof vis === 'undefined') {{
                        window.vis = {{}};
                    }}
                    // Attach DataSet to vis namespace
                    if (typeof vis.DataSet === 'undefined') {{
                        if (typeof DataSet !== 'undefined') {{
                            vis.DataSet = DataSet;
                        }} else if (typeof window.DataSet !== 'undefined') {{
                            vis.DataSet = window.DataSet;
                        }} else if (typeof visData !== 'undefined' && visData.DataSet) {{
                            vis.DataSet = visData.DataSet;
                        }} else {{
                            // Fallback: create a simple DataSet implementation
                            console.warn('DataSet not found, creating fallback implementation');
                            vis.DataSet = function(data) {{
                                this._data = data || [];
                                this.get = function(options) {{
                                    if (options && options.returnType === 'Object') {{
                                        var obj = {{}};
                                        for (var i = 0; i < this._data.length; i++) {{
                                            obj[this._data[i].id] = this._data[i];
                                        }}
                                        return obj;
                                    }}
                                    return this._data;
                                }};
                            }};
                        }}
                    }}
                    // Attach Network to vis namespace (from vis-network library)
                    if (typeof vis.Network === 'undefined') {{
                        if (typeof Network !== 'undefined') {{
                            vis.Network = Network;
                        }} else if (typeof window.Network !== 'undefined') {{
                            vis.Network = window.Network;
                        }} else if (typeof visNetwork !== 'undefined' && visNetwork.Network) {{
                            vis.Network = visNetwork.Network;
                        }}
                    }}
                }})();
            </script>
        </head>
        <body>
            <div class="container">
                <div class="messages-panel">
                    <h2>Conversation Messages</h2>
                    <p><strong>Agent:</strong> {agent_name}</p>
                    <p><strong>Timestamp:</strong> {timestamp}</p>
                    <hr style="margin: 20px 0;">
                    <div id="messages-list">
                        <!-- Messages will be rendered on demand by JavaScript -->
                    </div>
                </div>
                <div class="graph-panel">
                    {network_html}
                </div>
            </div>
            
            <script>
                // Store conversation and nodes data as JSON
                const conversationData = {conversation_json};
                const nodesData = {nodes_data_json};
                
                // Highlight message item when node is clicked
                let selectedNode = null;
                let selectedMessageItem = null;
                
                // Function to escape HTML special characters
                function escapeHtml(text) {{
                    if (typeof text !== 'string') {{
                        text = String(text);
                    }}
                    const div = document.createElement('div');
                    div.textContent = text;
                    return div.innerHTML;
                }}
                
                // Function to render a message item from node data
                function renderMessageItem(nodeData, nodeId, index) {{
                    let html = '<div class="message-item" data-node-id="' + nodeId + '">';
                    
                    if (nodeData.type === 'user_initial') {{
                        html += '<div class="message-header user-header">';
                        html += '<strong>Node ' + (index + 1) + ': User - Initial Request</strong>';
                        html += '</div>';
                        html += '<div class="message-content user-content">';
                        html += '<pre>' + escapeHtml(nodeData.content) + '</pre>';
                        html += '</div>';
                    }} else if (nodeData.type === 'assistant_request_user_response') {{
                        html += '<div class="message-header assistant-header">';
                        html += '<strong>Node ' + (index + 1) + ': Assistant Request</strong>';
                        html += '</div>';
                        html += '<div class="message-content assistant-content">';
                        html += '<pre>' + escapeHtml(nodeData.assistant_content) + '</pre>';
                        html += '</div>';
                        html += '<div class="message-header user-header">';
                        html += '<strong>User Response (Tool Result)</strong>';
                        html += '</div>';
                        html += '<div class="message-content user-content">';
                        html += '<pre>' + escapeHtml(nodeData.user_content) + '</pre>';
                        html += '</div>';
                    }} else if (nodeData.type === 'assistant_standalone') {{
                        html += '<div class="message-header assistant-header">';
                        html += '<strong>Node ' + (index + 1) + ': Assistant Response</strong>';
                        html += '</div>';
                        html += '<div class="message-content assistant-content">';
                        html += '<pre>' + escapeHtml(nodeData.content) + '</pre>';
                        html += '</div>';
                    }}
                    
                    html += '</div>';
                    return html;
                }}
                
                // Function to show a specific message item (renders on demand)
                function showMessageItem(nodeId) {{
                    // Clear existing messages
                    const messagesList = document.getElementById('messages-list');
                    messagesList.innerHTML = '';
                    
                    // Find the node data
                    const nodeIndex = parseInt(nodeId.replace('node_', ''));
                    const nodeData = nodesData[nodeIndex];
                    
                    if (nodeData) {{
                        // Render the message item
                        const messageHtml = renderMessageItem(nodeData, nodeId, nodeIndex);
                        messagesList.innerHTML = messageHtml;
                        
                        // Get the rendered element and highlight it
                        const messageItem = document.querySelector('[data-node-id="' + nodeId + '"]');
                        if (messageItem) {{
                            messageItem.classList.add('active');
                            var scrollOptions = {{'behavior': 'smooth', 'block': 'start'}};
                            messageItem.scrollIntoView(scrollOptions);
                            selectedMessageItem = messageItem;
                        }}
                    }}
                }}
                
                window.addEventListener('load', function() {{
                    // Show first node by default
                    const firstNodeId = 'node_0';
                    showMessageItem(firstNodeId);
                    selectedNode = firstNodeId;
                    
                    setTimeout(function() {{
                        const network = window.network;
                        if (network) {{
                            // Highlight first node in graph
                            var firstSelection = {{'nodes': [firstNodeId], 'edges': []}};
                            network.setSelection(firstSelection);
                            
                            network.on('click', function(params) {{
                                if (params.nodes.length > 0) {{
                                    const nodeId = params.nodes[0];
                                    selectedNode = nodeId;
                                    showMessageItem(nodeId);
                                }}
                            }});
                            
                            // Also allow clicking message items to highlight nodes
                            // Use event delegation since messages are rendered on demand
                            document.getElementById('messages-list').addEventListener('click', function(e) {{
                                const messageItem = e.target.closest('.message-item');
                                if (messageItem) {{
                                    const nodeId = messageItem.getAttribute('data-node-id');
                                    selectedNode = nodeId;
                                    showMessageItem(nodeId);
                                    
                                    // Highlight node in graph
                                    if (network) {{
                                        var selection = {{'nodes': [nodeId], 'edges': []}};
                                        network.setSelection(selection);
                                    }}
                                }}
                            }});
                        }}
                    }}, 1500);
                }});
            </script>
        </body>
        </html>
        """.format(
            agent_name=conversation['agent_name'],
            timestamp=conversation['timestamp'],
            network_html=self._extract_network_html(html_content),
            conversation_json=json.dumps(conversation, default=str, ensure_ascii=False),
            nodes_data_json=json.dumps(nodes_data, default=str, ensure_ascii=False)
        )
        
        return custom_html
    
    def _extract_network_html(self, html_content: str) -> str:
        """Extract the network visualization HTML from pyvis output."""
        import re
        # Extract everything between <body> and </body>, plus all scripts
        result = ""
        
        # Extract body content
        if '<body>' in html_content and '</body>' in html_content:
            body_start = html_content.find('<body>')
            body_end = html_content.find('</body>')
            body_content = html_content[body_start + 6:body_end]  # +6 to skip '<body>'
            result += body_content
        
        # Extract all scripts (from head and body), but filter out local file references
        script_start = 0
        while True:
            script_start = html_content.find('<script', script_start)
            if script_start == -1:
                break
            script_end = html_content.find('</script>', script_start)
            if script_end == -1:
                break
            script_content = html_content[script_start:script_end + 9]  # +9 for '</script>'
            
            # Only include scripts that use CDN (http/https) or inline scripts
            # Filter out local file references (lib/, node_modules/, etc.)
            if 'src=' in script_content:
                # Check if it's a CDN URL or local file
                src_match = re.search(r'src=["\']([^"\']+)["\']', script_content)
                if src_match:
                    src_url = src_match.group(1)
                    # Include if it's a CDN URL (starts with http/https) or relative path to CDN
                    if src_url.startswith('http://') or src_url.startswith('https://'):
                        result += script_content
                    # Skip local file references (lib/, node_modules/, etc.)
                    elif not (src_url.startswith('lib/') or src_url.startswith('node_modules/') or 
                             src_url.startswith('../lib/') or src_url.startswith('../node_modules/')):
                        result += script_content
                else:
                    result += script_content
            else:
                # Inline script (no src attribute) - always include
                # But check if it references vis - if so, we need to ensure vis is available
                result += script_content
            
            script_start = script_end + 9
        
        return result if result else html_content
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not isinstance(text, str):
            text = str(text)
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;"))
    
    def visualize(
        self,
        conversation_files: List[str],
        output_filename: Optional[str] = None,
    ) -> str:
        """Main method to visualize conversation files.
        
        Args:
            conversation_files: List of paths to conversation JSON files
            output_filename: Output HTML filename (optional)
        
        Returns:
            Path to generated HTML file
        """
        # Load conversations
        conversations = self.load_multiple_conversations(conversation_files)
        
        if not conversations:
            raise ValueError("No valid conversations could be loaded")
        
        # Generate visualization
        return self.generate_html(conversations, output_filename)
