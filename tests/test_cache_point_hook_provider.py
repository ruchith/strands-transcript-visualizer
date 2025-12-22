"""Unit tests for cache_point_hook_provider module."""

from unittest.mock import MagicMock
import pytest

from hooks.cache_point_hook_provider import CachePointHookProvider


@pytest.fixture
def mock_registry():
    """Create a mock HookRegistry."""
    return MagicMock()


@pytest.fixture
def mock_event():
    """Create a mock MessageAddedEvent with messages."""
    event = MagicMock()
    event.agent = MagicMock()
    event.agent.messages = []
    return event


class TestCachePointHookProviderInit:
    """Test CachePointHookProvider initialization."""

    def test_init_enabled_default(self):
        """Test default initialization with enabled=True."""
        provider = CachePointHookProvider()
        assert provider.enabled is True

    def test_init_enabled_true(self):
        """Test initialization with enabled=True."""
        provider = CachePointHookProvider(enabled=True)
        assert provider.enabled is True

    def test_init_enabled_false(self):
        """Test initialization with enabled=False."""
        provider = CachePointHookProvider(enabled=False)
        assert provider.enabled is False


class TestRegisterHooks:
    """Test register_hooks method."""

    def test_register_hooks_when_enabled(self, mock_registry):
        """Test that register_hooks adds callback when enabled."""
        provider = CachePointHookProvider(enabled=True)

        provider.register_hooks(mock_registry)

        # Verify add_callback was called
        assert mock_registry.add_callback.called
        call_args = mock_registry.add_callback.call_args
        assert callable(call_args[0][1])

    def test_register_hooks_when_disabled(self, mock_registry):
        """Test that register_hooks does not add callback when disabled."""
        provider = CachePointHookProvider(enabled=False)

        provider.register_hooks(mock_registry)

        # Verify add_callback was NOT called
        assert not mock_registry.add_callback.called


class TestOnMessageAdded:
    """Test _on_message_added async method."""

    @pytest.mark.asyncio
    async def test_on_message_added_with_less_than_3_messages(self, mock_event):
        """Test that no action is taken with less than 3 messages."""
        provider = CachePointHookProvider(enabled=True)

        # Test with 0 messages
        mock_event.agent.messages = []
        await provider._on_message_added(mock_event)
        # No assertion needed, just verify no error

        # Test with 1 message
        mock_event.agent.messages = [
            {"role": "user", "content": [{"text": "Hello"}]}
        ]
        await provider._on_message_added(mock_event)

        # Test with 2 messages
        mock_event.agent.messages = [
            {"role": "user", "content": [{"text": "Hello"}]},
            {"role": "assistant", "content": [{"text": "Hi"}]}
        ]
        await provider._on_message_added(mock_event)

        # Verify no cachePoints were added
        for msg in mock_event.agent.messages:
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    assert "cachePoint" not in block

    @pytest.mark.asyncio
    async def test_on_message_added_adds_cache_point_to_n_minus_2(self, mock_event):
        """Test that cachePoint is added to (n-2)nd message."""
        provider = CachePointHookProvider(enabled=True)

        # Create 3 messages (n=3, so n-2 = index 1)
        mock_event.agent.messages = [
            {"role": "user", "content": [{"text": "First"}]},
            {"role": "assistant", "content": [{"text": "Second"}]},
            {"role": "user", "content": [{"text": "Third"}]}
        ]

        await provider._on_message_added(mock_event)

        # Verify cachePoint was added to message at index 1 (n-2 = 3-2 = 1)
        message_at_n_minus_2 = mock_event.agent.messages[1]
        content = message_at_n_minus_2["content"]

        # Find cachePoint block
        cache_point_blocks = [
            block for block in content
            if isinstance(block, dict) and "cachePoint" in block
        ]

        assert len(cache_point_blocks) == 1
        assert cache_point_blocks[0] == {"cachePoint": {"type": "default"}}

    @pytest.mark.asyncio
    async def test_on_message_added_removes_existing_cache_points(self, mock_event):
        """Test that existing cachePoints are removed before adding new one."""
        provider = CachePointHookProvider(enabled=True)

        # Create messages with existing cachePoints
        mock_event.agent.messages = [
            {
                "role": "user",
                "content": [
                    {"text": "First"},
                    {"cachePoint": {"type": "default"}}  # Existing cache point
                ]
            },
            {
                "role": "assistant",
                "content": [
                    {"text": "Second"},
                    {"cachePoint": {"type": "default"}}  # Existing cache point
                ]
            },
            {"role": "user", "content": [{"text": "Third"}]}
        ]

        await provider._on_message_added(mock_event)

        # Count total cachePoint blocks across all messages
        total_cache_points = 0
        for msg in mock_event.agent.messages:
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict) and "cachePoint" in block:
                        total_cache_points += 1

        # Should only have 1 cachePoint (at index n-2 = 1)
        assert total_cache_points == 1

        # Verify it's at the correct position
        cache_point_in_msg_1 = any(
            isinstance(block, dict) and "cachePoint" in block
            for block in mock_event.agent.messages[1]["content"]
        )
        assert cache_point_in_msg_1 is True

    @pytest.mark.asyncio
    async def test_on_message_added_with_4_messages(self, mock_event):
        """Test with 4 messages (n=4, n-2=2)."""
        provider = CachePointHookProvider(enabled=True)

        mock_event.agent.messages = [
            {"role": "user", "content": [{"text": "Msg1"}]},
            {"role": "assistant", "content": [{"text": "Msg2"}]},
            {"role": "user", "content": [{"text": "Msg3"}]},
            {"role": "assistant", "content": [{"text": "Msg4"}]}
        ]

        await provider._on_message_added(mock_event)

        # Should add cachePoint to index 2 (n-2 = 4-2 = 2)
        cache_point_in_msg_2 = any(
            isinstance(block, dict) and "cachePoint" in block
            for block in mock_event.agent.messages[2]["content"]
        )
        assert cache_point_in_msg_2 is True

        # Verify no cachePoints in other messages
        for i, msg in enumerate(mock_event.agent.messages):
            if i != 2:
                cache_points = [
                    block for block in msg["content"]
                    if isinstance(block, dict) and "cachePoint" in block
                ]
                assert len(cache_points) == 0

    @pytest.mark.asyncio
    async def test_on_message_added_when_disabled(self, mock_event):
        """Test that no action is taken when provider is disabled."""
        provider = CachePointHookProvider(enabled=False)

        mock_event.agent.messages = [
            {"role": "user", "content": [{"text": "First"}]},
            {"role": "assistant", "content": [{"text": "Second"}]},
            {"role": "user", "content": [{"text": "Third"}]}
        ]

        await provider._on_message_added(mock_event)

        # Verify no cachePoints were added
        for msg in mock_event.agent.messages:
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    assert "cachePoint" not in block

    @pytest.mark.asyncio
    async def test_on_message_added_with_non_list_content(self, mock_event):
        """Test handling of messages with non-list content."""
        provider = CachePointHookProvider(enabled=True)

        # Create messages where n-2 has string content instead of list
        mock_event.agent.messages = [
            {"role": "user", "content": [{"text": "First"}]},
            {"role": "assistant", "content": "This is a string, not a list"},
            {"role": "user", "content": [{"text": "Third"}]}
        ]

        # Should handle gracefully without crashing
        try:
            await provider._on_message_added(mock_event)
        except Exception:
            pytest.fail("Should handle non-list content gracefully")

    @pytest.mark.asyncio
    async def test_on_message_added_handles_errors_gracefully(self, mock_event):
        """Test that errors are handled gracefully."""
        provider = CachePointHookProvider(enabled=True)

        # Create an event with invalid structure
        mock_event.agent.messages = None

        # Should not raise exception
        try:
            await provider._on_message_added(mock_event)
        except Exception:
            pytest.fail("Should handle errors gracefully")

    @pytest.mark.asyncio
    async def test_on_message_added_preserves_existing_content(self, mock_event):
        """Test that existing content blocks are preserved."""
        provider = CachePointHookProvider(enabled=True)

        original_text = "Important content"
        mock_event.agent.messages = [
            {"role": "user", "content": [{"text": "First"}]},
            {"role": "assistant", "content": [{"text": original_text}]},
            {"role": "user", "content": [{"text": "Third"}]}
        ]

        await provider._on_message_added(mock_event)

        # Verify original content is still there
        msg_1_content = mock_event.agent.messages[1]["content"]
        text_blocks = [
            block for block in msg_1_content
            if isinstance(block, dict) and "text" in block
        ]

        assert len(text_blocks) == 1
        assert text_blocks[0]["text"] == original_text

    @pytest.mark.asyncio
    async def test_on_message_added_multiple_calls_moves_cache_point(self, mock_event):
        """Test that cachePoint moves as messages are added."""
        provider = CachePointHookProvider(enabled=True)

        # Start with 3 messages
        mock_event.agent.messages = [
            {"role": "user", "content": [{"text": "Msg1"}]},
            {"role": "assistant", "content": [{"text": "Msg2"}]},
            {"role": "user", "content": [{"text": "Msg3"}]}
        ]

        await provider._on_message_added(mock_event)

        # CachePoint should be at index 1
        assert any(
            isinstance(block, dict) and "cachePoint" in block
            for block in mock_event.agent.messages[1]["content"]
        )

        # Add a 4th message
        mock_event.agent.messages.append(
            {"role": "assistant", "content": [{"text": "Msg4"}]}
        )

        await provider._on_message_added(mock_event)

        # CachePoint should now be at index 2 and removed from index 1
        cache_point_at_1 = any(
            isinstance(block, dict) and "cachePoint" in block
            for block in mock_event.agent.messages[1]["content"]
        )
        cache_point_at_2 = any(
            isinstance(block, dict) and "cachePoint" in block
            for block in mock_event.agent.messages[2]["content"]
        )

        assert cache_point_at_1 is False
        assert cache_point_at_2 is True
