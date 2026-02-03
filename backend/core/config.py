import os
from pathlib import Path
from dotenv import load_dotenv

# Load Auth Keys
auth_keys_path = "c:/pyPractice/auth-keys/auth_export/keys/.env"
if os.path.exists(auth_keys_path):
    load_dotenv(auth_keys_path)
else:
    load_dotenv()

class Settings:
    SESSION_SECRET = os.getenv("SESSION_SECRET", "super-secret-key-dev-only")
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
    GENAI_API_KEY = os.getenv("GENAI_API_KEY")
    DATABASE_URL = "sqlite:///./chat_history.db"

settings = Settings()
