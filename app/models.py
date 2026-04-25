from pydantic import BaseModel

class PaymentRequest(BaseModel):
    amount: float
    currency: str

class PaymentResponse(BaseModel):
    message: str
    idempotency_key: str