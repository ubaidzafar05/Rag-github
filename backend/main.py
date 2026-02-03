from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import JSONResponse
from core.config import settings
from database import engine
from db_models import Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Github RAG Chat API")

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )

# Middleware
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services Startup Checks
from services.chat import GENAI_API_KEY
if not GENAI_API_KEY:
    print("WARNING: GENAI_API_KEY is not set. Chat will not function.")

from services.retrieval import chromadb
if chromadb:
    print("INFO: ChromaDB is available and will be used for vector storage.")
else:
    print("WARNING: ChromaDB not found. Vector storage will be in-memory (numpy) only.")

# Include Routers
from routers import auth, session, ingest, chat, editor

app.include_router(auth.router)
app.include_router(session.router)
app.include_router(ingest.router)
app.include_router(chat.router)
app.include_router(editor.router)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Github RAG Chat Backend Running"}