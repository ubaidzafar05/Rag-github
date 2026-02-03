import os
import subprocess
from difflib import unified_diff
from typing import Iterable


def generate_diff(repo_path: str, file_rel_path: str, content: str) -> str:
    repo_abs = os.path.abspath(repo_path)
    full_path = os.path.abspath(os.path.join(repo_abs, file_rel_path))
    original = ""
    if os.path.exists(full_path):
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            original = f.read()
    diff = unified_diff(
        original.splitlines(),
        content.splitlines(),
        fromfile=f"a/{file_rel_path}",
        tofile=f"b/{file_rel_path}",
        lineterm="",
    )
    return "\n".join(diff)


def run_validation(repo_path: str, commands: Iterable[str]) -> list[dict]:
    results = []
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=repo_path,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
            )
            results.append(
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "command": command,
                    "returncode": 1,
                    "stdout": "",
                    "stderr": str(exc),
                }
            )
    return results

def apply_code_patch(repo_path: str, file_rel_path: str, content: str):
    """
    Safely overwrite the file at repo_path/file_rel_path with content.

    - Resolves real paths (symlinks) and uses os.path.commonpath to ensure containment.
    - Handles different drives on Windows as a security violation.
    - Creates parent directory only when needed.
    - Returns True on success, raises ValueError on security violation.
    """
    # Absolute repository path (base)
    repo_abs = os.path.abspath(repo_path)

    # Always join against repo_abs to avoid honoring an absolute path supplied in file_rel_path
    full_path = os.path.abspath(os.path.join(repo_abs, file_rel_path))

    # Resolve symlinks / normalize paths
    repo_real = os.path.realpath(repo_abs)
    full_real = os.path.realpath(full_path)

    # Ensure full_real is inside repo_real using commonpath (robust vs prefix attacks)
    try:
        common = os.path.commonpath([repo_real, full_real])
    except ValueError:
        # Different drives on Windows -> treat as violation
        raise ValueError("Security violation: Cannot write outside repository (different filesystem).")

    if common != repo_real:
        raise ValueError("Security violation: Cannot write outside repository.")

    # Make sure parent directory exists (skip if file is at repo root)
    parent_dir = os.path.dirname(full_real)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    # Write file (optionally atomic writes can be used)
    with open(full_real, "w", encoding="utf-8") as f:
        f.write(content)

    return True
