# GitHub RAG Chat 🤖

A premium, intelligent chat application that allows you to converse with any GitHub repository.

**Powered by:**
-   **Backend**: FastAPI, Repomix (Code Packing), Firecrawl (Docs), **Gemini 2.0 Flash** (LLM).
-   **Frontend**: Next.js 15, TailwindCSS, Shadcn UI, Framer Motion, Mermaid.js.

## 🚀 How to Run

### Prerequisites
-   Node.js & npm
-   Python 3.10+
-   Gemini API Key

### 1. Backend (Python)
Open a terminal in the root directory:

```bash
cd backend

# Create virtual env (first time only)
python -m venv venv

# Activate venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
# source venv/bin/activate

# Install dependencies (first time only)
pip install fastapi uvicorn google-genai itsdangerous firecrawl-py python-multipart sqlalchemy
# Note: google-genai is the new SDK replacing google-generativeai

# Set API Key (Linux/Mac)
# export GENAI_API_KEY="your_key_here"
# Windows (PowerShell)
# $env:GENAI_API_KEY="your_key_here"
# OR create a .env file in /backend with GENAI_API_KEY=...

# Run Server
uvicorn main:app --reload --port 8000
```

### 2. Frontend (Next.js)
Open a new terminal:

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Run Dev Server
npm run dev
```

Visit **http://localhost:3000** to start chatting!

## ✨ Features
-   **Repo Ingestion**: Clones and intelligently packs entire repositories using Repomix.
-   **Docs Integration**: Optional Firecrawl integration to read external documentation.
-   **Smart UI**: Premium dark mode design with "Smart Action" buttons.
-   **Visual Explanations**: Automatically generates Mermaid.js flowcharts for architecture questions.
-   **Persistent History**: Chat sessions are saved locally using SQLite.
-   **Knowledge Graph**: Visualize your codebase structure with an interactive node-link graph.
-   **Agentic "Apply Fix"**: The AI can now propose code changes which you can apply with one click.
-   **Latest SDK**: Migrated to the latest `google-genai` SDK for better performance and future-proofing.

## 🔮 Future Roadmap (Brainstorming)
Ideas for extending the project:

1.  **🤖 Local LLM Support**: Toggle to use Ollama/DeepSeek for privacy.
2.  **🗣️ Voice Interface**: Talk to your codebase.
3.  **☁️ Cloud Deployment**: Dockerize and deploy to AWS/GCP.
4.  **🔐 Advanced Auth**: Multi-user support with GitHub OAuth.
