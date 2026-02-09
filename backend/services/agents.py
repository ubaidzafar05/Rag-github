import os
import re
import json
from dataclasses import dataclass
from typing import List, Dict, Optional
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@dataclass

class AgentResponse:
    content: str
    agent_name: str
    metadata: Dict = None

class BaseAgent:
    def __init__(self, name: str, role_prompt: str):
        self.name = name
        self.role_prompt = role_prompt
        self.role_prompt = role_prompt
        self.groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

    def _format_history(self, history: List[Dict]) -> str:
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
        return conversation_text

    def _call_llm(self, messages: List[Dict], temperature: float = 0.7) -> str:
        if not self.groq_client:
            return "Error: Groq Client not configured."

        try:
            resp = self.groq_client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=temperature
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"[{self.name}] Groq Error: {e}")
            return f"Error executing {self.name}: {str(e)}"


    def run(self, input_text: str, context: str = "", history: List[Dict] = None) -> AgentResponse:
        hist_text = self._format_history(history or [])
        full_content = f"Context:\n{context}\n\nHistory:\n{hist_text}\n\nTask: {input_text}"
            
        messages = [
            {"role": "system", "content": self.role_prompt},
            {"role": "user", "content": full_content}
        ]
        content = self._call_llm(messages)
        return AgentResponse(content=content, agent_name=self.name)



class ManagerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Manager", 
            role_prompt="""
You are the Manager Agent. Your job is to classify the user's intent into one of these categories:
1. QUERY: The user is asking a question about the code or architecture.
2. CODING: The user wants to write code, fix a bug, or significantly refactor.
3. GENERAL: General conversation not related to the codebase.

Output ONLY a JSON object: {"intent": "QUERY" | "CODING" | "GENERAL", "reasoning": "..."}
"""
        )

    def route(self, input_text: str) -> str:
        messages = [
            {"role": "system", "content": self.role_prompt},
            {"role": "user", "content": f"User Input: {input_text}"}
        ]
        
        try:
            # Use the unified _call_llm logic (Respects PRIMARY_PROVIDER)
            content = self._call_llm(messages, temperature=0.1) 
            
            # Clean JSON if LLM added markdown blocks
            clean_json = content.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()
            
            # Additional cleanup for Groq/Llama which might chat before JSON
            # Find the first '{' and last '}'
            start = clean_json.find("{")
            end = clean_json.rfind("}")
            if start != -1 and end != -1:
                clean_json = clean_json[start:end+1]

            data = json.loads(clean_json)
            return data.get("intent", "QUERY")
        except Exception as e:
            print(f"Manager Route Error: {e}")
            return "QUERY"





class ResearcherAgent(BaseAgent):
    def __init__(self):
        # Porting the High-IQ prompt from chat.py
        super().__init__(
            name="Researcher",
            role_prompt="""
You are a **Senior Staff Software Engineer** and **Technical Architect**.
Your goal is to provide **world-class, production-ready** code analysis.

## 🧠 COGNITIVE PROCESS (ReAct + Chain of Thought):
Before answering, you must internally simulate a ReAct process:
1. **Thought**: What is the user asking? What information do I have?
2. **Observation**: Scan the provided CODEBASE context.
3. **Analysis**: Connect the dots. Is this a bug? A pattern? A missing file?
4. **Plan**: Formulate the response sections.

## 🌟 RESPONSE STANDARDS:
1. **TONE**: Professional, confident, concise.
2. **EVIDENCE**: Cite exact files/lines `path:line-start-line-end`.
3. **MERMAID**: Use `graph TD` or `graph LR` with single-word IDs.

## 🛑 STRICT RULES:
- **Context Only**: Answer ONLY based on the provided codebase.
- **Citations**: Mandatory for factual claims.
"""
        )
    
    def run(self, input_text: str, context: str = "", history: List[Dict] = None, cache_name: str | None = None) -> AgentResponse:
        # Override run to include validation logic
        response = super().run(input_text, context, history, cache_name=cache_name)

        
        # Validation Logic (Mermaid etc)
        response.content = self._validate_mermaid(response.content, context)
        return response

    def _validate_mermaid(self, text: str, context: str) -> str:
        if "```mermaid" not in text:
            return text
        
        valid_filenames = set(re.findall(r'path="([^"]+)"', context))
        blocks = text.split("```mermaid")
        validated = [blocks[0]]
        
        for block in blocks[1:]:
             mermaid, remainder = block.split("```", 1) if "```" in block else (block, "")
             
             # Basic Syntax
             lines = [l.strip() for l in mermaid.strip().splitlines() if l.strip()]
             if not lines or not (lines[0].startswith("graph") or lines[0].startswith("flowchart")):
                 validated.append(mermaid + "```" + remainder) # Skip invalid
                 continue
                 
             # Hallucination Check
             labels = re.findall(r'[\[\(]([\w/.-]+\.\w+)[\]\)]', mermaid)
             hallucinations = [label for label in labels if label not in valid_filenames]
             
             if hallucinations:
                 warning = f"\n\n⚠️ Diagram references missing files: {', '.join(hallucinations)}.\n"
                 validated.append(mermaid + "```" + warning + remainder)
             else:
                 validated.append(mermaid + "```" + remainder)
                 
        return "```mermaid".join(validated)


class CoderAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Coder",
            role_prompt="""
You are the Coder Agent.
Your ONLY goal is to write high-quality, bug-free code patches based on the requirements.
Output code blocks in their respective languages.
Do not provide excessive explanation, focus on the implementation.
Structure your response so `git apply` or manual copy-pasting is easy.
"""
        )


class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Reviewer",
            role_prompt="""
You are the Reviewer Agent.
You critique code provided by the Coder Agent.
Check for:
1. Syntax errors.
2. Security Vulnerabilities.
3. Style inconsistencies.
If the code is good, simply output "LGTM" and the code. 
If issues are found, list them and rewrite the code fixed.
"""
        )


def run_agentic_workflow(user_message: str, history: List[Dict], context: str, repo_index: str, repo_url: str = None) -> str:
    # 0. Attempt Cache (Only for Gemini)
    cache_name = None
    if PRIMARY_PROVIDER == "gemini" and repo_url and context and len(context) > 2000:
        try:
            from services.gemini_cache import get_or_create_repo_cache
            cache_payload = f"<CODEBASE>\n{context}\n</CODEBASE>\n\n<REPO_INDEX>\n{repo_index}\n</REPO_INDEX>"
            cache_name = get_or_create_repo_cache(repo_url, cache_payload)
        except ImportError:
            pass

    manager = ManagerAgent()
    # Manager doesn't need huge context, just the query usually.
    intent = manager.route(user_message)
    print(f"🤖 Manager routed to: {intent}")

    if intent == "CODING":
        print("🚀 Starting Coding Pipeline...")
        
        # 1. Researcher finds relevant context/explanation
        researcher = ResearcherAgent()
        research_result = researcher.run(f"Explain what needs to be done for: {user_message}", context, history, cache_name=cache_name).content
        
        # 2. Coder writes the code
        coder = CoderAgent()
        code_task = f"User Request: {user_message}\n\nResearch Analysis: {research_result}\n\nWrite the code."
        coder_result = coder.run(code_task, context, history, cache_name=cache_name).content
        
        # 3. Reviewer checks it
        reviewer = ReviewerAgent()
        review_task = f"Review this code implementation:\n\n{coder_result}"
        final_result = reviewer.run(review_task, context, history, cache_name=cache_name).content
        
        return f"**👨‍💻 Coding Pipeline Complete**\n\n{final_result}"

    else:
        researcher = ResearcherAgent()
        return researcher.run(user_message, context, history, cache_name=cache_name).content
