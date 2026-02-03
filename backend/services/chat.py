import google.generativeai as genai
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

GENAI_API_KEY = os.getenv("GENAI_API_KEY")
GENAI_MODEL = os.getenv("GENAI_MODEL", "gemini-1.5-flash")

# Initialize the GenAI client
model = None
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)
    model = genai.GenerativeModel(GENAI_MODEL)

def get_chat_response(message: str, history: list[dict], context: str = "", repo_url: str | None = None) -> str:
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
       - **Direct Answer**: Start with a 1-sentence summary of the solution or answer.
       - **Technical Deep Dive**: Explain *why* this works. Use analogies if helpful.
       - **Code**: Provide complete, copy-pasteable snippets. Use comments to explain complex lines.
       - **Caveats/Edge Cases**: Mention security implications, performance tips, or potential bugs.

    3. **FORMATTING**:
       - Use **Bold** for emphasis.
       - Use `Code` for variables/files.
       - Use 🔍, 🛠️, ⚠️, 🚀 emojis sparingly to categorize sections.
       - Use `> Blockquotes` for important takeaways.

    ## 🛑 STRICT RULES:
    - **Context Only**: Answer ONLY based on the provided codebase. If the answer isn't in the code, say "I don't see that in the current files, but generally..."
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
            if msg.get("parts"):
                part = msg["parts"][0]
                if isinstance(part, dict):
                    content = str(part.get("text", ""))
                else:
                    content = str(part)
            elif msg.get("content"):
                content = str(msg.get("content", ""))
            conversation_text += f"{role_label}: {content}\n"
            
    # Combine system prompt, history, and current message
    full_prompt = f"{system_prompt}\n\nConversation History:\n{conversation_text}\n\nUser Question: {message}"
    
    try:
        # Use configured Gemini model
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Error communicating with Gemini: {str(e)}"
