from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class RideRequest(BaseModel):
    text: str

class StructuredRideRequest(BaseModel):
    pickup: str
    drop: str
    priority: List[str]
    passenger_name: Optional[str] = "Guest"

class BookingResponse(BaseModel):
    request_id: str
    status: str
    chosen: Optional[Dict[str, Any]]
    booking: Optional[Dict[str, Any]]
    explanation: Optional[str]
    provider_responses: Dict[str, Any]