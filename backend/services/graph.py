import os
import re
from pathlib import Path

def build_knowledge_graph(repo_path: str):
    nodes = []
    links = []
    
    # helper to find node index or add
    node_map = {} # path -> index

    file_paths = []
    # 1. Walk files to create nodes
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.startswith('.') or file in ["package-lock.json", "yarn.lock"]:
                continue
                
            full_path = Path(root) / file
            rel_path = str(full_path.relative_to(repo_path)).replace("\\", "/")
            
            # Simple filtering
            if any(x in rel_path for x in ["node_modules", ".git", ".venv", "__pycache__", "dist", "build"]):
                continue

            node_data = {"id": rel_path, "group": 1, "name": file}
            
            # Assign groups based on extension
            ext = full_path.suffix
            if ext in [".py"]: node_data["group"] = 2
            elif ext in [".ts", ".tsx", ".js", ".jsx"]: node_data["group"] = 3
            elif ext in [".css", ".scss"]: node_data["group"] = 4
            elif ext in [".json", ".md"]: node_data["group"] = 5
            
            nodes.append(node_data)
            node_map[rel_path] = len(nodes) - 1
            file_paths.append(full_path)

    # 2. Parse imports to create links
    for i, fpath in enumerate(file_paths):
        source_node = nodes[i]["id"]
        
        try:
            content = fpath.read_text(errors="ignore")
        except:
            continue
            
        ext = fpath.suffix
        
        # Python Imports
        if ext == ".py":
            # from x import y -> x
            # import x -> x
            matches = re.findall(r'^(?:from|import) ([\w\.]+)', content, re.MULTILINE)
            for m in matches:
                # heuristic: look for file with this name
                target_guess = m.replace(".", "/") + ".py"
                target_guess_init = m.replace(".", "/") + "/__init__.py"
                
                # Check if we have this node?
                for n in nodes:
                    # Stricter check: match either exactly OR ensure it ends with /filename
                    # AND ensure we don't match "utils.py" to "other_utils.py"
                    if n["id"] == target_guess or n["id"].endswith("/" + target_guess) or \
                       n["id"] == target_guess_init or n["id"].endswith("/" + target_guess_init):
                        links.append({"source": source_node, "target": n["id"]})
                        break

        # JS/TS Imports
        elif ext in [".ts", ".tsx", ".js", ".jsx"]:
            # import ... from '...'
            matches = re.findall(r'from [\'"]([^\'"]+)[\'"]', content)
            for m in matches:
                if m.startswith("."):
                    # resolve relative path
                    # naive approximation: just match the filename at the end
                    target_name = m.split("/")[-1]
                    for n in nodes:
                        # Ensure we match the full filename to avoid partial matches
                        if n["id"].endswith("/" + target_name + ".ts") or \
                           n["id"].endswith("/" + target_name + ".tsx") or \
                           n["id"].endswith("/" + target_name + ".js") or \
                           n["id"] == target_name + ".ts" or \
                           n["id"] == target_name + ".tsx" or \
                           n["id"] == target_name + ".js":
                             links.append({"source": source_node, "target": n["id"]})
                             break

    return {"nodes": nodes, "links": links}


# Global Cache for Graph (Simple in-memory for now)
_GRAPH_CACHE = {}

def get_repo_graph(repo_path: str):
    if repo_path in _GRAPH_CACHE:
        return _GRAPH_CACHE[repo_path]
    
    graph_data = build_knowledge_graph(repo_path)
    
    # Convert to adjacency list for fast lookup
    adj_list = {}
    node_id_to_index = {}
    
    for i, node in enumerate(graph_data["nodes"]):
        node_id_to_index[node["id"]] = i
        adj_list[node["id"]] = []
        
    for link in graph_data["links"]:
        source = link["source"]
        target = link["target"]
        if source not in adj_list: adj_list[source] = []
        adj_list[source].append(target)
        # Undirected graph assumption for context? 
        # If A imports B, B is relevant to A.
        # But if A is main.py and imports utils.py, 
        # when looking at utils.py, main.py is also relevant context (usage examples).
        if target not in adj_list: adj_list[target] = []
        adj_list[target].append(source)
        
    _GRAPH_CACHE[repo_path] = adj_list
    return adj_list

def get_related_files(repo_path: str, file_path: str) -> list[str]:
    """Returns a list of file paths related to the given file based on imports."""
    graph = get_repo_graph(repo_path)
    
    # Normalize file_path relative to repo root if needed
    # The graph IDs are relative paths like "backend/main.py"
    # Ensure input matches that format
    rel_path = file_path.replace("\\", "/")
    if rel_path.startswith("/"): rel_path = rel_path[1:]
    
    neighbors = graph.get(rel_path, [])
    return list(set(neighbors)) # Dedupe logic

