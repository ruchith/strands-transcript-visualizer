"""Unit tests for message_hook_provider module."""

import json
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from hooks.message_hook_provider import MessageHookProvider


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)


@pytest.fixture
def mock_event():
    """Create a mock MessageAddedEvent."""
    event = MagicMock()
    event.agent = MagicMock()
    event.agent.name = "TestAgent"
    event.agent.agent_id = "test_agent_123"
    event.message = {
        "role": "assistant",
        "content": [{"text": "Test message"}]
    }
    return event


@pytest.fixture
def mock_registry():
    """Create a mock HookRegistry."""
    return MagicMock()


class TestMessageHookProviderInit:
    """Test MessageHookProvider initialization."""

    def test_init_local_storage(self, temp_dir):
        """Test initialization with local storage."""
        storage_path = os.path.join(temp_dir, "conversations")

        provider = MessageHookProvider(
            storage_type="local",
            storage_path=storage_path
        )

        assert provider.storage_type == "local"
        assert provider.storage_path == storage_path
        assert os.path.exists(storage_path)

    def test_init_s3_storage_valid(self):
        """Test initialization with S3 storage."""
        provider = MessageHookProvider(
            storage_type="s3",
            storage_path="my-prefix",
            s3_bucket="my-bucket"
        )

        assert provider.storage_type == "s3"
        assert provider.s3_bucket == "my-bucket"
        assert provider.storage_path == "my-prefix"

    def test_init_s3_storage_no_bucket(self):
        """Test initialization with S3 but no bucket raises error."""
        with pytest.raises(ValueError, match="S3 bucket name must be provided"):
            MessageHookProvider(storage_type="s3")

    def test_init_invalid_storage_type(self):
        """Test initialization with invalid storage type."""
        with pytest.raises(ValueError, match="Invalid storage_type"):
            MessageHookProvider(storage_type="invalid")

    def test_init_with_agent_name(self, temp_dir):
        """Test initialization with agent name."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir,
            agent_name="CustomAgent"
        )

        assert provider.agent_name == "CustomAgent"

    def test_init_creates_tracking_structures(self, temp_dir):
        """Test that __init__ creates empty tracking dictionaries."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        assert provider._saved_message_signatures == {}
        assert provider._message_counters == {}


class TestRegisterHooks:
    """Test register_hooks method."""

    def test_register_hooks_calls_add_callback(self, temp_dir, mock_registry):
        """Test that register_hooks adds the MessageAddedEvent callback."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        provider.register_hooks(mock_registry)

        # Verify add_callback was called
        assert mock_registry.add_callback.called
        # Get the call arguments
        call_args = mock_registry.add_callback.call_args
        # Verify it's listening for MessageAddedEvent
        # (We can't directly check the event class without importing it)
        assert callable(call_args[0][1])  # Second arg should be the callback


class TestGetAgentKey:
    """Test _get_agent_key method."""

    def test_get_agent_key_with_agent_id(self, temp_dir):
        """Test _get_agent_key returns agent_id when available."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        agent = MagicMock()
        agent.agent_id = "test_id_123"
        agent.name = "TestAgent"

        result = provider._get_agent_key(agent)
        assert result == "test_id_123"

    def test_get_agent_key_with_name_only(self, temp_dir):
        """Test _get_agent_key returns name when agent_id not available."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        agent = MagicMock()
        agent.agent_id = None
        agent.name = "TestAgent"

        result = provider._get_agent_key(agent)
        assert result == "TestAgent"

    def test_get_agent_key_fallback_to_id(self, temp_dir):
        """Test _get_agent_key falls back to object id."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        agent = MagicMock()
        agent.agent_id = None
        agent.name = None

        result = provider._get_agent_key(agent)
        assert result.startswith("agent_")


class TestGetMessageFilename:
    """Test _get_message_filename method."""

    def test_get_message_filename_format(self, temp_dir):
        """Test filename format is correct."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        message = {"role": "assistant", "content": []}
        filename = provider._get_message_filename("TestAgent", 5, message)

        # Should match format: timestamp-agent-msg5-assistant.json
        assert "-TestAgent-" in filename
        assert "-msg5-" in filename
        assert "-assistant.json" in filename
        assert filename.endswith(".json")

    def test_get_message_filename_sanitizes_agent_name(self, temp_dir):
        """Test that agent name is sanitized."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        message = {"role": "user", "content": []}
        filename = provider._get_message_filename("Test/Agent!", 1, message)

        # Special characters should be removed
        assert "/" not in filename
        assert "!" not in filename
        assert "TestAgent" in filename

    def test_get_message_filename_different_roles(self, temp_dir):
        """Test filename with different message roles."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        user_msg = {"role": "user", "content": []}
        user_filename = provider._get_message_filename("Agent", 1, user_msg)
        assert "-user.json" in user_filename

        assistant_msg = {"role": "assistant", "content": []}
        assistant_filename = provider._get_message_filename("Agent", 2, assistant_msg)
        assert "-assistant.json" in assistant_filename


class TestGetMessageSignature:
    """Test _get_message_signature method."""

    def test_get_message_signature_identical_messages(self, temp_dir):
        """Test that identical messages produce same signature."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        msg1 = {"role": "user", "content": [{"text": "Hello"}]}
        msg2 = {"role": "user", "content": [{"text": "Hello"}]}

        sig1 = provider._get_message_signature(msg1)
        sig2 = provider._get_message_signature(msg2)

        assert sig1 == sig2

    def test_get_message_signature_different_messages(self, temp_dir):
        """Test that different messages produce different signatures."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        msg1 = {"role": "user", "content": [{"text": "Hello"}]}
        msg2 = {"role": "user", "content": [{"text": "Goodbye"}]}

        sig1 = provider._get_message_signature(msg1)
        sig2 = provider._get_message_signature(msg2)

        assert sig1 != sig2

    def test_get_message_signature_different_roles(self, temp_dir):
        """Test that different roles produce different signatures."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        msg1 = {"role": "user", "content": [{"text": "Same content"}]}
        msg2 = {"role": "assistant", "content": [{"text": "Same content"}]}

        sig1 = provider._get_message_signature(msg1)
        sig2 = provider._get_message_signature(msg2)

        assert sig1 != sig2


class TestSaveToLocal:
    """Test _save_to_local method."""

    def test_save_to_local_creates_file(self, temp_dir):
        """Test that _save_to_local creates a JSON file."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        message = {"role": "user", "content": [{"text": "Test"}]}
        filename = "test_message.json"

        file_path = provider._save_to_local(filename, [message])

        assert os.path.exists(file_path)
        assert file_path == os.path.join(temp_dir, filename)

        # Verify content
        with open(file_path, "r") as f:
            saved_data = json.load(f)

        assert saved_data == message

    def test_save_to_local_single_message_extraction(self, temp_dir):
        """Test that single message is extracted from list."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        message = {"role": "assistant", "content": []}
        file_path = provider._save_to_local("test.json", [message])

        with open(file_path, "r") as f:
            saved_data = json.load(f)

        # Should save the message directly, not as a list
        assert isinstance(saved_data, dict)
        assert saved_data == message


class TestSaveToS3:
    """Test _save_to_s3 method."""

    @patch('boto3.client')
    def test_save_to_s3_creates_object(self, mock_boto3_client):
        """Test that _save_to_s3 creates an S3 object."""
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client

        provider = MessageHookProvider(
            storage_type="s3",
            storage_path="prefix",
            s3_bucket="test-bucket"
        )

        message = {"role": "user", "content": [{"text": "Test"}]}
        s3_key = provider._save_to_s3("test.json", [message])

        # Verify S3 client was called
        mock_boto3_client.assert_called_once_with("s3")
        mock_s3_client.put_object.assert_called_once()

        # Check the call arguments
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "prefix/test.json"
        assert call_kwargs["ContentType"] == "application/json"

        # Verify returned key
        assert s3_key == "prefix/test.json"

    @patch('boto3.client')
    def test_save_to_s3_no_prefix(self, mock_boto3_client):
        """Test S3 save without storage path prefix."""
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client

        provider = MessageHookProvider(
            storage_type="s3",
            storage_path="",
            s3_bucket="test-bucket"
        )

        message = {"role": "user", "content": []}
        s3_key = provider._save_to_s3("test.json", [message])

        # Should use filename directly without prefix
        assert s3_key == "test.json"


class TestOnMessageAdded:
    """Test _on_message_added async method."""

    @pytest.mark.asyncio
    async def test_on_message_added_saves_message(self, temp_dir, mock_event):
        """Test that _on_message_added saves a message."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        await provider._on_message_added(mock_event)

        # Check that a file was created
        files = os.listdir(temp_dir)
        assert len(files) == 1
        assert files[0].endswith(".json")

    @pytest.mark.asyncio
    async def test_on_message_added_increments_counter(self, temp_dir, mock_event):
        """Test that message counter is incremented."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        # Add first message
        await provider._on_message_added(mock_event)
        agent_key = provider._get_agent_key(mock_event.agent)
        assert provider._message_counters[agent_key] == 1

        # Add second message (modify content to avoid duplicate detection)
        mock_event.message = {"role": "user", "content": [{"text": "Different"}]}
        await provider._on_message_added(mock_event)
        assert provider._message_counters[agent_key] == 2

    @pytest.mark.asyncio
    async def test_on_message_added_skips_duplicates(self, temp_dir, mock_event):
        """Test that duplicate messages are skipped."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        # Add message twice
        await provider._on_message_added(mock_event)
        await provider._on_message_added(mock_event)

        # Should only create one file
        files = os.listdir(temp_dir)
        assert len(files) == 1

        # Counter should only increment once
        agent_key = provider._get_agent_key(mock_event.agent)
        assert provider._message_counters[agent_key] == 1

    @pytest.mark.asyncio
    async def test_on_message_added_handles_errors_gracefully(self, temp_dir, mock_event):
        """Test that errors in saving don't crash the handler."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path="/invalid/path/that/does/not/exist"
        )

        # Should not raise exception
        try:
            await provider._on_message_added(mock_event)
        except Exception:
            pytest.fail("_on_message_added should handle errors gracefully")

    @pytest.mark.asyncio
    async def test_on_message_added_uses_custom_agent_name(self, temp_dir, mock_event):
        """Test that custom agent name is used in filename."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir,
            agent_name="CustomAgentName"
        )

        await provider._on_message_added(mock_event)

        files = os.listdir(temp_dir)
        assert len(files) == 1
        assert "CustomAgentName" in files[0]

    @pytest.mark.asyncio
    @patch('boto3.client')
    async def test_on_message_added_s3_storage(self, mock_boto3_client, mock_event):
        """Test saving to S3 storage."""
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client

        provider = MessageHookProvider(
            storage_type="s3",
            storage_path="conversations",
            s3_bucket="test-bucket"
        )

        await provider._on_message_added(mock_event)

        # Verify S3 put_object was called
        assert mock_s3_client.put_object.called

    @pytest.mark.asyncio
    async def test_on_message_added_initializes_tracking(self, temp_dir, mock_event):
        """Test that tracking structures are initialized for new agents."""
        provider = MessageHookProvider(
            storage_type="local",
            storage_path=temp_dir
        )

        agent_key = provider._get_agent_key(mock_event.agent)
        assert agent_key not in provider._saved_message_signatures
        assert agent_key not in provider._message_counters

        await provider._on_message_added(mock_event)

        assert agent_key in provider._saved_message_signatures
        assert agent_key in provider._message_counters
