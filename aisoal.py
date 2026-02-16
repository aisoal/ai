import json
import os
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import perplexity
import tiktoken
from pypdf import PdfReader

app = FastAPI(title="AIsoal AI Layer")

COOKIE_FILE = "cookies.json"
client = None


def init_client():
    global client
    cookies = {}
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r") as f:
                cookies = json.load(f)
            print("✅ Cookies loaded.")
        except Exception as e:
            print(f"⚠️ Error loading cookies: {e}")

    try:
        client = perplexity.Client(cookies=cookies)
        print("✅ Perplexity Client Ready.")
    except Exception as e:
        print(f"❌ Client Init Error: {e}")


init_client()


def count_tokens(text: str) -> int:
    """Estimasi token menggunakan encoding cl100k_base (GPT-4/Llama3 compatible)"""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception as e:
        print(f"⚠️ Tokenizer error: {e}")
        return 0


def extract_text_from_pdf(file_path: str) -> str:
    """Ekstrak raw text dari PDF untuk perhitungan token"""
    text = ""
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print(f"⚠️ Failed to read PDF text: {e}")
    return text


class GeneratePayload(BaseModel):
    query: str
    model: str = "sonar"
    file_path: Optional[str] = None


@app.post("/generate")
def generate(payload: GeneratePayload):
    global client
    if not client:
        init_client()

    req_model = payload.model.lower()
    final_mode = "auto"
    final_model = None

    if any(
        x in req_model
        for x in [
            "gpt-5.2-thinking",
            "claude-4.5-sonnet-thinking",
            "gemini-3.0-pro",
            "gemini-3.0-flash",
            "kimi-k2-thinking",
            "grok-4.1-reasoning",
        ]
    ):
        final_mode = "reasoning"
        final_model = payload.model
    elif any(x in req_model for x in ["sonar", "gpt-5.2", "claude-4.5-sonnet", "grok-4.1"]):
        final_mode = "pro"
        final_model = payload.model

    print(f"\n🚀 Request: {final_model or 'Auto'} | Mode: {final_mode}")

    files_data = {}
    file_content_text = ""

    if payload.file_path and os.path.exists(payload.file_path):
        filename = os.path.basename(payload.file_path)
        try:
            with open(payload.file_path, "rb") as f:
                files_data[filename] = f.read()

            if filename.lower().endswith(".pdf"):
                file_content_text = extract_text_from_pdf(payload.file_path)

            print(f"📂 File attached: {filename}")
        except Exception as e:
            print(f"❌ File Error: {e}")

    full_input = f"{payload.query}\n{file_content_text}"
    input_tokens = count_tokens(full_input)

    try:
        start_time = time.time()
        response = client.search(
            query=payload.query,
            mode=final_mode,
            model=final_model,
            files=files_data if files_data else None,
        )
        duration = round(time.time() - start_time, 2)

        answer_text = (
            response.get("answer", str(response)) if isinstance(response, dict) else str(response)
        )

        output_tokens = count_tokens(answer_text)
        total_tokens = input_tokens + output_tokens

        print("✅ Response received.")
        print(f"📝 Answer: {answer_text}")
        print(
            f"📊 Stats: {duration}s | Tokens: {input_tokens} -> {output_tokens} (Total: {total_tokens})"
        )

        return {
            "status": "success",
            "answer": answer_text,
            "usage_estimate": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "duration": duration,
            },
        }

    except Exception as e:
        print(f"❌ API Error: {e}")
        if "401" in str(e) or "unauthorized" in str(e).lower():
            init_client()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=8000)
