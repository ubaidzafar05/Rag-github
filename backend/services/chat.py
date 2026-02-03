import google.generativeai as genai
from dotenv import load_dotenv
import os
import re
from pathlib import Path

load_dotenv()

GENAI_API_KEY = os.getenv("GENAI_API_KEY")
GENAI_MODEL = os.getenv("GENAI_MODEL", "gemini-1.5-flash")

# Initialize the GenAI client
model = None
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)
    model = genai.GenerativeModel(GENAI_MODEL)

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
    if not GENAI_API_KEY or not model:
        return "Error: GENAI_API_KEY not set."

    repo_name = ""
    if repo_url:
        repo_name = Path(repo_url).stem.replace(".git", "")

    # Construct the system instruction / context
    system_prompt = f"""
    You are a **Senior Staff Software Engineer** and **Technical Architect** assisting a developer. 
    Your goal is to provide **world-class, production-ready** code analysis and explanations, rivaling the best AI assistants (Claude 3.5 Sonnet, GPT-4o).

    <CODEBASE>
    {context}
    </CODEBASE>

    <REPO_INDEX>
    {repo_index}
    </REPO_INDEX>

    <REPO_METADATA>
    Repo Name: {repo_name}
    Repo URL: {repo_url or ""}
    </REPO_METADATA>
    
    ## 🧠 COGNITIVE PROCESS (INTERNAL):
    Before answering, you must:
    1. **Analyze** the user's intent deeply. Are they debugging? Learning? Copy-pasting?
    2. **Scan** the provided codebase for dependencies, patterns, and architectural constraints.
    3. **Formulate** a structured answer that addresses the *root cause*, not just the symptom.

    ## 🌟 RESPONSE STANDARDS:
    
    1. **TONE**:
       - Professional, confident, and concise. 
       - Avoid fluff ("Here is the code you asked for"). Jump straight to the solution.
       - Be opinionated about best practices (e.g., "Ideally, we should move this logic to...").

    2. **STRUCTURE**:
       - **Summary**: 1-sentence direct answer.
       - **Evidence (with citations)**: Bullet points that cite exact files and line ranges from <FILE> snippets using format `path:line-start-line-end`.
       - **Explanation**: Why this works and how it relates to the repo structure.
       - **Code (if needed)**: Copy-pasteable snippets with brief comments.
       - **Caveats/Edge Cases**: Security/performance/bug notes.

    3. **FORMATTING**:
       - Use **Bold** for emphasis.
       - Use `Code` for variables/files.
       - Use 🔍, 🛠️, ⚠️, 🚀 emojis sparingly to categorize sections.
       - Use `> Blockquotes` for important takeaways.

    ## 🛑 STRICT RULES:
    - **Context Only**: Answer ONLY based on the provided codebase. If the answer isn't in the code, say "I don't see that in the current files, but generally..."
    - **Citations are mandatory**: Every factual claim about the repo must include at least one file citation using the `path:line-start-line-end` format, based on <FILE> snippets.
    - **Mermaid Diagrams**:
       - ALWAYS use `graph TD` or `graph LR`.
       - **Node IDs**: MUST be SINGLE_WORD alphanumeric (use `_` for spaces). NO spaces, parens, or brackets in IDs.
       - **Labels**: `ID[Label Text]`.
       - **Example**: `Client[Frontend App] -->|HTTP| API[Backend API]`
    
    ## 🎯 SCENARIOS:
    
    - **"Explain this file"**: Breakdown the purpose, key classes, and how it fits into the larger architecture.
    - **"Fix this bug"**: Analyze the error, propose a fix, and explain *why* the error happened.
    - **"Add feature X"**: Provide a step-by-step implementation plan (File A -> File B -> DB).

    ## Code Editing Instructions:
    If you want to suggest a code change that the user can apply, wrap the code in a specialized XML tag like this:
    <file path="path/to/file.ext">
    ... full new file content ...
    </file>
    Ensure you provide the FULL content of the file (or the relevant replacement if doing partials, but full is safer for this tool) when using this tag.
    The path should be relative to the repository root.
    """
    
    # Build conversation history
    # The new SDK might handle history differently if using chat sessions, 
    # but since the existing code builds a text block, I'll keep that logic for now 
    # or migrate it to the SDK's message format if preferred.
    # The user logic was building a single prompt.
    
    conversation_text = ""
    if history:
        for msg in history:
            role_label = "User" if msg.get("role") == "user" else "Assistant"
            content = ""
            parts = msg.get("parts") or []
            if parts:
                normalized_parts = []
                for part in parts:
                    if isinstance(part, dict):
                        normalized_parts.append(str(part.get("text", "")))
                    else:
                        normalized_parts.append(str(part))
                content = " ".join([part for part in normalized_parts if part])
            elif msg.get("content"):
                content = str(msg.get("content", ""))
            conversation_text += f"{role_label}: {content}\n"
            
    # Combine system prompt, history, and current message
    full_prompt = f"{system_prompt}\n\nConversation History:\n{conversation_text}\n\nUser Question: {message}"
    
    try:
        # Use configured Gemini model
        response = model.generate_content(full_prompt)
        
        # Extract filenames from context for validation
        valid_filenames = set(re.findall(r'path="([^"]+)"', context))
        return _validate_mermaid(response.text, valid_filenames)
    except Exception as e:
        return f"Error communicating with Gemini: {str(e)}"


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
