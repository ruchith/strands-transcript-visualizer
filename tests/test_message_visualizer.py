"""Unit tests for message_visualizer module."""

import json
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from visualizer.message_visualizer import MessageVisualizer


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    return [
        {
            "role": "user",
            "content": [{"text": "Hello, how are you?"}]
        },
        {
            "role": "assistant",
            "content": [
                {"text": "I'm doing well!"},
                {
                    "toolUse": {
                        "toolUseId": "tool1",
                        "name": "read_file",
                        "input": {"file_path": "/test/file.txt"}
                    }
                }
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": "tool1",
                        "status": "success",
                        "content": [{"text": "File contents here"}]
                    }
                }
            ]
        },
        {
            "role": "assistant",
            "content": [{"text": "Here is the final response."}]
        }
    ]


@pytest.fixture
def visualizer(temp_dir):
    """Create a MessageVisualizer instance with temp output directory."""
    return MessageVisualizer(output_dir=temp_dir)


class TestMessageVisualizerInit:
    """Test MessageVisualizer initialization."""

    def test_init_creates_output_dir(self, temp_dir):
        """Test that __init__ creates the output directory."""
        output_path = os.path.join(temp_dir, "test_output")
        assert not os.path.exists(output_path)

        visualizer = MessageVisualizer(output_dir=output_path)

        assert os.path.exists(output_path)
        assert visualizer.output_dir == output_path

    def test_init_with_existing_dir(self, temp_dir):
        """Test initialization with an existing directory."""
        # Directory already exists
        visualizer = MessageVisualizer(output_dir=temp_dir)
        assert visualizer.output_dir == temp_dir


class TestFindMessageFiles:
    """Test find_message_files method."""

    def test_find_message_files_basic(self, temp_dir, visualizer):
        """Test finding message files in a directory."""
        # Create test message files
        files = [
            "20230101120000-agent1-msg1-user.json",
            "20230101120001-agent1-msg2-assistant.json",
            "20230101120002-agent1-msg3-user.json"
        ]

        for filename in files:
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, "w") as f:
                json.dump({"test": "data"}, f)

        # Find files
        found_files = visualizer.find_message_files(temp_dir)

        assert len(found_files) == 3
        # Verify they're sorted by message number
        assert "msg1" in found_files[0]
        assert "msg2" in found_files[1]
        assert "msg3" in found_files[2]

    def test_find_message_files_with_agent_name(self, temp_dir, visualizer):
        """Test finding message files filtered by agent name."""
        # Create test message files for different agents
        files = [
            "20230101120000-agent1-msg1-user.json",
            "20230101120001-agent2-msg1-user.json",
            "20230101120002-agent1-msg2-assistant.json"
        ]

        for filename in files:
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, "w") as f:
                json.dump({"test": "data"}, f)

        # Find files for agent1 only
        found_files = visualizer.find_message_files(temp_dir, agent_name="agent1")

        assert len(found_files) == 2
        assert all("agent1" in f for f in found_files)

    def test_find_message_files_nonexistent_directory(self, visualizer):
        """Test finding files in a nonexistent directory raises error."""
        with pytest.raises(ValueError, match="Directory does not exist"):
            visualizer.find_message_files("/nonexistent/directory")

    def test_find_message_files_custom_pattern(self, temp_dir, visualizer):
        """Test finding files with custom pattern."""
        # Create test files
        files = [
            "custom-file-1.json",
            "custom-file-2.json",
            "other-file.json"
        ]

        for filename in files:
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, "w") as f:
                json.dump({"test": "data"}, f)

        found_files = visualizer.find_message_files(temp_dir, pattern="custom-*.json")

        assert len(found_files) == 2
        assert all("custom" in f for f in found_files)


class TestConsolidateMessages:
    """Test consolidate_messages method."""

    def test_consolidate_messages_basic(self, temp_dir, visualizer):
        """Test basic message consolidation."""
        # Create test message files
        messages = [
            {"role": "user", "content": [{"text": "Hello"}]},
            {"role": "assistant", "content": [{"text": "Hi there"}]}
        ]

        files = []
        for i, msg in enumerate(messages):
            filename = f"20230101120000-TestAgent-msg{i+1}-{msg['role']}.json"
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, "w") as f:
                json.dump(msg, f)
            files.append(filepath)

        # Consolidate
        result = visualizer.consolidate_messages(files)

        assert result["message_count"] == 2
        assert result["agent_name"] == "TestAgent"
        assert len(result["messages"]) == 2
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][1]["role"] == "assistant"

    def test_consolidate_messages_empty_list(self, visualizer):
        """Test consolidation with empty file list raises error."""
        with pytest.raises(ValueError, match="No message files provided"):
            visualizer.consolidate_messages([])

    def test_consolidate_messages_invalid_file(self, temp_dir, visualizer):
        """Test consolidation handles invalid files gracefully."""
        # Create one valid and one invalid file
        valid_file = os.path.join(temp_dir, "20230101120000-agent1-msg1-user.json")
        invalid_file = os.path.join(temp_dir, "20230101120001-agent1-msg2-user.json")

        with open(valid_file, "w") as f:
            json.dump({"role": "user", "content": []}, f)

        with open(invalid_file, "w") as f:
            f.write("invalid json{")

        # Should still work with valid file
        result = visualizer.consolidate_messages([valid_file, invalid_file])
        assert result["message_count"] == 1


class TestParseMessages:
    """Test parse_messages method."""

    def test_parse_messages_user_initial(self, visualizer):
        """Test parsing messages starting with user."""
        messages = [
            {"role": "user", "content": [{"text": "Hello"}]},
            {"role": "assistant", "content": [{"text": "Hi"}]}
        ]

        result = visualizer.parse_messages(messages)

        assert len(result["nodes"]) == 2
        assert result["nodes"][0]["type"] == "user_initial"
        assert result["nodes"][1]["type"] == "assistant_final"
        assert len(result["edges"]) == 1

    def test_parse_messages_with_tool_use(self, visualizer):
        """Test parsing messages with tool usage."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tool1",
                            "name": "test_tool",
                            "input": {"param": "value"}
                        }
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": "tool1",
                            "status": "success",
                            "content": [{"text": "result"}]
                        }
                    }
                ]
            }
        ]

        result = visualizer.parse_messages(messages)

        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["type"] == "tool_execution"
        assert len(result["nodes"][0]["tool_executions"]) == 1
        assert result["nodes"][0]["tool_executions"][0]["tool_name"] == "test_tool"

    def test_parse_messages_assistant_final(self, visualizer):
        """Test parsing final assistant response without tools."""
        messages = [
            {"role": "assistant", "content": [{"text": "Final response"}]}
        ]

        result = visualizer.parse_messages(messages)

        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["type"] == "assistant_final"


class TestHelperMethods:
    """Test helper methods."""

    def test_has_tool_use_true(self, visualizer):
        """Test _has_tool_use returns True when tool use present."""
        msg = {
            "role": "assistant",
            "content": [
                {"text": "Some text"},
                {"toolUse": {"toolUseId": "123", "name": "tool"}}
            ]
        }

        assert visualizer._has_tool_use(msg) is True

    def test_has_tool_use_false(self, visualizer):
        """Test _has_tool_use returns False when no tool use."""
        msg = {
            "role": "assistant",
            "content": [{"text": "Just text"}]
        }

        assert visualizer._has_tool_use(msg) is False

    def test_extract_text_from_string(self, visualizer):
        """Test _extract_text with string content."""
        result = visualizer._extract_text("Hello world")
        assert result == "Hello world"

    def test_extract_text_from_list(self, visualizer):
        """Test _extract_text with list content."""
        content = [
            {"text": "First part"},
            {"text": "Second part"}
        ]

        result = visualizer._extract_text(content)
        assert "First part" in result
        assert "Second part" in result

    def test_extract_text_with_tool_use(self, visualizer):
        """Test _extract_text handles tool use blocks."""
        content = [
            {"text": "Using tool"},
            {"toolUse": {"name": "my_tool"}}
        ]

        result = visualizer._extract_text(content)
        assert "Using tool" in result
        assert "my_tool" in result

    def test_normalize_json_string_valid_python_dict(self, visualizer):
        """Test _normalize_json_string converts Python dict syntax."""
        python_dict_str = "{'key': 'value', 'number': 42}"

        result = visualizer._normalize_json_string(python_dict_str)

        # Should be valid JSON now
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["number"] == 42

    def test_normalize_json_string_invalid(self, visualizer):
        """Test _normalize_json_string returns original for invalid input."""
        invalid_str = "not a dict at all"

        result = visualizer._normalize_json_string(invalid_str)
        assert result == invalid_str

    def test_extract_tool_executions(self, visualizer):
        """Test _extract_tool_executions extracts tool calls and results."""
        assistant_msg = {
            "content": [
                {
                    "toolUse": {
                        "toolUseId": "tool1",
                        "name": "read_file",
                        "input": {"path": "/test.txt"}
                    }
                }
            ]
        }

        user_msg = {
            "content": [
                {
                    "toolResult": {
                        "toolUseId": "tool1",
                        "status": "success",
                        "content": [{"text": "file contents"}]
                    }
                }
            ]
        }

        result = visualizer._extract_tool_executions(assistant_msg, user_msg)

        assert len(result) == 1
        assert result[0]["tool_name"] == "read_file"
        assert result[0]["tool_status"] == "success"
        assert "file contents" in result[0]["tool_result"]


class TestCreateVisualization:
    """Test create_visualization method."""

    def test_create_visualization_generates_html(self, temp_dir, visualizer, sample_messages):
        """Test that create_visualization generates an HTML file."""
        output_path = visualizer.create_visualization(
            messages=sample_messages,
            agent_name="TestAgent",
            timestamp="20230101120000",
            output_filename="test_output.html"
        )

        assert os.path.exists(output_path)
        assert output_path.endswith(".html")

        # Verify HTML content
        with open(output_path, "r") as f:
            html_content = f.read()

        assert "<!DOCTYPE html>" in html_content
        assert "TestAgent" in html_content
        assert "vizData" in html_content

    def test_create_visualization_auto_filename(self, visualizer, sample_messages):
        """Test auto-generated filename."""
        with patch('visualizer.message_visualizer.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20230101120000"

            output_path = visualizer.create_visualization(
                messages=sample_messages,
                agent_name="TestAgent",
                timestamp="20230101120000"
            )

        assert "conversation_visualization_" in output_path
        assert output_path.endswith(".html")


class TestVisualizeFromDirectory:
    """Test visualize_from_directory method."""

    def test_visualize_from_directory_success(self, temp_dir, visualizer):
        """Test end-to-end visualization from directory."""
        # Create test message files
        messages = [
            {"role": "user", "content": [{"text": "Hello"}]},
            {"role": "assistant", "content": [{"text": "Hi"}]}
        ]

        for i, msg in enumerate(messages):
            filename = f"20230101120000-TestAgent-msg{i+1}-{msg['role']}.json"
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, "w") as f:
                json.dump(msg, f)

        # Visualize
        output_path = visualizer.visualize_from_directory(
            directory=temp_dir,
            output_filename="test.html"
        )

        assert os.path.exists(output_path)
        assert output_path.endswith("test.html")

    def test_visualize_from_directory_no_files(self, temp_dir, visualizer):
        """Test error when no message files found."""
        with pytest.raises(ValueError, match="No message files found"):
            visualizer.visualize_from_directory(directory=temp_dir)


class TestCreateConsolidatedJson:
    """Test create_consolidated_json method."""

    def test_create_consolidated_json(self, temp_dir, visualizer):
        """Test creating consolidated JSON file."""
        # Create test message files
        messages = [
            {"role": "user", "content": [{"text": "Hello"}]},
            {"role": "assistant", "content": [{"text": "Hi"}]}
        ]

        files = []
        for i, msg in enumerate(messages):
            filename = f"20230101120000-TestAgent-msg{i+1}-{msg['role']}.json"
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, "w") as f:
                json.dump(msg, f)
            files.append(filepath)

        # Create consolidated JSON
        output_path = visualizer.create_consolidated_json(files)

        assert os.path.exists(output_path)
        assert output_path.endswith(".json")

        # Verify content
        with open(output_path, "r") as f:
            consolidated = json.load(f)

        assert isinstance(consolidated, list)
        assert len(consolidated) == 2
        assert consolidated[0]["role"] == "user"
        assert consolidated[1]["role"] == "assistant"
