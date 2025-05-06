import os
import sys
from pathlib import Path

def find_file(filename, search_path):
    """Search for a file in the given path and all subdirectories."""
    found_files = []
    
    for root, dirs, files in os.walk(search_path):
        if filename in files:
            found_files.append(os.path.join(root, filename))
    
    return found_files

def main():
    if len(sys.argv) < 2:
        print("Usage: python find_files.py <filename>")
        return
    
    filename = sys.argv[1]
    
    # Search in common directories
    search_paths = [
        os.path.join(os.getcwd(), "inspicio", ".data"),
        os.path.join(os.getcwd(), ".data"),
        os.path.join(os.getcwd(), "inspicio", ".data", "extracted"),
        os.path.join(os.getcwd(), "inspicio", ".data", "webarena"),
    ]
    
    for path in search_paths:
        if os.path.exists(path):
            print(f"Searching in {path}...")
            found = find_file(filename, path)
            
            if found:
                print(f"Found {len(found)} matches:")
                for file_path in found:
                    print(f"  {file_path}")
            else:
                print(f"No matches found in {path}")
        else:
            print(f"Path does not exist: {path}")

if __name__ == "__main__":
    main() 