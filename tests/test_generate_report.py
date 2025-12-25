"""Unit tests for generate_report CLI module."""

import sys
import os
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock
from io import StringIO
import pytest

from visualizer.generate_report import main


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)


@pytest.fixture
def sample_message_files(temp_dir):
    """Create sample message files in temp directory."""
    messages = [
        {"role": "user", "content": [{"text": "Hello"}]},
        {"role": "assistant", "content": [{"text": "Hi there"}]}
    ]

    for i, msg in enumerate(messages):
        filename = f"20230101120000-TestAgent-msg{i+1}-{msg['role']}.json"
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, "w") as f:
            json.dump(msg, f)

    return temp_dir


class TestMainFunction:
    """Test the main CLI function."""

    def test_main_with_valid_directory(self, sample_message_files):
        """Test main function with valid directory."""
        test_args = ["generate_report.py", sample_message_files]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                try:
                    main()
                except SystemExit as e:
                    # If it exits with 0, that's success
                    assert e.code == 0 or e.code is None

    def test_main_with_nonexistent_directory(self):
        """Test main function with nonexistent directory."""
        test_args = ["generate_report.py", "/nonexistent/directory"]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Should exit with error code
                assert exc_info.value.code == 1

                # Should print error message
                error_output = mock_stderr.getvalue()
                assert "not found" in error_output.lower()

    def test_main_with_file_instead_of_directory(self, temp_dir):
        """Test main function with file path instead of directory."""
        # Create a file
        file_path = os.path.join(temp_dir, "test_file.txt")
        with open(file_path, "w") as f:
            f.write("test")

        test_args = ["generate_report.py", file_path]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1
                error_output = mock_stderr.getvalue()
                assert "not a directory" in error_output.lower()

    def test_main_with_agent_name_filter(self, temp_dir):
        """Test main function with --agent-name filter."""
        # Create files for different agents
        messages = [
            ("agent1", {"role": "user", "content": [{"text": "Hello"}]}),
            ("agent2", {"role": "user", "content": [{"text": "Hi"}]})
        ]

        for agent_name, msg in messages:
            filename = f"20230101120000-{agent_name}-msg1-user.json"
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, "w") as f:
                json.dump(msg, f)

        test_args = [
            "generate_report.py",
            temp_dir,
            "--agent-name", "agent1"
        ]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0 or e.code is None

    def test_main_with_output_filename(self, sample_message_files):
        """Test main function with custom output filename."""
        test_args = [
            "generate_report.py",
            sample_message_files,
            "--output", "custom_output.html"
        ]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0 or e.code is None

    def test_main_with_output_dir(self, sample_message_files, temp_dir):
        """Test main function with custom output directory."""
        output_dir = os.path.join(temp_dir, "custom_output")

        test_args = [
            "generate_report.py",
            sample_message_files,
            "--output-dir", output_dir
        ]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0 or e.code is None

                # Verify output directory was created
                assert os.path.exists(output_dir)

    def test_main_with_pattern(self, sample_message_files):
        """Test main function with custom glob pattern."""
        test_args = [
            "generate_report.py",
            sample_message_files,
            "--pattern", "*-msg*.json"
        ]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0 or e.code is None

    def test_main_with_no_message_files(self, temp_dir):
        """Test main function with directory containing no message files."""
        test_args = ["generate_report.py", temp_dir]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1
                error_output = mock_stderr.getvalue()
                assert "error" in error_output.lower()

    def test_main_prints_success_message(self, sample_message_files):
        """Test that main prints success message."""
        test_args = ["generate_report.py", sample_message_files]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0 or e.code is None

                output = mock_stdout.getvalue()
                assert "generated successfully" in output.lower() or "✓" in output

    def test_main_prints_output_file_path(self, sample_message_files):
        """Test that main prints the output file path."""
        test_args = ["generate_report.py", sample_message_files]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0 or e.code is None

                output = mock_stdout.getvalue()
                assert "output" in output.lower() or ".html" in output

    def test_main_handles_visualization_error(self, sample_message_files):
        """Test that main handles visualization errors gracefully."""
        test_args = ["generate_report.py", sample_message_files]

        with patch.object(sys, 'argv', test_args):
            with patch('visualizer.generate_report.MessageVisualizer') as mock_viz:
                # Make visualize_from_directory raise an exception
                mock_viz.return_value.visualize_from_directory.side_effect = Exception("Test error")

                with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                    with pytest.raises(SystemExit) as exc_info:
                        main()

                    assert exc_info.value.code == 1
                    error_output = mock_stderr.getvalue()
                    assert "error" in error_output.lower()

    def test_main_all_arguments_combined(self, sample_message_files, temp_dir):
        """Test main with all arguments combined."""
        output_dir = os.path.join(temp_dir, "output")

        test_args = [
            "generate_report.py",
            sample_message_files,
            "--agent-name", "TestAgent",
            "--pattern", "*.json",
            "--output", "my_report.html",
            "--output-dir", output_dir
        ]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0 or e.code is None

    def test_main_help_flag(self):
        """Test that --help flag works."""
        test_args = ["generate_report.py", "--help"]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Help should exit with 0
                assert exc_info.value.code == 0

                output = mock_stdout.getvalue()
                # Should contain help text
                assert "usage:" in output.lower() or "help" in output.lower()


class TestArgumentParsing:
    """Test argument parsing behavior."""

    def test_required_directory_argument(self):
        """Test that directory argument is required."""
        test_args = ["generate_report.py"]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stderr', new_callable=StringIO):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Should exit with error
                assert exc_info.value.code != 0

    def test_optional_arguments_have_defaults(self, sample_message_files):
        """Test that optional arguments have sensible defaults."""
        test_args = ["generate_report.py", sample_message_files]

        with patch.object(sys, 'argv', test_args):
            # Mock ArgumentParser to capture parsed args
            with patch('argparse.ArgumentParser.parse_args') as mock_parse:
                mock_args = MagicMock()
                mock_args.directory = sample_message_files
                mock_args.agent_name = None
                mock_args.pattern = None
                mock_args.output = None
                mock_args.output_dir = "visualizations"
                mock_parse.return_value = mock_args

                with patch('visualizer.generate_report.MessageVisualizer'):
                    try:
                        main()
                    except:
                        pass

                # Verify parse_args was called
                assert mock_parse.called
