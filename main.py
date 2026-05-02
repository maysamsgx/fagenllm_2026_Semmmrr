"""
main.py
The main entry point for our FastAPI app. This is what uvicorn runs.
"""

import logging
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from utils.auth import create_access_token
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("fagentllm")

app = FastAPI(
    title="FAgentLLM API",
    description="Multi-agent LLM financial automation system (V3)",
    version="0.3.0",
)


@app.on_event("startup")
def _bootstrap_data() -> None:
    """Make sure every dashboard has data the first time the user opens it."""
    if os.getenv("FAGENTLLM_SKIP_BOOTSTRAP", "").lower() in ("1", "true", "yes"):
        logger.info("FAGENTLLM_SKIP_BOOTSTRAP set; skipping data bootstrap.")
        return
    try:
        from utils.bootstrap import seed_if_empty, ensure_initial_match_state
        seed_if_empty()
        ensure_initial_match_state()
    except Exception as e:
        logger.error(f"Bootstrap failed: {e}")

@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "admin123")
    if form_data.username == admin_user and form_data.password == admin_pass:
        access_token = create_access_token(data={"sub": form_data.username})
        return {"access_token": access_token, "token_type": "bearer"}
    logger.warning(f"Failed login attempt for user: {form_data.username}")
    raise HTTPException(status_code=400, detail="Incorrect username or password")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "system": "FAgentLLM v3 (10/10 Architecture)"}

# -- Routers --
from routers import invoice, budget, cash, reconciliation, credit, intel, payment, departments

app.include_router(invoice.router,        prefix="/api/invoice",        tags=["Invoice"])
app.include_router(budget.router,         prefix="/api/budget",         tags=["Budget"])
app.include_router(cash.router,           prefix="/api/cash",           tags=["Cash"])
app.include_router(reconciliation.router, prefix="/api/reconciliation", tags=["Reconciliation"])
app.include_router(credit.router,         prefix="/api/credit",         tags=["Credit"])
app.include_router(payment.router,        prefix="/api/payment",        tags=["Payment"])
app.include_router(intel.router,          prefix="/api/intel",          tags=["Intelligence"])
app.include_router(departments.router,    prefix="/api/departments",    tags=["Departments"])
