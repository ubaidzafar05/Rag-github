import os

def apply_code_patch(repo_path: str, file_rel_path: str, content: str):
    """
    Overwrites the file at repo_path/file_rel_path with content.
    """
    # Security check: ensure the target is within the repo
    full_path = os.path.abspath(os.path.join(repo_path, file_rel_path))
    repo_abs = os.path.abspath(repo_path)
    
    if not full_path.startswith(repo_abs):
        raise ValueError("Security violation: Cannot write outside repository.")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return True
