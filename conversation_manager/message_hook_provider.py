"""Hook provider for capturing messages in real-time as they're added to the conversation.

This hook provider listens to MessageAddedEvent to capture each LLM response and user message
pair as it happens, rather than waiting for the end of the conversation.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from strands.hooks import HookProvider, HookRegistry, MessageAddedEvent
except ImportError:
    raise ImportError(
        "Could not import hooks from strands. Please ensure strands-agents is installed."
    )


class MessageHookProvider(HookProvider):
    """Hook provider that captures messages in real-time as they're added.
    
    This provider listens to MessageAddedEvent and saves messages immediately
    when they're added to the conversation, rather than waiting for the end.
    
    Args:
        storage_type: Storage backend type ('local' or 's3')
        storage_path: Local directory path or S3 prefix for storing conversations
        s3_bucket: S3 bucket name (required if storage_type is 's3')
        agent_name: Optional agent name for filename generation
    """
    
    def __init__(
        self,
        storage_type: str = "local",
        storage_path: str = "conversations",
        s3_bucket: Optional[str] = None,
        agent_name: Optional[str] = None,
    ):
        self.storage_type = storage_type
        self.storage_path = storage_path
        self.s3_bucket = s3_bucket
        self.agent_name = agent_name
        
        # Validate storage configuration
        if self.storage_type == "s3" and not self.s3_bucket:
            raise ValueError("S3 bucket name must be provided when storage_type is 's3'")
        
        if self.storage_type not in ["local", "s3"]:
            raise ValueError(f"Invalid storage_type: {storage_type}. Must be 'local' or 's3'")
        
        # Create local storage directory if it doesn't exist
        if self.storage_type == "local" and not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)
        
        # Track messages that have already been saved (to avoid duplicates)
        # Key: agent_id or agent name, Value: set of message signatures
        self._saved_message_signatures: dict = {}
        
        # Track message counter per agent for unique filenames
        # Key: agent_id or agent name, Value: counter
        self._message_counters: dict = {}
    
    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        """Register the MessageAddedEvent callback."""
        registry.add_callback(MessageAddedEvent, self._on_message_added)
    
    async def _on_message_added(self, event: MessageAddedEvent) -> None:
        """Handle MessageAddedEvent - save message immediately to a separate file."""
        try:
            agent = event.agent
            message = event.message
            
            # Get agent key for tracking
            agent_key = self._get_agent_key(agent)
            
            # Initialize tracking structures for this agent if needed
            if agent_key not in self._saved_message_signatures:
                self._saved_message_signatures[agent_key] = set()
                self._message_counters[agent_key] = 0
            
            # Generate message signature to check for duplicates
            message_signature = self._get_message_signature(message)
            
            # Skip if message has already been saved
            if message_signature in self._saved_message_signatures[agent_key]:
                logger.debug(
                    f"Skipping duplicate message (role={message.get('role')}) for agent '{agent_key}'"
                )
                return
            
            # Mark message as saved
            self._saved_message_signatures[agent_key].add(message_signature)
            
            # Increment message counter for unique filename
            self._message_counters[agent_key] += 1
            message_number = self._message_counters[agent_key]
            
            # Generate unique filename for this message
            agent_name = self.agent_name or getattr(agent, "name", "UnknownAgent")
            filename = self._get_message_filename(agent_name, message_number, message)
            
            # Save message to its own separate file
            if self.storage_type == "local":
                file_path = self._save_to_local(filename, [message])
                logger.info(
                    f"Real-time save: Saved message #{message_number} (role={message.get('role')}) "
                    f"to separate file {file_path} for agent '{agent_key}'"
                )
            elif self.storage_type == "s3":
                s3_key = self._save_to_s3(filename, [message])
                logger.info(
                    f"Real-time save: Saved message #{message_number} (role={message.get('role')}) "
                    f"to separate file S3://{self.s3_bucket}/{s3_key} for agent '{agent_key}'"
                )
                
        except Exception as e:
            # Log error but don't break the agent flow
            logger.warning(f"Failed to save message in real-time: {e}", exc_info=True)
    
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
    
    def _get_message_filename(self, agent_name: str, message_number: int, message: dict) -> str:
        """Generate unique filename for a single message.
        
        Format: <timestamp>-<agent_name>-msg<number>-<role>.json
        Example: 20250107143022123456-MyAgent-msg1-assistant.json
        
        Args:
            agent_name: Name of the agent
            message_number: Sequential message number for this agent
            message: The message dictionary to extract role from
        
        Returns:
            Unique filename for this message
        """
        # Use microseconds for better uniqueness
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        # Sanitize agent name for filename
        safe_agent_name = "".join(c for c in agent_name if c.isalnum() or c in ("-", "_"))
        # Get message role
        role = message.get("role", "unknown")
        # Sanitize role
        safe_role = "".join(c for c in role if c.isalnum() or c in ("-", "_"))
        return f"{timestamp}-{safe_agent_name}-msg{message_number}-{safe_role}.json"
    
    def _get_message_signature(self, message: dict) -> str:
        """Generate a unique signature for a message to detect duplicates.
        
        Uses role and content to create a unique signature.
        
        Args:
            message: The message dictionary
        
        Returns:
            String signature for the message
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
    
    def _save_to_local(self, filename: str, messages: list) -> str:
        """Save messages to local filesystem.
        
        Note: This saves a single message to its own file.
        
        Args:
            filename: Filename for the message file
            messages: List containing a single message (for consistency with API)
        
        Returns:
            Path to the saved file
        """
        file_path = os.path.join(self.storage_path, filename)
        # Save the message (should be a single message in the list)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(messages[0] if len(messages) == 1 else messages, f, indent=2, ensure_ascii=False)
        return file_path
    
    def _save_to_s3(self, filename: str, messages: list) -> str:
        """Save messages to S3 bucket.
        
        Note: This saves a single message to its own file.
        
        Args:
            filename: Filename for the message file
            messages: List containing a single message (for consistency with API)
        
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
        # Save the message (should be a single message in the list)
        message_to_save = messages[0] if len(messages) == 1 else messages
        file_content = json.dumps(message_to_save, indent=2, ensure_ascii=False)
        
        # Construct S3 key with storage_path as prefix
        s3_key = f"{self.storage_path}/{filename}" if self.storage_path else filename
        
        s3_client.put_object(
            Bucket=self.s3_bucket,
            Key=s3_key,
            Body=file_content.encode("utf-8"),
            ContentType="application/json",
        )
        return s3_key

