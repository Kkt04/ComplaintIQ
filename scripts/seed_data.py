"""Seed script to populate ComplaintIQ MongoDB with realistic CFPB consumer complaints."""

import asyncio
from datetime import datetime, timezone
import uuid
from complaintiq.core.database import get_database, close_db_connection
from complaintiq.serving.schemas import TriageRequest
from complaintiq.serving.services.triage_service import TriageService
from complaintiq.serving.services.feedback_service import FeedbackService
from complaintiq.serving.schemas import HumanReviewRequest


SEED_COMPLAINTS = [
    {
        "text": "I am receiving daily automated phone calls at 4am from Midland Credit Management regarding a disputed debt of $1,450 that was settled in full three years ago. My SSN is 000-12-3456 and my phone is 555-123-4567. Cease all harassment.",
        "client_id": "seed_client_01"
    },
    {
        "text": "Citibank charged my credit card account an unlawful $49 late fee and increased my APR to 29.99% despite my payment having been submitted and received three days prior to the billing cycle due date.",
        "client_id": "seed_client_02"
    },
    {
        "text": "Wells Fargo Home Mortgage failed to properly credit our monthly escrow payments for property taxes. We received a notice of default and imminent foreclosure auction on our primary residence scheduled for next Tuesday.",
        "client_id": "seed_client_03"
    },
    {
        "text": "Navient has repeatedly failed to process my Public Service Loan Forgiveness (PSLF) application. I have made 120 qualifying payments over ten years working for public schools.",
        "client_id": "seed_client_04"
    },
    {
        "text": "Ally Auto Finance sent a repossession order for my leased vehicle despite account statements showing full automatic recurring debit payments made on the 1st of every month.",
        "client_id": "seed_client_05"
    },
    {
        "text": "Chase Bank placed an indefinite freeze on my primary checking account holding my direct-deposited paycheck, preventing me from purchasing food or paying rent.",
        "client_id": "seed_client_06"
    },
    {
        "text": "I initiated a wire remittance transfer of $3,200 via Western Union to support family overseas, but the funds have been withheld for 14 days without explanation or refund.",
        "client_id": "seed_client_07"
    },
    {
        "text": "Experian and TransUnion are reporting a delinquent account that belongs to an individual with a similar name in another state. I submitted documentation but the trade line remains on my report.",
        "client_id": "seed_client_08"
    },
    {
        "text": "Speedy Cash assessed an effective annual percentage rate of 650% on a short-term installment loan and began calling my supervisor after I requested a payment arrangement.",
        "client_id": "seed_client_09"
    },
    {
        "text": "CRITICAL EMERGENCY: Someone committed identity theft, hacked my online credentials, and initiated $12,500 in unauthorized wire transfers from my accounts yesterday.",
        "client_id": "seed_client_10"
    },
    {
        "text": "I noticed an ambiguous financial issue on my online statement. The balances looked uncertain and confusing to me, please clarify general calculation.",
        "client_id": "seed_client_11"
    },
    {
        "text": "There is an uncertain calculation with my monthly service fee that appears ambiguous and unclear.",
        "client_id": "seed_client_12"
    }
]


async def seed():
    print("Connecting to ComplaintIQ datastore...")
    db = await get_database()
    triage_service = TriageService()
    feedback_service = FeedbackService()

    print(f"Ingesting {len(SEED_COMPLAINTS)} realistic CFPB complaint narratives...")
    created_ids = []
    for item in SEED_COMPLAINTS:
        req = TriageRequest(text=item["text"], client_id=item["client_id"])
        res = await triage_service.triage(req)
        created_ids.append(res.request_id)
        print(f" -> Ingested {res.request_id}: Product='{res.predicted_product}' Team='{res.assigned_team}' Gate='{res.gate_decision.value}'")

    # Simulate human review correction on one of the ambiguous complaints
    if created_ids:
        last_id = created_ids[-1]
        print(f"\nSimulating human-in-the-loop review correction for {last_id}...")
        await feedback_service.submit_review(
            last_id,
            HumanReviewRequest(
                action="CORRECT",
                corrected_product="Checking or savings account",
                corrected_issue="Managing an account",
                correction_reason="Specialist inspected bank statement and confirmed account service fee dispute.",
                reviewer_id="lead_specialist_sarah",
            )
        )
        print(f" -> Successfully corrected {last_id} to Checking or savings account.")

    print("\nDatabase seeding completed successfully.")
    await close_db_connection()


if __name__ == "__main__":
    asyncio.run(seed())
