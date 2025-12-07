"""HTML visualizer for agent conversations from MessageHookProvider output files.

This visualizer works with the separate message files created by MessageHookProvider,
where each message is saved to its own file. It consolidates these files into a
conversation array and then uses the same visualization logic as ConversationVisualizer.
"""

import json
import os
import re
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

# Import the existing visualizer to reuse its logic
from .conversation_visualizer import ConversationVisualizer


class HookMessageVisualizer(ConversationVisualizer):
    """Creates interactive HTML visualizations from MessageHookProvider message files.
    
    This extends ConversationVisualizer to handle the case where messages are stored
    in separate files (one per message) rather than a single conversation file.
    """
    
    def __init__(self, output_dir: str = "visualizations"):
        """Initialize the visualizer.
        
        Args:
            output_dir: Directory to save generated HTML files
        """
        super().__init__(output_dir)
    
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
        
        # Generate visualization using parent class method
        return self.generate_html([conversation], output_filename)
    
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
        
        # Generate visualization using parent class method
        return self.generate_html([conversation], output_filename)
    
    def create_consolidated_json(
        self,
        message_files: List[str],
        output_path: Optional[str] = None,
    ) -> str:
        """Create a consolidated JSON file from message files.
        
        This creates a simple JSON array containing all messages, which can be
        used with the existing ConversationVisualizer.
        
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

