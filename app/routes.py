from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
import asyncio
import json
from app.models import PaymentRequest
from app.idempotency import (
    hash_payload,
    get_lock,
    check_idempotency,
    save_initial_request,
    save_final_response
)

router = APIRouter()

@router.post("/process-payment")
async def process_payment(
    request: PaymentRequest,
    idempotency_key: str = Header(None, alias="Idempotency-Key")
):
    # Step 1: Validate Header
    if not idempotency_key:
        return JSONResponse(
            status_code=400,
            content={"message": "Idempotency-Key header is required"}
        )

    # Step 2: Hash Payload
    payload_dict = request.model_dump()
    current_payload_hash = hash_payload(payload_dict)

    # Step 3: Get and acquire lock
    lock = await get_lock(idempotency_key)

    async with lock:
        # Step 4: Check Database
        record = await check_idempotency(idempotency_key, current_payload_hash)

        # Step 5: Handle "in_flight" status - poll OUTSIDE the lock
        if record and record["status"] == "in_flight":
            # Release lock before polling so Request A can finish
            pass

        # Step 6: Handle "done" status
        elif record and record["status"] == "done":
            if record["payload_hash"] != current_payload_hash:
                return JSONResponse(
                    status_code=409,
                    content={"message": "Idempotency key already used for a different request body."}
                )
            return JSONResponse(
                status_code=record["response_status_code"],
                content=json.loads(record["response_body"]),
                headers={"X-Cache-Hit": "true"}
            )

        # Step 7: New request - mark as in_flight inside lock
        elif not record:
            await save_initial_request(idempotency_key, current_payload_hash)

    # --- Lock is now released ---

    # If record was in_flight, poll here (outside the lock)
    if record and record["status"] == "in_flight":
        while True:
            await asyncio.sleep(0.5)
            record = await check_idempotency(idempotency_key, current_payload_hash)
            if record and record["status"] == "done":
                break
        return JSONResponse(
            status_code=record["response_status_code"],
            content=json.loads(record["response_body"]),
            headers={"X-Cache-Hit": "true"}
        )

    # If this is a new request, process it now (lock already released)
    if not record:
        await asyncio.sleep(2)  # Simulate processing

        response_data = {
            "message": f"Charged {request.amount} {request.currency}",
            "idempotency_key": idempotency_key
        }
        response_body_str = json.dumps(response_data)

        await save_final_response(
            key=idempotency_key,
            response_body=response_body_str,
            status_code=201
        )

        return JSONResponse(
            status_code=201,
            content=response_data,
            headers={"X-Cache-Hit": "false"}
        )