import httpx

from config import INVEST_INSIGHT_TOKEN, INVEST_INSIGHT_URL


class InvestInsightClient:
    def __init__(self):
        self.base_url = INVEST_INSIGHT_URL.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if INVEST_INSIGHT_TOKEN:
            headers["Authorization"] = f"Bearer {INVEST_INSIGHT_TOKEN}"
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=30.0)

    async def run_analysis(self, business_type: str, location: str, radius_km: float = 5.0) -> dict:
        resp = await self.client.post(
            "/api/v1/analysis",
            json={
                "business_type": business_type,
                "location": location,
                "radius_km": radius_km,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def get_demographics(self, zip_code: str) -> dict:
        resp = await self.client.get(f"/api/v1/demographics/{zip_code}")
        resp.raise_for_status()
        return resp.json()

    async def list_properties(self) -> dict:
        resp = await self.client.get("/api/v1/properties")
        resp.raise_for_status()
        return resp.json()

    async def add_property(self, data: dict) -> dict:
        resp = await self.client.post("/api/v1/properties", json=data)
        resp.raise_for_status()
        return resp.json()

    async def update_property(self, property_id: str, data: dict) -> dict:
        resp = await self.client.put(f"/api/v1/properties/{property_id}", json=data)
        resp.raise_for_status()
        return resp.json()

    async def delete_property(self, property_id: str) -> dict:
        await self.client.delete(f"/api/v1/properties/{property_id}")
        return {"success": True, "deleted": property_id}

    async def get_business_types(self) -> list:
        resp = await self.client.get("/api/v1/businesses/types")
        resp.raise_for_status()
        return resp.json()
