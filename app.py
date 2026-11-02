import os
from fastapi import FastAPI, HTTPException, Security, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import urllib.request
import json

app = FastAPI(
    title="Clothing AI Assistant API",
    description="Secure proxy API for clothing and fashion inquiries powered by OpenRouter.",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI Documentation path
    redoc_url="/redoc" # ReDoc Documentation path
)

# 1. ENFORCE HTTPS
# Redirects all incoming HTTP traffic to secure HTTPS automatically
app.add_middleware(HTTPSRedirectMiddleware)

# 2. CORS CONFIGURATION
# Configured specifically to allow requests from your browser-side Wix subdomains
origins = [
    "https://yourdomain.com",
    "https://www.yourdomain.com",
    "https://wixsite.com", # Replace with your exact Wix site URLs
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Allows browser requests from these domains
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"], # Required HTTP methods
    allow_headers=["*"],         # Allows all headers (including Content-Type/X-API-Key)
)

# 3. AUTHENTICATION SCHEME
# Expects a header named 'X-API-Key' to authorize requests to this API
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Internal secret token protecting this specific endpoint (Set this in server environment variables)
MY_API_SECRET = os.environ.get("MY_API_SECRET", "default_secure_fallback_key_123")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == MY_API_SECRET:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing X-API-Key header credential."
    )

# 4. REQUEST VALIDATION MODEL
class ChatRequest(BaseModel):
    userPrompt: str

# 5. API ENDPOINTS
@app.post("/chat", response_class=JSONResponse)
async def chat_endpoint(request: ChatRequest, api_key: str = Security(get_api_key)):
    """
    Secure chat proxy endpoint. Requires an X-API-Key header.
    Restricts all conversation models specifically to clothing, apparel, and fashion.
    """
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenRouter API Key configuration error on server side.")

    url = "https://openrouter.ai"
    
    # Payload carrying the strict system instructions to bound the AI to clothing
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
            
            # Formats and enforces standard JSON response schema back to Wix
            return JSONResponse(content={"reply": ai_reply}, status_code=200)
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return JSONResponse(content={"error": f"OpenRouter Error: {error_body}"}, status_code=e.code)
    except Exception as e:
        return JSONResponse(content={"error": f"Internal process failed: {str(e)}"}, status_code=500)
