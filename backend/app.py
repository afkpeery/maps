"""Local-first FastAPI application. Never initiates arbitrary network scanning."""
from __future__ import annotations

import ipaddress
import re
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from demo import make_demo
from models import RouterRequest, ReconstructionRequest, ReconstructionResponse, CalibrationRequest, CalibrationResponse
from reconstruction import reconstruct
from calibration import calibrate
from hardware import CaptureRequest, CapturedReading, SensorError, capture_reading, capabilities

app = FastAPI(title="Maps RF Reconstruction API", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


class IdentifierResponse(BaseModel):
    identifier: str
    kind: str
    verified: bool
    ready_to_map: bool
    message: str


def classify_router(identifier: str):
    value = identifier.strip()
    try:
        ip = ipaddress.ip_address(value)
        if ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError("Only private, local IPv4 router addresses are accepted.")
        return "local_ip"
    except ValueError as exc:
        if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", value):
            raise ValueError("Invalid or non-local IPv4 address.") from exc
    if value.endswith(".local") and re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.local", value):
        return "local_hostname"
    if 1 <= len(value.encode("utf-8")) <= 32 and not any(c in "/\\" for c in value):
        return "ssid"
    raise ValueError("Enter a private router IPv4 address, .local hostname, or SSID up to 32 bytes.")


@app.get("/api/health")
def health():
    return {"ok": True, "measurement_hardware": "not attached", "mode": "local"}


@app.post("/api/identify", response_model=IdentifierResponse)
def identify_router(payload: RouterRequest):
    if not payload.authorized:
        raise HTTPException(403, "Confirm you are authorized to map this network and building.")
    try:
        kind = classify_router(payload.identifier)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return IdentifierResponse(identifier=payload.identifier, kind=kind, verified=False, ready_to_map=False,
                              message="Identifier format accepted. This does not verify access or reveal building geometry. Import authorized, georeferenced Wi-Fi readings or use the clearly labeled simulation.")


@app.post("/api/demo", response_model=ReconstructionResponse)
def demo(payload: RouterRequest):
    if not payload.authorized:
        raise HTTPException(403, "Authorization confirmation required.")
    try:
        classify_router(payload.identifier)
        return reconstruct(make_demo(payload.identifier))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/reconstruct", response_model=ReconstructionResponse)
def run_reconstruction(payload: ReconstructionRequest):
    try:
        classify_router(payload.router_identifier)
        return reconstruct(payload)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/calibrate", response_model=CalibrationResponse)
def run_calibration(payload: CalibrationRequest):
    try:
        classify_router(payload.identifier)
        return calibrate(payload)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/demo/preview", response_model=ReconstructionResponse)
def preview_demo():
    """Public synthetic-only data. Never interacts with user hardware or real router."""
    return reconstruct(make_demo("SYNTHETIC_DEMO_ONLY"))


@app.get("/api/hardware/capabilities")
def hardware_capabilities():
    """Report *server-side* adapter support; no sensing or scanning performed."""
    return capabilities()


@app.post("/api/hardware/capture", response_model=CapturedReading)
def hardware_capture(payload: CaptureRequest, x_maps_hardware_token: str = Header(default="")):
    """A single opt-in RSSI reading from the already-associated local Wi-Fi link."""
    try:
        classify_router(payload.router_identifier)
        return capture_reading(payload, x_maps_hardware_token)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except SensorError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
