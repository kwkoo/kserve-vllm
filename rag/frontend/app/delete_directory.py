#!/usr/bin/env python3

from pathlib import Path
import os

# https://kodify.net/python/remove-folder-recursively/
def remove_directory_tree(start_directory: Path):
    for path in start_directory.iterdir():
        if path.is_file():
            path.unlink()
        else:
            remove_directory_tree(path)
            path.rmdir()

def delete_database():
    persist_directory = os.environ.get("PERSIST_DIRECTORY", "db")
    remove_directory_tree(Path(persist_directory))
