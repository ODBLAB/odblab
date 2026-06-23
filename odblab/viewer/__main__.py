import sys
from pathlib import Path
from argparse import ArgumentParser, Namespace
from odblab.viewer import view
from odblab.core import load

def main() -> None:
    """CLI entry point executed via `python -m odblab.viewer`."""
    parser: ArgumentParser = ArgumentParser(description="ODBLAB Viewer")
    parser.add_argument("-f", "--file", required=True, type=Path, help="database file path")
    parser.add_argument("-t", "--theme", required=False, type=str, default=None, help="app theme (light or dark)")
    args: Namespace = parser.parse_args()
    sys.exit(view(load(args.file), args.theme))

if __name__ == "__main__":
    main()
