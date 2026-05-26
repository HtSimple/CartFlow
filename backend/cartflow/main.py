from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from cartflow.checkout import checkout_cart


class CheckoutRequest(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    final_amount: Any | None = None


app = FastAPI(title="CartFlow API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/checkout")
def checkout(request: CheckoutRequest) -> dict[str, Any]:
    return checkout_cart(request.items, client_final_amount=request.final_amount)
