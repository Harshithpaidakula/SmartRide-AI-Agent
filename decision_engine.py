import asyncio
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from providers import ProviderWrapper
from llm_utils import generate_explanation
from models import Request, ProviderResponse, Booking, AuditTrace

async def gather_offers(pickup: str, drop: str, providers: List[ProviderWrapper]) -> Dict[str, List[Dict[str, Any]]]:
    tasks = [prov.search(pickup, drop) for prov in providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    offers_by_provider = {}
    for prov, result in zip(providers, results):
        if not isinstance(result, Exception):
            offers_by_provider[prov.name] = result
    return offers_by_provider

def filter_and_sort_candidates(offers_by_provider: Dict[str, List[Dict[str, Any]]], vehicle: str) -> List[Dict[str, Any]]:
    candidates = []
    for prov_name, offers in offers_by_provider.items():
        for offer in offers:
            if offer["vehicle_type"] == vehicle and offer["available"]:
                offer["provider"] = prov_name
                candidates.append(offer)
    return sorted(candidates, key=lambda o: o["price"])  # Cheapest first

async def attempt_parallel_bookings(candidates: List[Dict[str, Any]], providers: Dict[str, ProviderWrapper], timeout: int = 12) -> Dict[str, Any]:
    prov_dict = {p.name: p for p in providers}
    tasks = {}
    for cand in candidates:
        prov = prov_dict[cand["provider"]]
        task = asyncio.create_task(prov.book(cand))
        tasks[task] = (prov, cand)

    done, pending = await asyncio.wait(tasks.keys(), timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
    
    winner = None
    for task in done:
        result = task.result()
        if result["status"] == "confirmed":
            winner = result
            winner["provider"] = tasks[task][0].name
            break  # First confirmed wins

    # Cancel pending and other done tasks
    for task in pending:
        task.cancel()
    for task in done:
        if task.result()["status"] == "confirmed" and task.result() != winner:
            prov, _ = tasks[task]
            await prov.cancel(task.result()["booking_id"])

    return winner or {"status": "failed"}

async def orchestrate_booking(request_id: str, pickup: str, drop: str, priority: List[str], providers: List[ProviderWrapper], db: Session):
    try:
        offers_by_provider = await gather_offers(pickup, drop, providers)
        
        # Save provider responses
        for prov_name, offers in offers_by_provider.items():
            for offer in offers:
                db.add(ProviderResponse(
                    request_id=request_id,
                    provider_name=prov_name,
                    vehicle_type=offer["vehicle_type"],
                    price=offer["price"],
                    eta=offer["eta"],
                    available=str(offer["available"]),  # String for SQLite
                    raw_response=offer,
                    created_at=datetime.utcnow()
                ))
        db.commit()

        chosen_booking = None
        decision_raw = {"attempts": []}
        
        # Try priorities in order
        for vehicle in priority:
            candidates = filter_and_sort_candidates(offers_by_provider, vehicle)
            if candidates:
                booking_result = await attempt_parallel_bookings(candidates, providers)
                decision_raw["attempts"].append({"vehicle": vehicle, "candidates": [c["provider"] for c in candidates], "result": booking_result})
                if booking_result["status"] in ["confirmed", "deep_link"]:
                    chosen_booking = booking_result
                    break

        # Fallback to any cheapest if no priority match
        if not chosen_booking:
            all_candidates = []
            for prov_offers in offers_by_provider.values():
                all_candidates.extend([o for o in prov_offers if o["available"]])
            if all_candidates:
                all_candidates = sorted(all_candidates, key=lambda o: o["price"])
                for cand in all_candidates:
                    cand["provider"] = next(p.name for p in providers if p.name in offers_by_provider and cand in offers_by_provider[p.name])
                booking_result = await attempt_parallel_bookings(all_candidates, providers)
                decision_raw["attempts"].append({"vehicle": "fallback", "candidates": [c["provider"] for c in all_candidates], "result": booking_result})
                if booking_result["status"] in ["confirmed", "deep_link"]:
                    chosen_booking = booking_result

        # Update request status
        db_request = db.query(Request).filter(Request.id == request_id).first()
        if chosen_booking:
            db_booking = Booking(
                request_id=request_id,
                provider_name=chosen_booking["provider"],
                booking_id=chosen_booking.get("booking_id", "n/a"),
                status=chosen_booking["status"],
                driver_info=chosen_booking.get("driver", {}),
                price=chosen_booking["meta"]["price"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(db_booking)
            db_request.status = "confirmed" if chosen_booking["status"] == "confirmed" else "deep_link"
            
            # Generate explanation
            explanation = await generate_explanation(
                chosen_booking["provider"],
                chosen_booking["meta"]["vehicle_type"],
                chosen_booking["meta"]["price"],
                chosen_booking["meta"]["eta"],
                decision_raw["attempts"]
            )
        else:
            db_request.status = "failed"
            explanation = "No rides found across providers."

        # Audit trace
        db.add(AuditTrace(
            request_id=request_id,
            decision_summary=explanation,
            decision_raw=decision_raw,
            created_at=datetime.utcnow()
        ))
        db.commit()
    except Exception as e:
        # Handle errors (log to Sentry in prod)
        db_request = db.query(Request).filter(Request.id == request_id).first()
        db_request.status = "failed"
        db.commit()
    finally:
        db.close()