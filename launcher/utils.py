"""Shared helper utilities for the launcher."""

import hashlib
import os
import sys


def resource_path(filename: str) -> str:
    """Resolve a resource path from either a frozen executable or a source tree."""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, filename)


def ensure_dir(path: str) -> str:
    """Create a directory if it does not exist and return the same path."""
    os.makedirs(path, exist_ok=True)
    return path


def calculate_sha1(file_path: str) -> str | None:
    """Return the SHA1 digest of the given file."""
    try:
        digest = hashlib.sha1()
        with open(file_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(4096), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None


def java_binary_path(java_home: str) -> str:
    """Build a Java executable path from a JDK/JRE home."""
    return os.path.join(java_home, "bin", "java.exe" if os.name == "nt" else "java")
