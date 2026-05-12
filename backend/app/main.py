"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import chat, workflows, admin

app = FastAPI(
    title="DigiNav AI",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

# CORS – allow the Next.js frontend origin(s)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")
app.include_router(admin.router, prefix="/api/admin")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
