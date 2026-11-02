import os
import json
import urllib.request
import urllib.error
from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(
    title="Clothing AI Assistant API",
    description="Secure proxy API for clothing and fashion inquiries powered by OpenRouter.",
    version="1.0.0",
    docs_url="/docs",  # Interactive Swagger UI Documentation path
    redoc_url="/redoc" # ReDoc Documentation path
)

# 1. ENFORCE HTTPS
# Automatically redirects all incoming HTTP traffic to secure HTTPS
app.add_middleware(HTTPSRedirectMiddleware)

# 2. CORS CONFIGURATION
# Configured to allow browser-side direct requests from your Wix subdomains
origins = [
    "https://yourdomain.com",
    "https://yourdomain.com",
    "https://wixsite.com", # Replace with your exact Wix site domain strings
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Allows browser requests from these specific origins
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"], 
    allow_headers=["*"],         # Allows custom headers (Content-Type, X-API-Key)
)

# 3. AUTHENTICATION SCHEME
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Read variables securely from your platform environment dashboard settings
MY_API_SECRET = os.environ.get("MY_API_SECRET", "default_secure_fallback_key_123")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == MY_API_SECRET:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing X-API-Key header credential."
    )

# 4. DATA STRUCT VALIDATION MODEL
class ChatRequest(BaseModel):
    userPrompt: str

# 5. API ROUTE HANDLERS

@app.get("/chat", response_class=JSONResponse)
async def chat_status_check():
    """
    Status endpoint. Gracefully responds to standard browser calls (GET) 
    instead of throwing internal server errors.
    """
    return JSONResponse(
        content={
            "status": "active",
            "message": "The Clothing AI API is operational. Send a POST request containing an 'X-API-Key' header to chat."
        },
        status_code=200
    )

@app.post("/chat", response_class=JSONResponse)
async def chat_endpoint(request: ChatRequest, api_key: str = Security(get_api_key)):
    """
    Secure chat proxy endpoint. Binds conversational LLM scope tightly to 
    clothing, garments, style advice, and textile design.
    """
    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY variable is missing on the server.")
        return JSONResponse(content={"error": "Server configuration mismatch."}, status_code=500)

    url = "https://openrouter.ai"
    
    # System payload context locking prompt to clothing queries only
    payload = {
        "model": "openrouter/free",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict clothing store assistant. You must ONLY answer questions "
                    "related to fashion, clothing, apparel, outfits, styles, and fabrics. If the user asks "
                    "about ANY other topic (such as programming, cooking, history, math, or general knowledge), "
                    "politely refuse to answer and remind them that you only talk about clothing."
                )
            },
            {"role": "user", "content": request.userPrompt}
        ]
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            ai_reply = res_data['choices'][0]['message']['content']
            return JSONResponse(content={"reply": ai_reply}, status_code=200)
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"OpenRouter HTTP Error status code {e.code}: {error_body}")
        return JSONResponse(content={"error": f"Model layer down stream error: {error_body}"}, status_code=e.code)
    except Exception as e:
        print(f"General internal crash: {str(e)}")
        return JSONResponse(content={"error": f"Internal system failed to compute response."}, status_code=500)
