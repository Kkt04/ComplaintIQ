"""MongoDB repository for ComplaintIQ triage requests."""

from typing import Any, Dict, List, Optional
from complaintiq.core.database import get_database


class RequestRepository:
    """Async repository for complaint triage requests stored in MongoDB."""

    COLLECTION_NAME = "triage_requests"

    async def _get_collection(self):
        db = await get_database()
        return db[self.COLLECTION_NAME]

    async def insert(self, doc: Dict[str, Any]) -> str:
        col = await self._get_collection()
        res = await col.insert_one(doc)
        return str(res.inserted_id)

    async def get_by_request_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        col = await self._get_collection()
        doc = await col.find_one({"request_id": request_id})
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def update_by_request_id(self, request_id: str, updates: Dict[str, Any]) -> bool:
        col = await self._get_collection()
        res = await col.update_one(
            {"request_id": request_id},
            {"$set": updates},
        )
        return res.modified_count > 0

    async def append_timeline_event(self, request_id: str, event: Dict[str, Any]) -> bool:
        col = await self._get_collection()
        res = await col.update_one(
            {"request_id": request_id},
            {"$push": {"timeline": event}},
        )
        return res.modified_count > 0

    async def list_requests(
        self,
        filter_query: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> List[Dict[str, Any]]:
        col = await self._get_collection()
        query = filter_query or {}
        direction = -1 if sort_desc else 1

        cursor = col.find(query).sort(sort_by, direction).skip(skip).limit(limit)
        items = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            items.append(doc)
        return items

    async def count_requests(self, filter_query: Optional[Dict[str, Any]] = None) -> int:
        col = await self._get_collection()
        query = filter_query or {}
        return await col.count_documents(query)

    async def get_analytics_metrics(self) -> Dict[str, Any]:
        """Aggregate high-level metrics for dashboard and analytics views."""
        col = await self._get_collection()
        total = await col.count_documents({})
        if total == 0:
            return {
                "total_requests": 0,
                "automated_count": 0,
                "human_review_count": 0,
                "automation_rate": 0.0,
                "avg_confidence": 0.0,
                "review_status_breakdown": {},
                "priority_breakdown": {},
                "top_products": [],
                "team_queues": [],
            }

        # Calculate breakdown counts
        status_counts = {}
        for st in ["NOT_REQUIRED", "PENDING", "CORRECTED", "CONFIRMED"]:
            cnt = await col.count_documents({"review_status": st})
            status_counts[st] = cnt

        priority_counts = {}
        for pr in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            cnt = await col.count_documents({"priority": pr})
            priority_counts[pr] = cnt

        automated_cnt = await col.count_documents({"gate_decision": "ALLOW_ROUTING"})
        review_cnt = await col.count_documents({"gate_decision": "HUMAN_REVIEW"})

        # Fetch recent sample to calculate average confidence
        cursor = col.find({}, {"product_confidence": 1, "predicted_product": 1, "assigned_team": 1, "priority": 1}).limit(500)
        total_conf = 0.0
        sample_count = 0
        product_freq: Dict[str, int] = {}
        team_freq: Dict[str, int] = {}
        team_critical: Dict[str, int] = {}

        async for item in cursor:
            c = item.get("product_confidence", 0.0)
            total_conf += c
            sample_count += 1

            p = item.get("predicted_product", "Unknown")
            product_freq[p] = product_freq.get(p, 0) + 1

            t = item.get("assigned_team", "Unassigned")
            team_freq[t] = team_freq.get(t, 0) + 1
            if item.get("priority") == "CRITICAL":
                team_critical[t] = team_critical.get(t, 0) + 1

        avg_conf = round(total_conf / sample_count, 3) if sample_count > 0 else 0.0
        auto_rate = round((automated_cnt / total) * 100, 1) if total > 0 else 0.0

        top_prods = [
            {"product": k, "count": v, "percentage": round((v / max(1, sample_count)) * 100, 1)}
            for k, v in sorted(product_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        team_queues = [
            {
                "queue_name": team,
                "count": count,
                "critical_count": team_critical.get(team, 0),
            }
            for team, count in sorted(team_freq.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "total_requests": total,
            "automated_count": automated_cnt,
            "human_review_count": review_cnt,
            "automation_rate": auto_rate,
            "avg_confidence": avg_conf,
            "review_status_breakdown": status_counts,
            "priority_breakdown": priority_counts,
            "top_products": top_prods,
            "team_queues": team_queues,
        }
