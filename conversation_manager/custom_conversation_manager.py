"""Custom conversation manager that extends Strands' SlidingWindowConversationManager.

This manager captures and stores messages to either local filesystem or S3 bucket.
"""

import json
import os
import logging
from datetime import datetime
from typing import Optional

# Set up logger for this module
logger = logging.getLogger(__name__)

try:
    from strands.agent.conversation_manager import SlidingWindowConversationManager
except ImportError:
    # Fallback for different import paths
    try:
        from strands.conversation_manager import SlidingWindowConversationManager
    except ImportError:
        raise ImportError(
            "Could not import SlidingWindowConversationManager from strands. "
            "Please ensure strands-agents is installed."
        )


class CustomConversationManager(SlidingWindowConversationManager):
    """Custom conversation manager that stores messages to local filesystem or S3.
    
    Extends SlidingWindowConversationManager to add message persistence functionality.
    Messages are saved in the format: <timestamp>-<agent_name>.json
    
    Args:
        window_size: Maximum number of messages to keep in the sliding window
        should_truncate_results: Whether to truncate results when window is exceeded
        storage_type: Storage backend type ('local' or 's3')
        storage_path: Local directory path or S3 prefix for storing conversations
        s3_bucket: S3 bucket name (required if storage_type is 's3')
    """
    
    def __init__(
        self,
        window_size: int = 40,
        should_truncate_results: bool = True,
        storage_type: str = "local",
        storage_path: str = "conversations",
        s3_bucket: Optional[str] = None,
    ):
        """Initialize the custom conversation manager."""
        super().__init__(window_size=window_size, should_truncate_results=should_truncate_results)
        self.storage_type = storage_type
        self.storage_path = storage_path
        self.s3_bucket = s3_bucket
        
        # Validate storage configuration
        if self.storage_type == "s3" and not self.s3_bucket:
            raise ValueError("S3 bucket name must be provided when storage_type is 's3'")
        
        if self.storage_type not in ["local", "s3"]:
            raise ValueError(f"Invalid storage_type: {storage_type}. Must be 'local' or 's3'")
        
        # Create local storage directory if it doesn't exist
        if self.storage_type == "local" and not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)
        
        # Track saved messages per agent to avoid duplicates
        # Key: agent_id or agent name, Value: number of messages already saved
        self._saved_message_counts: dict = {}
        
        # Track current file per agent for appending
        # Key: agent_id or agent name, Value: filename
        self._agent_files: dict = {}
    
    def apply_management(self, agent, **kwargs):
        """Apply conversation management and save messages.
        
        Overrides parent method to add message persistence functionality.
        
        IMPORTANT NOTE ON CALLING BEHAVIOR (CONFIRMED BY SOURCE CODE ANALYSIS):
        Based on examination of the Strands SDK source code (github.com/strands-agents/sdk-python):
        
        The call chain is:
        - agent(prompt) → __call__() → invoke_async() → stream_async() → _run_loop()
        - _run_loop() calls _execute_event_loop_cycle() ONCE, which handles the ENTIRE conversation
          (all tool calls, all LLM responses) as a single event loop cycle
        - apply_management() is called ONCE in the finally block of _run_loop(), at the very end
        
        This means apply_management is called ONCE at the end of the complete agent invocation,
        NOT after each individual LLM response. The entire conversation (user prompt → assistant
        with tool call → tool result → final assistant response) is treated as a single event
        loop cycle.
        
        As a result, all messages are saved together at the end rather than incrementally.
        This is by design in Strands - a single agent(prompt) call is one event loop cycle.
        The messages are still saved correctly - just all at once rather than after each response.
        
        If you need incremental saves after each LLM response, you would need to:
        1. Use Strands' streaming APIs and manually save after each event
        2. Manually call apply_management after each agent interaction
        3. Hook into Strands internals (not recommended)
        """
        logger.info(f"apply_management called for agent '{agent.name}'")
        
        # Store message count before parent applies management
        messages_before = getattr(agent, "messages", [])
        count_before = len(messages_before)
        
        # Call parent method first to apply sliding window management
        super().apply_management(agent, **kwargs)
        
        # Get message count after management
        messages_after = getattr(agent, "messages", [])
        count_after = len(messages_after)
        
        # If messages were reduced, update our tracking
        if count_after < count_before:
            self._handle_message_reduction(agent, count_before, count_after)
        
        # Save only new messages after management is applied
        logger.info(
            f"apply_management: agent '{agent.name}', "
            f"messages before: {count_before}, after: {count_after}"
        )
        self._save_messages(agent)
    
    def reduce_context(self, agent, e=None, **kwargs):
        """Override reduce_context to track message reductions.
        
        When reduce_context is called, messages are removed from the beginning
        of the messages array. We need to update our saved message count accordingly.
        """
        # Get message count before reduction
        messages_before = getattr(agent, "messages", [])
        count_before = len(messages_before)
        
        # Call parent reduce_context
        super().reduce_context(agent, e=e, **kwargs)
        
        # Get message count after reduction
        messages_after = getattr(agent, "messages", [])
        count_after = len(messages_after)
        
        # Update our tracking
        self._handle_message_reduction(agent, count_before, count_after)
    
    def _handle_message_reduction(self, agent, count_before: int, count_after: int):
        """Handle message reduction by updating saved message counts.
        
        When messages are reduced, we need to adjust our saved message count
        to account for the removed messages. The saved_count represents how many
        messages from the current in-memory array have been saved.
        
        After reduction:
        - If we had saved_count > count_after, it means some saved messages were removed
        - We should set saved_count to count_after (all current messages are "saved")
        - This ensures we don't try to save messages that no longer exist
        """
        agent_key = self._get_agent_key(agent)
        saved_count = self._saved_message_counts.get(agent_key, 0)
        
        # After reduction, the saved_count should not exceed the current message count
        # If saved_count > count_after, it means some saved messages were removed from memory
        # In this case, we set saved_count to count_after (all current messages are considered saved)
        # This prevents trying to save messages that no longer exist in memory
        if saved_count > count_after:
            self._saved_message_counts[agent_key] = count_after
    
    def _get_agent_key(self, agent) -> str:
        """Get a unique key for the agent."""
        # Try to get agent_id first, then name, then use object id
        agent_id = getattr(agent, "agent_id", None)
        if agent_id:
            return str(agent_id)
        agent_name = getattr(agent, "name", None)
        if agent_name:
            return str(agent_name)
        return f"agent_{id(agent)}"
    
    def _save_messages(self, agent):
        """Save only new messages to the configured storage backend."""
        try:
            # Get agent key for tracking
            agent_key = self._get_agent_key(agent)
            
            # Get messages from agent
            messages = getattr(agent, "messages", [])
            
            logger.debug(
                f"_save_messages: agent '{agent_key}', "
                f"total messages: {len(messages)}, "
                f"saved_count: {self._saved_message_counts.get(agent_key, 0)}"
            )
            
            if not messages:
                logger.debug(f"_save_messages: No messages to save for agent '{agent_key}'")
                return  # No messages to save
            
            # Get or create filename for this agent
            if agent_key not in self._agent_files:
                agent_name = getattr(agent, "name", "UnknownAgent")
                self._agent_files[agent_key] = self._get_filename(agent_name)
            
            filename = self._agent_files[agent_key]
            
            # Load existing messages if file exists
            existing_messages = self._load_existing_messages(filename)
            
            # Get count of already saved messages
            saved_count = self._saved_message_counts.get(agent_key, 0)
            
            # Determine which messages to save
            # If saved_count is 0 (e.g., after reduce_context), check for duplicates
            if saved_count == 0 and existing_messages:
                # Filter out messages that already exist in the file
                new_messages = self._filter_duplicate_messages(messages, existing_messages)
            else:
                # Only save new messages (those after the saved count)
                new_messages = messages[saved_count:]
            
            if not new_messages:
                logger.debug(f"_save_messages: No new messages to save for agent '{agent_key}'")
                return  # No new messages to save
            
            # Append new messages to existing ones
            all_messages = existing_messages + new_messages
            
            # Save all messages (existing + new)
            if self.storage_type == "local":
                file_path = self._save_to_local(filename, all_messages)
                logger.info(
                    f"Saved {len(new_messages)} new message(s) to {file_path} "
                    f"(total: {len(all_messages)} messages) for agent '{agent_key}'"
                )
            elif self.storage_type == "s3":
                s3_key = self._save_to_s3(filename, all_messages)
                logger.info(
                    f"Saved {len(new_messages)} new message(s) to S3://{self.s3_bucket}/{s3_key} "
                    f"(total: {len(all_messages)} messages) for agent '{agent_key}'"
                )
            
            # Update saved message count to reflect current in-memory message count
            # This represents how many of the current messages have been saved
            self._saved_message_counts[agent_key] = len(messages)
                
        except Exception as e:
            # Log error but don't break the agent flow
            logger.warning(f"Failed to save conversation messages for agent '{agent_key}': {e}", exc_info=True)
    
    def _filter_duplicate_messages(self, messages: list, existing_messages: list) -> list:
        """Filter out messages that already exist in the saved messages.
        
        Compares messages by their content to avoid duplicates.
        """
        new_messages = []
        existing_content_set = set()
        
        # Create a set of existing message signatures for quick lookup
        for msg in existing_messages:
            signature = self._get_message_signature(msg)
            existing_content_set.add(signature)
        
        # Only add messages that don't already exist
        for msg in messages:
            signature = self._get_message_signature(msg)
            if signature not in existing_content_set:
                new_messages.append(msg)
                existing_content_set.add(signature)  # Avoid duplicates within new_messages
        
        return new_messages
    
    def _get_message_signature(self, message: dict) -> str:
        """Generate a signature for a message to detect duplicates.
        
        Uses role and content to create a unique signature.
        """
        role = message.get("role", "")
        content = message.get("content", [])
        
        # Convert content to a string representation
        if isinstance(content, list):
            content_str = json.dumps(content, sort_keys=True)
        else:
            content_str = str(content)
        
        # Create signature from role and content
        return f"{role}:{content_str}"
    
    def _load_existing_messages(self, filename: str) -> list:
        """Load existing messages from file if it exists."""
        try:
            if self.storage_type == "local":
                file_path = os.path.join(self.storage_path, filename)
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        return json.load(f)
            elif self.storage_type == "s3":
                try:
                    import boto3
                    from botocore.exceptions import ClientError
                    s3_client = boto3.client("s3")
                    s3_key = f"{self.storage_path}/{filename}" if self.storage_path else filename
                    response = s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
                    content = response["Body"].read().decode("utf-8")
                    return json.loads(content)
                except ClientError as e:
                    # File doesn't exist yet (NoSuchKey error)
                    if e.response["Error"]["Code"] == "NoSuchKey":
                        pass
                    else:
                        raise
        except Exception as e:
            # If loading fails, start fresh
            print(f"Warning: Failed to load existing messages from {filename}: {e}")
        
        return []
    
    def _get_filename(self, agent_name: str) -> str:
        """Generate filename with timestamp and agent name.
        
        Format: <timestamp>-<agent_name>.json
        Example: 20250107143022-MyAgent.json
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # Sanitize agent name for filename
        safe_agent_name = "".join(c for c in agent_name if c.isalnum() or c in ("-", "_"))
        return f"{timestamp}-{safe_agent_name}.json"
    
    def _save_to_local(self, filename: str, messages: list) -> str:
        """Save messages to local filesystem.
        
        Returns:
            Path to the saved file
        """
        file_path = os.path.join(self.storage_path, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
        return file_path
    
    def _save_to_s3(self, filename: str, messages: list) -> str:
        """Save messages to S3 bucket.
        
        Returns:
            S3 key of the saved file
        """
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 storage. Install it with: pip install boto3"
            )
        
        s3_client = boto3.client("s3")
        file_content = json.dumps(messages, indent=2, ensure_ascii=False)
        
        # Construct S3 key with storage_path as prefix
        s3_key = f"{self.storage_path}/{filename}" if self.storage_path else filename
        
        s3_client.put_object(
            Bucket=self.s3_bucket,
            Key=s3_key,
            Body=file_content.encode("utf-8"),
            ContentType="application/json",
        )
        return s3_key

