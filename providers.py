import asyncio
import random
from typing import List, Dict, Any

class ProviderWrapper:
    name: str

    async def search(self, pickup: str, drop: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def book(self, offer: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def cancel(self, booking_id: str) -> Dict[str, Any]:
        raise NotImplementedError

class MockProvider(ProviderWrapper):
    def __init__(self, name: str):
        self.name = name

    async def search(self, pickup: str, drop: str) -> List[Dict[str, Any]]:
        # Simulate offers with randomness for realism
        offers = []
        if random.random() > 0.1:  # 90% chance of offers
            offers = [
                {"vehicle_type": "auto", "price": random.uniform(50, 100), "eta": random.randint(2, 5), "available": True, "offer_id": f"{self.name}_auto_{random.randint(1,100)}", "meta": {}},
                {"vehicle_type": "cab", "price": random.uniform(150, 250), "eta": random.randint(4, 8), "available": True, "offer_id": f"{self.name}_cab_{random.randint(1,100)}", "meta": {}},
                {"vehicle_type": "bike", "price": random.uniform(30, 60), "eta": random.randint(1, 3), "available": random.choice([True, False]), "offer_id": f"{self.name}_bike_{random.randint(1,100)}", "meta": {}},
            ]
        return [o for o in offers if o["available"]]

    async def book(self, offer: Dict[str, Any]) -> Dict[str, Any]:
        # Simulate delay (1-5s) and 80% confirm rate
        await asyncio.sleep(random.uniform(1, 5))
        if random.random() < 0.8:
            return {
                "status": "confirmed",
                "booking_id": f"{self.name}_bk_{random.randint(1000,9999)}",
                "driver": {"name": f"Driver_{self.name}", "phone": "9999999999", "vehicle_type": offer["vehicle_type"], "eta": offer["eta"]},
                "meta": offer
            }
        else:
            return {"status": "failed", "meta": offer}

    async def cancel(self, booking_id: str) -> Dict[str, Any]:
        # Simulate 90% success
        await asyncio.sleep(0.5)
        return {"status": "cancelled" if random.random() < 0.9 else "failed"}

class DeepLinkProvider(ProviderWrapper):
    def __init__(self, name: str):
        self.name = name

    async def search(self, pickup: str, drop: str) -> List[Dict[str, Any]]:
        # Always return offers, but book will fallback to deep-link
        return [
            {"vehicle_type": "auto", "price": 70.0, "eta": 4, "available": True, "offer_id": f"{self.name}_auto", "meta": {}},
            {"vehicle_type": "cab", "price": 200.0, "eta": 7, "available": True, "offer_id": f"{self.name}_cab", "meta": {}},
        ]

    async def book(self, offer: Dict[str, Any]) -> Dict[str, Any]:
        # Always deep-link fallback
        url = f"https://{self.name}.com/deep-link?pickup=encoded_pickup&drop=encoded_drop&vehicle={offer['vehicle_type']}"
        return {"status": "deep_link", "deep_link_url": url, "meta": offer}

    async def cancel(self, booking_id: str) -> Dict[str, Any]:
        return {"status": "cancelled"}  # No-op for deep-link