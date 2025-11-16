import os
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Union
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException
from sqlalchemy import create_engine, Column, String, Float, Integer, JSON, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON  # For SQLite JSON support
import openai

from schemas import RideRequest, StructuredRideRequest, BookingResponse
from providers import MockProvider, DeepLinkProvider, ProviderWrapper
from decision_engine import orchestrate_booking
from llm_utils import parse_nlu, generate_explanation
from models import Base, Request, ProviderResponse, Booking, AuditTrace

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"  # Swap to postgresql://user:pass@host/db for prod
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Providers (add more as needed, e.g., real ones later)
providers: List[ProviderWrapper] = [
    MockProvider("ola"),
    MockProvider("uber"),
    DeepLinkProvider("rapido")  # Fallback example
]

@app.post("/request-ride", response_model=Dict[str, str])
async def request_ride(request: Union[RideRequest, StructuredRideRequest], background_tasks: BackgroundTasks):
    db = SessionLocal()
    try:
        if isinstance(request, RideRequest):  # Free-text mode
            parsed = await parse_nlu(request.text)
            pickup = parsed["pickup"]
            drop = parsed["drop"]
            priority = parsed["priority"]
        else:  # Structured mode
            pickup = request.pickup
            drop = request.drop
            priority = request.priority

        request_id = str(uuid.uuid4())
        db_request = Request(
            id=request_id,
            pickup=pickup,
            drop=drop,
            priority=priority,
            raw_text=getattr(request, "text", None),
            status="processing",
            created_at=datetime.utcnow()
        )
        db.add(db_request)
        db.commit()

        background_tasks.add_task(orchestrate_booking, request_id, pickup, drop, priority, providers, db)
        return {"request_id": request_id, "status": "processing"}
    finally:
        db.close()

@app.get("/booking/{request_id}", response_model=BookingResponse)
async def get_booking(request_id: str):
    db = SessionLocal()
    try:
        db_request = db.query(Request).filter(Request.id == request_id).first()
        if not db_request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        if db_request.status == "processing":
            return BookingResponse(
                request_id=request_id,
                status="processing",
                chosen=None,
                booking=None,
                explanation=None,
                provider_responses={}
            )
        
        provider_responses = {pr.provider_name: pr.raw_response for pr in db_request.provider_responses}
        booking = db_request.bookings[0] if db_request.bookings else None
        audit = db_request.audit_traces[0] if db_request.audit_traces else None
        
        chosen = None
        explanation = audit.decision_summary if audit else None
        if booking:
            chosen = {
                "provider": booking.provider_name,
                "vehicle_type": booking.driver_info.get("vehicle_type") if booking.driver_info else None,
                "price": booking.price,
                "eta": booking.driver_info.get("eta") if booking.driver_info else None
            }
        
        return BookingResponse(
            request_id=request_id,
            status=db_request.status,
            chosen=chosen,
            booking={
                "booking_id": booking.booking_id,
                "driver": booking.driver_info,
            } if booking else None,
            explanation=explanation,
            provider_responses=provider_responses
        )
    finally:
        db.close()

# Optional webhook for real providers (not used in demo)
@app.post("/provider/webhook")
async def provider_webhook(payload: Dict):
    # Handle updates from real providers here
    pass