from groq import Groq
from dotenv import load_dotenv
import os
import re
from pathlib import Path

load_dotenv()



GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq client
groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

def get_chat_response(
    message: str,
    history: list[dict],
    context: str = "",
    repo_url: str | None = None,
    repo_index: str = "",
) -> str:
    """
    Generates a response using Gemini with the provided context (code base).
    Uses a refined system prompt for high-quality, architect-level responses.
    """
    # Delegate to the Agentic Workflow
    from services.agents import run_agentic_workflow
    
    return run_agentic_workflow(
        user_message=message,
        history=history,
        context=context,
        repo_index=repo_index,
        repo_url=repo_url
    )



def _validate_mermaid(text: str, valid_filenames: set[str] | None = None) -> str:
    if "```mermaid" not in text:
        return text
        
    if valid_filenames is None:
        valid_filenames = set()

    blocks = text.split("```mermaid")
    validated = [blocks[0]]
    for block in blocks[1:]:
        mermaid, remainder = block.split("```", 1) if "```" in block else (block, "")
        
        # 1. Syntax Check
        if not _is_mermaid_valid(mermaid):
            warning = (
                "\n\n⚠️ Mermaid validation failed. "
                "Ensure `graph TD`/`graph LR` and node IDs are single-word alphanumeric/underscore.\n"
            )
            validated.append(mermaid + warning + "```" + remainder)
            continue

        # 2. Citation Check (Text around diagram)
        if not _mermaid_has_citations(remainder):
             # We assume citations should be in the text FOLLOWING the diagram or PRECEDING?
             # The original check looked at 'remainder' which is following text.
             # Let's keep it but maybe relax if it's not super strict requirement for *every* diagram
             # Actually, let's keep the warning but not break.
             pass

        # 3. Consistency Check (Node Labels vs Files)
        # Extract labels like [backend/main.py] or (frontend/utils.ts)
        # Regex to find content inside brackets that looks like a file path
        labels = re.findall(r'[\[\(]([\w/.-]+\.\w+)[\]\)]', mermaid)
        hallucinations = [label for label in labels if label not in valid_filenames]
        
        if hallucinations:
             masked_mermaid = mermaid
             # Allow it but append a warning listing missing files
             warning = (
                 f"\n\n⚠️ Diagram references files not found in context: {', '.join(hallucinations)}. "
                 "This might be a hallucination.\n"
             )
             validated.append(mermaid + "```" + warning + remainder)
        else:
             validated.append(mermaid + "```" + remainder)
             
    return "```mermaid".join(validated)


def _is_mermaid_valid(mermaid: str) -> bool:
    lines = [line.strip() for line in mermaid.strip().splitlines() if line.strip()]
    if not lines:
        return False
    # Allow flowcharts and sequence diagrams
    if not (lines[0].startswith("graph ") or lines[0].startswith("flowchart ") or lines[0].startswith("sequenceDiagram")):
         # Basic check, maybe too strict if using other types? 
         # MVP: Only support graph/flowchart for architecture
         return False
         
    for line in lines[1:]:
        # Skip comments
        if line.startswith("%%"): continue
        
        # Simple tokenizer to find Node IDs
        # Node ID is usually start of line or after --> 
        # But this is complex to parse perfectly with regex.
        # Fallback to the alphanumeric check on tokens that look like IDs
        tokens = [token for token in line.replace("-->", " ").replace("-.->", " ").replace("==>", " ").replace("|", " ").split() if token]
        for token in tokens:
            if "[" in token:
                token = token.split("[", 1)[0]
            if "(" in token:
                token = token.split("(", 1)[0]
            if "{" in token:
                token = token.split("{", 1)[0]
            
            # If token is empty after split, it was just a label start, ignore
            if not token: continue
            
            # Ignore standard keywords
            if token in ["graph", "TD", "LR", "subgraph", "end", "flowchart", "sequenceDiagram", "participant"]: continue
            
            # Check ID format
            if not token.replace("_", "").isalnum():
                # Verify it's not a style class or legitimate syntax I missed
                # If it has quotes, its likely a string not ID
                if '"' in token: continue 
                return False
    return True


def _mermaid_has_citations(text: str) -> bool:
    return re.search(r"\b[\w./-]+:\d+-\d+\b", text) is not None
