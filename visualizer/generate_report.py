"""CLI script for generating conversation visualization reports."""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from visualizer.conversation_visualizer import ConversationVisualizer


def main():
    """Command-line interface for generating conversation visualizations."""
    parser = argparse.ArgumentParser(
        description="Generate HTML visualization reports for Strands agent conversations"
    )
    
    parser.add_argument(
        "conversation_files",
        nargs="+",
        help="Path(s) to conversation JSON file(s) to visualize",
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
    
    # Validate input files exist
    for file_path in args.conversation_files:
        if not Path(file_path).exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
    
    try:
        # Create visualizer
        visualizer = ConversationVisualizer(output_dir=args.output_dir)
        
        # Generate visualization
        print(f"Loading {len(args.conversation_files)} conversation file(s)...")
        output_path = visualizer.visualize(
            conversation_files=args.conversation_files,
            output_filename=args.output,
        )
        
        print(f"\n✓ Visualization generated successfully!")
        print(f"  Output file: {output_path}")
        print(f"\nOpen the file in your browser to view the interactive graph.")
        
    except Exception as e:
        print(f"Error generating visualization: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

