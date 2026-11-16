"""Validated request and response data types for local, authorized RF reconstruction."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class RouterRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=253)
    authorized: bool

    @field_validator("identifier")
    @classmethod
    def strip_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Please enter a valid router identifier.")
        return value


class Measurement(BaseModel):
    tx_x: float = Field(ge=0, le=200)
    tx_y: float = Field(ge=0, le=200)
    rx_x: float = Field(ge=0, le=200)
    rx_y: float = Field(ge=0, le=200)
    rssi_dbm: float = Field(ge=-130, le=0)
    baseline_dbm_at_1m: float = Field(default=-40.0, ge=-100, le=0)
    path_loss_exponent: float = Field(default=2.1, ge=1, le=6)
    label: str | None = Field(default=None, max_length=60)


class ReconstructionRequest(BaseModel):
    router_identifier: str = Field(min_length=1, max_length=253)
    authorized: bool
    width_m: float = Field(default=24, ge=4, le=70)
    height_m: float = Field(default=16, ge=4, le=70)
    cell_size_m: float = Field(default=0.75, ge=0.4, le=2.0)
    samples: list[Measurement] = Field(min_length=24, max_length=1500)
    source: Literal["measured", "simulated"] = "measured"


class CellInfo(BaseModel):
    x: int
    y: int
    attenuation_db_per_m: float
    confidence: float


class ReconstructionResponse(BaseModel):
    source: Literal["measured", "simulated"]
    router_identifier: str
    nx: int
    ny: int
    width_m: float
    height_m: float
    cell_width_m: float
    cell_height_m: float
    attenuation: list[list[float]]
    confidence: list[list[float]]
    obstruction_threshold: float
    measurements: int
    transmitter_positions: int
    receiver_positions: int
    coverage_pct: float
    holdout_mae_db: float | None
    spatially_observable: bool
    warnings: list[str]
    rays: list[dict[str, float]]
    model_description: str
