import requests
import json

# Setup
URL = "http://localhost:8000/chat"
REPO_URL = "https://github.com/ubaidzafar05/medicat-assistant-bot" # User's evident repo
HEADERS = {"Content-Type": "application/json"}

# 1. Ingest First (to ensure context)
print("Ingesting...")
requests.post("http://localhost:8000/ingest", json={"repo_url": REPO_URL})

# 2. Ask Complex Question
QUESTION = "Explain the architecture of this app and show a diagram of how the User, Backend, and Database interact."

payload = {
    "message": QUESTION,
    "history": []
}

print(f"Asking: {QUESTION}")
try:
    response = requests.post(URL, json=payload, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        print("\n\n=== AI RESPONSE ===\n")
        print(data["response"])
        print("\n===================\n")
        
        # Validation
        ans = data["response"]
        if "```mermaid" in ans:
            print("✅ Mermaid Diagram Detected")
        else:
            print("❌ No Mermaid Diagram")
            
        if "##" in ans:
            print("✅ Markdown Headers Detected")
        else:
            print("❌ Poor Formatting")
            
    else:
        print(f"Error: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Request Failed: {e}")
