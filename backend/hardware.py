"""Opt-in, host-local Wi-Fi sensor adapter.

Only reads RSSI for the network to which a Linux interface is *already* associated.
This is deliberately not an IP scanner, network discovery service or CSI sensor.
A remote web deployment cannot read Wi-Fi radios on the visitor's machine:
run the local backend on the machine with the associated wireless interface.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
import re
import secrets
import shutil
import subprocess
import sys
from typing import Protocol

from pydantic import BaseModel, Field, field_validator

from models import Measurement

LINK_BSSID = re.compile(r'^\s*Connected to\s+([0-9a-fA-F:]{17})\b', re.MULTILINE)
LINK_SSID = re.compile(r'^\s*SSID:\s*(.*?)\s*$', re.MULTILINE)
LINK_SIGNAL = re.compile(r'^\s*signal:\s*(-?\d+(?:\.\d+)?)\s*dBm\b', re.MULTILINE)
SAFE_INTERFACE = re.compile(r'^[A-Za-z0-9_.:-]{1,50}$')


class SensorError(Exception):
    """Local sensing could not be completed without inventing data."""


class CaptureRequest(BaseModel):
    router_identifier: str = Field(min_length=1, max_length=253)
    authorized: bool
    interface: str = Field(min_length=1, max_length=50)
    expected_ssid: str = Field(min_length=1, max_length=32)
    expected_bssid: str | None = None
    tx_x: float = Field(ge=0, le=200)
    tx_y: float = Field(ge=0, le=200)
    rx_x: float = Field(ge=0, le=200)
    rx_y: float = Field(ge=0, le=200)
    baseline_dbm_at_1m: float = Field(ge=-100, le=0)
    path_loss_exponent: float = Field(ge=1, le=6)

    @field_validator('expected_bssid')
    @classmethod
    def validate_bssid(cls, value: str | None) -> str | None:
        if value is None or value.strip() == '':
            return None
        if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', value):
            raise ValueError('Expected BSSID must be a six-octet MAC address (aa:bb:cc:dd:ee:ff).')
        return value.lower()

    @field_validator('interface')
    @classmethod
    def validate_interface(cls, value: str) -> str:
        if not SAFE_INTERFACE.fullmatch(value):
            raise ValueError('Interface must be a simple local device name, such as wlan0.')
        return value


class CapturedReading(BaseModel):
    adapter: str
    ssid: str
    bssid: str | None = None
    captured_at: str
    measurement: Measurement
    warnings: list[str]


class WifiSensor(Protocol):
    name: str
    def read(self, interface: str, expected_ssid: str, expected_bssid: str | None = None) -> tuple[str, float, str | None]: ...


class LinuxIwSensor:
    """An associated-link RSSI adapter; no scanning or association performed."""
    name = 'linux_iw_associated_link'

    def read(self, interface: str, expected_ssid: str, expected_bssid: str | None = None) -> tuple[str, float, str | None]:
        if sys.platform != 'linux':
            raise SensorError('Linux iw capture only works on a Linux host.')
        if shutil.which('iw') is None:
            raise SensorError('The iw executable is not installed on the local host.')
        if not SAFE_INTERFACE.fullmatch(interface):
            raise SensorError('Invalid local wireless interface.')
        try:
            result = subprocess.run(
                ['iw', 'dev', interface, 'link'], capture_output=True, text=True,
                check=True, timeout=8,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            raise SensorError('Cannot read the associated Wi-Fi link using iw; confirm the interface is connected.') from exc
        ssid_match = LINK_SSID.search(result.stdout)
        dbm_match = LINK_SIGNAL.search(result.stdout)
        bssid_match = LINK_BSSID.search(result.stdout)
        if ssid_match is None or dbm_match is None:
            raise SensorError('The driver did not report an associated SSID and signal in dBm.')
        ssid = ssid_match.group(1)
        if not secrets.compare_digest(ssid.encode(), expected_ssid.encode()):
            raise SensorError('Connected SSID differs from the authorized expected SSID; capture refused.')
        actual_bssid = bssid_match.group(1).lower() if bssid_match else None
        if expected_bssid and actual_bssid != expected_bssid:
            raise SensorError('Associated AP BSSID does not match the surveyed transmitter.')
        dbm = float(dbm_match.group(1))
        if not -130 <= dbm <= 0:
            raise SensorError('Driver returned RSSI outside the supported dBm range.')
        return ssid, dbm, actual_bssid


def local_capture_enabled() -> bool:
    return os.environ.get('MAPS_ENABLE_LOCAL_CAPTURE') == '1'


def capabilities() -> dict:
    linux = sys.platform == 'linux'
    iw = shutil.which('iw') is not None
    enabled = local_capture_enabled()
    token_configured = len(os.environ.get('MAPS_HARDWARE_TOKEN', '')) >= 20
    operational = linux and iw and enabled and token_configured
    return {
        'scope': 'the computer running the FastAPI backend, not the visitor browser',
        'capture_enabled': enabled,
        'token_configured': token_configured,
        'adapters': [
            {'id': 'linux_iw_associated_link', 'supported': linux and iw,
             'ready': operational, 'measurement': 'RSSI dBm',
             'description': 'Reads the current associated network from a Linux Wi-Fi interface; no scan or router probing.'},
            {'id': 'csi_plugin', 'supported': False, 'ready': False,
             'measurement': 'Channel State Information',
             'description': 'Extension point only. Requires compatible hardware, drivers and a validated plugin.'},
        ],
        'warning': 'A router IP or SSID alone is never enough to identify walls. Surveyed positions and calibrated independent wireless paths are required.',
    }


def capture_reading(payload: CaptureRequest, token: str, adapter: WifiSensor | None = None) -> CapturedReading:
    if not payload.authorized:
        raise PermissionError('Explicit permission is required for measurement collection.')
    if not local_capture_enabled():
        raise SensorError('Hardware capture is disabled. Set MAPS_ENABLE_LOCAL_CAPTURE=1 on the local backend.')
    configured_token = os.environ.get('MAPS_HARDWARE_TOKEN', '')
    if len(configured_token) < 20 or not token or not secrets.compare_digest(token, configured_token):
        raise PermissionError('A valid local capture token is required. It must be configured on the local backend.')
    source = adapter if adapter is not None else LinuxIwSensor()
    ssid, rssi_dbm, bssid = source.read(payload.interface, payload.expected_ssid, payload.expected_bssid)
    return CapturedReading(
        adapter=source.name, ssid=ssid, bssid=bssid,
        captured_at=datetime.now(timezone.utc).isoformat(),
        measurement=Measurement(
            tx_x=payload.tx_x, tx_y=payload.tx_y, rx_x=payload.rx_x, rx_y=payload.rx_y,
            rssi_dbm=rssi_dbm, baseline_dbm_at_1m=payload.baseline_dbm_at_1m,
            path_loss_exponent=payload.path_loss_exponent,
        ),
        warnings=[
            'The access-point position and receiver position were user-supplied, not measured by this adapter.',
            'One link sample is not a floor plan. A single stationary access point has limited tomography observability.',
            'Verify transmitter coordinates against the actual AP BSSID, especially on mesh Wi-Fi networks.',
        ],
    )
