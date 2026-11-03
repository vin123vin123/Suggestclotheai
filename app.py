import os
import json
import urllib.request
import urllib.error
from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(
    title="Clothing AI Assistant API",
    description="Secure proxy API for clothing and fashion inquiries powered by OpenRouter.",
    version="1.0.0",
    docs_url="/docs",  
    redoc_url="/redoc" 
)

# CORS CONFIGURATION
origins = [
    "https://yourdomain.com",
    "https://yourdomain.com",
    "https://wixsite.com", 
    "*" # Keeps testing completely open for Wix frontend domains
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"], 
    allow_headers=["*"],         
)

# AUTHENTICATION SCHEME
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

MY_API_SECRET = os.environ.get("MY_API_SECRET", "default_secure_fallback_key_123")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == MY_API_SECRET:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing X-API-Key header credential."
    )

class ChatRequest(BaseModel):
    userPrompt: str

# ROUTE HANDLERS
@app.get("/chat", response_class=JSONResponse)
async def chat_status_check():
    return JSONResponse(
        content={
            "status": "active",
            "message": "The Clothing AI API is operational. Send a POST request containing an 'X-API-Key' header to chat."
        },
        status_code=200
    )

@app.post("/chat", response_class=JSONResponse)
async def chat_endpoint(request: ChatRequest, api_key: str = Security(get_api_key)):
    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY variable is missing on Render Environment Variables.")
        return JSONResponse(content={"error": "Server configuration mismatch."}, status_code=500)

    url = "https://openrouter.ai"
    
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
    
    req_body = json.dumps(payload).encode('utf-8')
    
    # Custom Headers spoofing a standard desktop browser to bypass Cloudflare 1010 blocking layers
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "HTTP-Referer": "https://yourdomain.com", 
        "X-OpenRouter-Title": "Clothing Assistant App"
    }
    
    req = urllib.request.Request(
        url,
        data=req_body,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            raw_body = response.read().decode('utf-8')
            
            if not raw_body or raw_body.strip() == "":
                return JSONResponse(content={"error": "OpenRouter returned an empty payload."}, status_code=502)
            
            try:
                res_data = json.loads(raw_body)
            except json.JSONDecodeError:
                return JSONResponse(content={"error": "Received invalid non-JSON data from the AI provider."}, status_code=502)

            if 'choices' in res_data and len(res_data['choices']) > 0:
                ai_reply = res_data['choices'][0]['message']['content']
                return JSONResponse(content={"reply": ai_reply}, status_code=200)
            else:
                return JSONResponse(content={"error": "Unexpected JSON nesting structure returned by AI provider."}, status_code=502)
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"OpenRouter HTTP Error status code {e.code}: {error_body}")
        if e.code == 429:
            return JSONResponse(content={"error": "OpenRouter free tier limit reached. Try again shortly."}, status_code=429)
        return JSONResponse(content={"error": f"Model error code {e.code}: {error_body}"}, status_code=e.code)
    except Exception as e:
        print(f"General internal crash: {str(e)}")
        return JSONResponse(content={"error": "Internal server processing crash."}, status_code=500)
