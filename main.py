"""
main.py
FAgentLLM FastAPI application entrypoint (V3 - 10/10 Causal).
"""

from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from utils.auth import create_access_token

app = FastAPI(
    title="FAgentLLM API",
    description="Multi-agent LLM financial automation system (V3)",
    version="0.3.0",
)

@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if form_data.username == "admin" and form_data.password == "admin123":
        access_token = create_access_token(data={"sub": form_data.username})
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Incorrect username or password")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "system": "FAgentLLM v3 (10/10 Architecture)"}

# -- Routers --
from routers import invoice, budget, cash, reconciliation, credit, intel, payment

app.include_router(invoice.router,        prefix="/api/invoice",        tags=["Invoice"])
app.include_router(budget.router,         prefix="/api/budget",         tags=["Budget"])
app.include_router(cash.router,           prefix="/api/cash",           tags=["Cash"])
app.include_router(reconciliation.router, prefix="/api/reconciliation", tags=["Reconciliation"])
app.include_router(credit.router,         prefix="/api/credit",         tags=["Credit"])
app.include_router(payment.router,        prefix="/api/payment",        tags=["Payment"])
app.include_router(intel.router,          prefix="/api/intel",          tags=["Intelligence"])
