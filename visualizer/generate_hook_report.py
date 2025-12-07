"""CLI script for generating conversation visualization reports from MessageHookProvider files."""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from visualizer.hook_message_visualizer import HookMessageVisualizer


def main():
    """Command-line interface for generating conversation visualizations from hook message files."""
    parser = argparse.ArgumentParser(
        description="Generate HTML visualization reports from MessageHookProvider message files"
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
        help="Optional agent name to filter message files (if not provided, uses first agent found)",
    )
    
    parser.add_argument(
        "--pattern",
        type=str,
        default=None,
        help="Optional glob pattern to match message files (default: *-msg*.json)",
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
    
    parser.add_argument(
        "--consolidate-json",
        type=str,
        default=None,
        metavar="OUTPUT_JSON",
        help="Also create a consolidated JSON file with all messages (optional output path)",
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
        # Create visualizer
        visualizer = HookMessageVisualizer(output_dir=args.output_dir)
        
        # Generate visualization
        print(f"Searching for message files in: {args.directory}")
        if args.agent_name:
            print(f"Filtering by agent name: {args.agent_name}")
        
        output_path = visualizer.visualize_from_directory(
            directory=args.directory,
            agent_name=args.agent_name,
            output_filename=args.output,
            pattern=args.pattern,
        )
        
        print(f"\n✓ Visualization generated successfully!")
        print(f"  Output file: {output_path}")
        
        # Optionally create consolidated JSON
        if args.consolidate_json:
            # Find message files again to create consolidated JSON
            message_files = visualizer.find_message_files(
                args.directory,
                args.agent_name,
                args.pattern,
            )
            json_path = visualizer.create_consolidated_json(
                message_files,
                args.consolidate_json,
            )
            print(f"  Consolidated JSON: {json_path}")
        
        print(f"\nOpen the HTML file in your browser to view the interactive graph.")
        
    except Exception as e:
        print(f"Error generating visualization: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

