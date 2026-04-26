"""
main.py
FAgentLLM FastAPI application entrypoint.

Run with:
    uvicorn main:app --reload --port 8000
"""

from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from fastapi.security import OAuth2PasswordRequestForm
from utils.auth import create_access_token, get_current_user

app = FastAPI(
    title="FAgentLLM API",
    description="Multi-agent LLM financial automation system",
    version="0.1.0",
)

@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    # For prototype: admin/admin123
    if form_data.username == "admin" and form_data.password == "admin123":
        access_token = create_access_token(data={"sub": form_data.username})
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Incorrect username or password")

# Allow React frontend (localhost:3000 in dev) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "system": "FAgentLLM"}


# ── Routers ───────────────────────────────────────────────────────────────────
from routers import invoice, budget, cash, reconciliation, credit

app.include_router(invoice.router,        prefix="/invoice",        tags=["Invoice"])
app.include_router(budget.router,         prefix="/budget",         tags=["Budget"])
app.include_router(cash.router,           prefix="/cash",           tags=["Cash"])
app.include_router(reconciliation.router, prefix="/reconciliation", tags=["Reconciliation"])
app.include_router(credit.router,         prefix="/credit",         tags=["Credit"])
