import difflib
import sys
import argparse
from pathlib import Path

def generate_diff(file1_path: str, file2_path: str) -> str:
    """
    Generate a unified diff between two text files (e.g. netlists).
    """
    p1 = Path(file1_path)
    p2 = Path(file2_path)

    if not p1.exists():
        return f"Error: {file1_path} not found."
    if not p2.exists():
        return f"Error: {file2_path} not found."

    with open(p1, 'r') as f1, open(p2, 'r') as f2:
        lines1 = f1.readlines()
        lines2 = f2.readlines()

    diff = difflib.unified_diff(
        lines1, lines2,
        fromfile=str(p1),
        tofile=str(p2),
        lineterm=''
    )
    
    return '\n'.join(diff)

def main():
    parser = argparse.ArgumentParser(description="Circuit-AI Visual Diff Tool")
    parser.add_argument("file1", help="First file (original)")
    parser.add_argument("file2", help="Second file (modified)")
    args = parser.parse_args()

    print(generate_diff(args.file1, args.file2))

if __name__ == "__main__":
    main()

