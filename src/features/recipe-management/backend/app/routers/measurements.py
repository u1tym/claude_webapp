from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StrictBool

from app.common import Trimmed
from app.deps import AuthContext, get_current_user
from app.services import measurement_service

router = APIRouter(tags=["measurements"])


class MeasurementCreate(BaseModel):
    name_bef: Trimmed
    name_aft: Trimmed
    ness_amount: StrictBool


@router.get("/measurements")
def list_measurements(auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return measurement_service.list_measurements(auth.user.id)


@router.post("/measurements", status_code=201)
def create_measurement(body: MeasurementCreate, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return measurement_service.create_measurement(auth.user.id, body.name_bef, body.name_aft, body.ness_amount)
