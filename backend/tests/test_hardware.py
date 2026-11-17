"""Local sensing endpoints, including isolation of demo and authorization gates."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient
from app import app
from hardware import CaptureRequest, LinuxIwSensor, SensorError, capture_reading

client = TestClient(app)


PAYLOAD = {
    'router_identifier': '192.168.1.6', 'authorized': True,
    'interface': 'wlan0', 'expected_ssid': 'TestLab',
    'tx_x': 2, 'tx_y': 3, 'rx_x': 4, 'rx_y': 8,
    'baseline_dbm_at_1m': -40, 'path_loss_exponent': 2.2,
}


class FakeSensor:
    name = 'test_fake'
    def read(self, interface, expected_ssid, expected_bssid=None):
        assert interface == 'wlan0'
        assert expected_ssid == 'TestLab'
        return 'TestLab', -62.5, '00:11:22:33:44:55'


def test_synthetic_preview_does_not_require_authorization_or_connect_router():
    response = client.get('/api/demo/preview')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['source'] == 'simulated'
    assert data['router_identifier'] == 'SYNTHETIC_DEMO_ONLY'
    assert data['measurements'] > 24


def test_capabilities_reveal_limitations_without_probing():
    response = client.get('/api/hardware/capabilities')
    assert response.status_code == 200
    data = response.json()
    assert data['adapters'][1]['id'] == 'csi_plugin'
    assert data['adapters'][1]['ready'] is False
    assert 'backend' in data['scope']


def test_capture_disabled_by_default(monkeypatch):
    monkeypatch.delenv('MAPS_ENABLE_LOCAL_CAPTURE', raising=False)
    monkeypatch.delenv('MAPS_HARDWARE_TOKEN', raising=False)
    response = client.post('/api/hardware/capture', json=PAYLOAD)
    assert response.status_code == 503


def test_permission_required_even_with_token(monkeypatch):
    monkeypatch.setenv('MAPS_ENABLE_LOCAL_CAPTURE', '1')
    monkeypatch.setenv('MAPS_HARDWARE_TOKEN', 'hardwarereadonlytokentest123456789')
    response = client.post('/api/hardware/capture', json={**PAYLOAD, 'authorized': False},
                           headers={'X-MAPS-Hardware-Token': 'hardwarereadonlytokentest123456789'})
    assert response.status_code == 403


def test_secret_required_and_not_accepted_in_payload(monkeypatch):
    monkeypatch.setenv('MAPS_ENABLE_LOCAL_CAPTURE', '1')
    monkeypatch.setenv('MAPS_HARDWARE_TOKEN', 'hardwarereadonlytokentest123456789')
    response = client.post('/api/hardware/capture', json={**PAYLOAD, 'token': 'hardwarereadonlytokentest123456789'})
    assert response.status_code == 403


def test_authorized_sample_with_fake_adapter(monkeypatch):
    monkeypatch.setenv('MAPS_ENABLE_LOCAL_CAPTURE', '1')
    monkeypatch.setenv('MAPS_HARDWARE_TOKEN', 'hardwarereadonlytokentest123456789')
    reading = capture_reading(CaptureRequest(**PAYLOAD), 'hardwarereadonlytokentest123456789', FakeSensor())
    assert reading.measurement.rssi_dbm == -62.5
    assert reading.measurement.rx_y == 8
    assert reading.adapter == 'test_fake'
    assert reading.bssid == '00:11:22:33:44:55'


def test_invalid_interface_rejected_before_shell_invocation():
    response = client.post('/api/hardware/capture', json={**PAYLOAD, 'interface': 'wlan0; echo no'})
    assert response.status_code == 422


def test_read_associated_only_and_verify_expected_ssid():
    mock_output = type('Completed', (), {'stdout': 'Connected to 00:11:22:33:44:55\n\tSSID: TestLab\n\tsignal: -58 dBm\n'})()
    with patch('hardware.sys.platform', 'linux'), patch('hardware.shutil.which', return_value='/usr/bin/iw'), \
         patch('hardware.subprocess.run', return_value=mock_output) as run:
        ssid, signal, bssid = LinuxIwSensor().read('wlan0', 'TestLab')
        assert (ssid, signal, bssid) == ('TestLab', -58, '00:11:22:33:44:55')
        assert run.call_args.args[0] == ['iw', 'dev', 'wlan0', 'link']
        try:
            LinuxIwSensor().read('wlan0', 'OtherSSID')
            assert False, 'Should reject a mismatching connection'
        except SensorError:
            pass


def test_invalid_local_router_address_refused_without_hardware():
    response = client.post('/api/hardware/capture', json={**PAYLOAD, 'router_identifier': '8.8.8.8'})
    assert response.status_code == 422


def test_bssid_pin_prevents_mesh_roaming():
    link = type('Completed', (), {'stdout': 'Connected to aa:bb:cc:dd:ee:ff\n\tSSID: TestLab\n\tsignal: -58 dBm\n'})()
    with patch('hardware.sys.platform', 'linux'), patch('hardware.shutil.which', return_value='/usr/bin/iw'), \
         patch('hardware.subprocess.run', return_value=link):
        assert LinuxIwSensor().read('wlan0', 'TestLab', 'aa:bb:cc:dd:ee:ff')[1] == -58
        try:
            LinuxIwSensor().read('wlan0', 'TestLab', 'aa:bb:cc:dd:ee:00')
            assert False, 'Mismatch should be rejected'
        except SensorError:
            pass


def test_bad_bssid_rejected():
    response = client.post('/api/hardware/capture', json={**PAYLOAD, 'expected_bssid': 'oops'})
    assert response.status_code == 422
