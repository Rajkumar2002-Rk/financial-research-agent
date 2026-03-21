from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/health", tags=["Health"])


class HealthStatus(BaseModel):
    status: str
    timestamp: datetime
    version: str = "1.0.0"


@router.get("/live")
async def liveness():
    return HealthStatus(status="healthy", timestamp=datetime.utcnow())


@router.get("/ready")
async def readiness():
    return HealthStatus(status="healthy", timestamp=datetime.utcnow())