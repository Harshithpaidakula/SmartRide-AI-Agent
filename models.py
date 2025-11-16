from sqlalchemy import Column, String, Float, Integer, JSON, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Request(Base):
    __tablename__ = "requests"
    id = Column(String, primary_key=True, index=True)
    pickup = Column(String)
    drop = Column(String)
    priority = Column(JSON)  # List of strings
    raw_text = Column(String, nullable=True)
    status = Column(String)
    created_at = Column(DateTime)

    provider_responses = relationship("ProviderResponse", back_populates="request")
    bookings = relationship("Booking", back_populates="request")
    audit_traces = relationship("AuditTrace", back_populates="request")

class ProviderResponse(Base):
    __tablename__ = "provider_responses"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, ForeignKey("requests.id"))
    provider_name = Column(String)
    vehicle_type = Column(String)
    price = Column(Float)
    eta = Column(Integer)
    available = Column(String)  # "True" or "False" as string for SQLite
    raw_response = Column(JSON)
    created_at = Column(DateTime)

    request = relationship("Request", back_populates="provider_responses")

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, ForeignKey("requests.id"))
    provider_name = Column(String)
    booking_id = Column(String)
    status = Column(String)
    driver_info = Column(JSON)
    price = Column(Float)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    request = relationship("Request", back_populates="bookings")

class AuditTrace(Base):
    __tablename__ = "audit_traces"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, ForeignKey("requests.id"))
    decision_summary = Column(String)
    decision_raw = Column(JSON)
    created_at = Column(DateTime)

    request = relationship("Request", back_populates="audit_traces")