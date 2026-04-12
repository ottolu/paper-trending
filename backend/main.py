from fastapi import FastAPI

app = FastAPI(title="LLM Paper Tracker", version="0.1.0")

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
