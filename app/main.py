from fastapi import FastAPI
from app.database import init_db
from app.routes import router

app = FastAPI(
    title="Idempotency Gateway",
    description="A payment processing API that ensures requests are processed exactly once",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    await init_db()

app.include_router(router)

@app.get("/")
async def root():
    return {"status": "ok", "message": "Idempotency Gateway is running"}