import os
import subprocess
import shutil
import stat
from pathlib import Path
from firecrawl import FirecrawlApp

TEMP_DIR = Path("temp_repos")

def build_repo_index(repo_path: str, max_files: int = 500) -> str:
    """Builds a lightweight file index for the repo for prompt grounding."""
    repo_root = Path(repo_path)
    entries: list[str] = []
    for root, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [
            d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}
        ]
        for filename in filenames:
            if filename in {"repomix-output.txt", "repomix-output.xml"}:
                continue
            full_path = Path(root) / filename
            entries.append(str(full_path.relative_to(repo_root)))
            if len(entries) >= max_files:
                return "\n".join(entries)
    return "\n".join(entries)

def clone_repo(repo_url: str) -> str:
    """Clones a GitHub repository to a temporary directory."""
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    target_dir = TEMP_DIR / repo_name
    def on_rm_error(func, path, exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    import uuid
    
    # Use a unique path for every clone to avoid Windows file locking issues completely
    # We never reuse directories.
    repo_name = f"{repo_name}_{uuid.uuid4().hex[:8]}"
    target_dir = TEMP_DIR / repo_name
        
    os.makedirs(target_dir, exist_ok=True)
    # Use --depth 1 for faster clones
    try:
        # Enable longpaths support for Windows to avoid checkout errors
        subprocess.run(
            ["git", "clone", "-c", "core.longpaths=true", "--depth", "1", repo_url, "."], 
            cwd=str(target_dir), 
            check=True, 
            timeout=120, # 2 minutes max for clone
            stdin=subprocess.DEVNULL,
            capture_output=True 
        )
    except subprocess.TimeoutExpired:
        raise Exception("Git clone timed out after 120 seconds.")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Git clone failed: {e.stderr.decode('utf-8', errors='ignore')}")

    return str(target_dir)

def run_repomix(repo_path: str) -> str:
    """Runs Repomix on the cloned repository."""
    # Assuming repomix is installed globally or accessible via npx
    # We will use npx to run it to ensure we don't need a local install
    # Output file will be in the repo path
    try:
        subprocess.run(
            ["npx", "-y", "repomix"], 
            cwd=repo_path, 
            shell=True, 
            check=True,
            timeout=180, # 3 minutes max for packing
            stdin=subprocess.DEVNULL
        )
    except subprocess.TimeoutExpired:
        raise Exception("Repomix timed out after 180 seconds.")
    except subprocess.CalledProcessError as e:
        # Check if it failed, but sometimes repomix uses exit codes differently.
        # We'll just log and proceed to check for output file.
        print(f"Repomix warning/error: {e}")
    
    output_file = Path(repo_path) / "repomix-output.txt"
    if output_file.exists():
        return output_file.read_text(encoding="utf-8")
    
    output_file_xml = Path(repo_path) / "repomix-output.xml" 
    if output_file_xml.exists():
        return output_file_xml.read_text(encoding="utf-8")
        
    return ""

def crawl_docs(url: str) -> str:
    """Crawls a documentation URL using Firecrawl."""
    try:
        app = FirecrawlApp() 
        # Scrape the single page or crawl subpages? 
        # For a "Repo Chat", we probably want to map or crawl the docs. 
        # Let's start with a scrape of the URL provided for MVP speed.
        scrape_result = app.scrape_url(url, params={'formats': ['markdown']})
        return scrape_result.get('markdown', '')
    except Exception as e:
        print(f"Firecrawl error: {e}")
        return f"Error crawling docs: {e}"
