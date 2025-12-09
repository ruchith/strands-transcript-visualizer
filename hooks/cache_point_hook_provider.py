"""Hook provider for adding cache points to conversation messages.

This hook provider automatically adds cachePoint content blocks to the (n-2)nd message
in the conversation history to optimize token usage through prompt caching.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from strands.hooks import HookProvider, HookRegistry, MessageAddedEvent
except ImportError:
    raise ImportError(
        "Could not import hooks from strands. Please ensure strands-agents is installed."
    )


class CachePointHookProvider(HookProvider):
    """Hook provider that adds cachePoint to the (n-2)nd message in conversation history.
    
    When a new message is added (making it the nth message), this hook:
    1. Removes all existing cachePoints from all messages
    2. Adds a cachePoint content block to the (n-2)nd message (the second-to-last message)
    
    This ensures only the (n-2)nd message has a cachePoint, enabling prompt caching
    and reducing token usage.
    
    Args:
        enabled: Whether to enable cache point insertion (default: True)
    """
    
    def __init__(self, enabled: bool = True):
        """Initialize the cache point hook provider.
        
        Args:
            enabled: Whether to enable cache point insertion (default: True)
        """
        self.enabled = enabled
    
    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        """Register the MessageAddedEvent callback."""
        if self.enabled:
            registry.add_callback(MessageAddedEvent, self._on_message_added)
    
    async def _on_message_added(self, event: MessageAddedEvent) -> None:
        """Handle MessageAddedEvent - remove all cachePoints, then add to (n-2)nd message."""
        if not self.enabled:
            return
        
        try:
            agent = event.agent
            messages = getattr(agent, "messages", [])
            
            # Need at least 3 messages to have an (n-2)nd message
            # When a new message is added, n = len(messages)
            # We want to modify message at index (n-2) = len(messages) - 2
            if len(messages) < 3:
                return  # Not enough messages yet
            
            # Step 1: Remove all existing cachePoints from all messages
            removed_count = 0
            for msg_index, message in enumerate(messages):
                content = message.get("content", [])
                if not isinstance(content, list):
                    continue
                
                # Filter out cachePoint blocks
                original_length = len(content)
                content[:] = [
                    block for block in content
                    if not (isinstance(block, dict) and "cachePoint" in block)
                ]
                
                if len(content) < original_length:
                    removed_count += 1
                    logger.debug(
                        f"Removed cachePoint(s) from message at index {msg_index} "
                        f"(role={message.get('role')})"
                    )
            
            if removed_count > 0:
                logger.debug(f"Removed cachePoints from {removed_count} message(s)")
            
            # Step 2: Add cachePoint to the (n-2)nd message (second-to-last)
            target_index = len(messages) - 2
            target_message = messages[target_index]
            
            content = target_message.get("content", [])
            if not isinstance(content, list):
                logger.warning(
                    f"Message at index {target_index} has non-list content, "
                    "cannot add cachePoint"
                )
                return
            
            # Add cachePoint as a new content block
            cache_point_block = {"cachePoint": {"type": "default"}}
            content.append(cache_point_block)
            
            logger.debug(
                f"Added cachePoint to message at index {target_index} "
                f"(role={target_message.get('role')})"
            )
            
        except Exception as e:
            # Log error but don't break the agent flow
            logger.warning(f"Failed to manage cachePoint: {e}", exc_info=True)

