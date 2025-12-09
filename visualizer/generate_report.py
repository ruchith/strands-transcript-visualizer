"""CLI script for generating conversation visualizations from MessageHookProvider files."""

import argparse
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from visualizer.message_visualizer import MessageVisualizer


def main():
    """Command-line interface for generating conversation visualizations."""
    parser = argparse.ArgumentParser(
        description="Generate HTML visualization from MessageHookProvider message files"
    )

    parser.add_argument(
        "directory",
        type=str,
        help="Directory containing message files (from MessageHookProvider)",
    )

    parser.add_argument(
        "--agent-name",
        type=str,
        default=None,
        help="Optional agent name to filter message files",
    )

    parser.add_argument(
        "--pattern",
        type=str,
        default=None,
        help="Optional glob pattern to match message files",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output HTML filename (default: auto-generated with timestamp)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="visualizations",
        help="Directory to save visualization files (default: visualizations)",
    )

    args = parser.parse_args()

    # Validate directory exists
    if not Path(args.directory).exists():
        print(f"Error: Directory not found: {args.directory}", file=sys.stderr)
        sys.exit(1)

    if not Path(args.directory).is_dir():
        print(f"Error: Path is not a directory: {args.directory}", file=sys.stderr)
        sys.exit(1)

    try:
        # Use MessageVisualizer to find and consolidate messages
        visualizer = MessageVisualizer(output_dir=args.output_dir)

        print(f"Searching for message files in: {args.directory}")
        if args.agent_name:
            print(f"Filtering by agent name: {args.agent_name}")

        # Find and visualize messages
        output_path = visualizer.visualize_from_directory(
            directory=args.directory,
            agent_name=args.agent_name,
            output_filename=args.output,
            pattern=args.pattern,
        )

        print(f"\n✓ Visualization generated successfully!")
        print(f"  Output file: {output_path}")
        print(f"\nOpen the HTML file in your browser to view the interactive graph.")

    except Exception as e:
        print(f"Error generating visualization: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
