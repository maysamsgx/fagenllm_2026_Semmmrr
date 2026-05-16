"""
main.py
The main entry point for our FastAPI app. This is what uvicorn runs.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from utils.auth import create_access_token
from fastapi.responses import RedirectResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# Ensure the default stream handler uses UTF-8 on Windows
import sys
for handler in logging.root.handlers:
    if isinstance(handler, logging.StreamHandler):
        handler.setStream(sys.stdout) # sys.stdout was already reconfigured in evaluator.py if run there
logger = logging.getLogger("fagentllm")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Make sure every dashboard has data the first time the user opens it."""
    if os.getenv("FAGENTLLM_SKIP_BOOTSTRAP", "").lower() not in ("1", "true", "yes"):
        try:
            from utils.bootstrap import seed_if_empty, ensure_initial_match_state, ensure_forecast_current
            seed_if_empty()
            ensure_initial_match_state()
            ensure_forecast_current()
        except Exception as e:
            logger.error(f"Bootstrap failed: {e}")
    else:
        logger.info("FAGENTLLM_SKIP_BOOTSTRAP set; skipping data bootstrap.")
    yield


app = FastAPI(
    title="FAgentLLM Financial Intelligence",
    description="Multi-agent autonomous financial orchestration with causal reasoning and system-level intelligence.",
    version="0.4.0",
    lifespan=lifespan,
)

@app.get("/")
async def root():
    """Redirect root to /docs for easier navigation."""
    return RedirectResponse(url="/docs")

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
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176", "http://localhost:5177"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "system": "FAgentLLM Autonomous Financial Intelligence (10/10 Architecture)"}

# -- Routers --
from routers import invoice, budget, cash, reconciliation, credit, payment, departments, analytics, governance

app.include_router(invoice.router,        prefix="/api/invoice",        tags=["Invoice"])
app.include_router(budget.router,         prefix="/api/budget",         tags=["Budget"])
app.include_router(cash.router,           prefix="/api/cash",           tags=["Cash"])
app.include_router(reconciliation.router, prefix="/api/reconciliation", tags=["Reconciliation"])
app.include_router(credit.router,         prefix="/api/credit",         tags=["Credit"])
app.include_router(payment.router,        prefix="/api/payment",        tags=["Payment"])

app.include_router(departments.router,    prefix="/api/departments",    tags=["Departments"])
app.include_router(analytics.router,      prefix="/api/analytics",      tags=["Analytics"])
app.include_router(governance.router,     prefix="/api/governance",     tags=["Governance"])
