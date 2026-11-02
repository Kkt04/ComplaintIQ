"""MongoDB repository for ComplaintIQ human feedback and operator ratings."""

from typing import Any, Dict, List, Optional
from complaintiq.core.database import get_database


class FeedbackRepository:
    """Async repository for human feedback records stored in MongoDB."""

    COLLECTION_NAME = "human_feedback"

    async def _get_collection(self):
        db = await get_database()
        return db[self.COLLECTION_NAME]

    async def insert(self, doc: Dict[str, Any]) -> str:
        col = await self._get_collection()
        res = await col.insert_one(doc)
        return str(res.inserted_id)

    async def get_by_request_id(self, request_id: str) -> List[Dict[str, Any]]:
        col = await self._get_collection()
        cursor = col.find({"request_id": request_id}).sort("created_at", -1)
        items = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            items.append(doc)
        return items

    async def list_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        col = await self._get_collection()
        cursor = col.find({}).sort("created_at", -1).limit(limit)
        items = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            items.append(doc)
        return items
