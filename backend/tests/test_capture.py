import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]/'agent'))
from iw_capture import extract_link


def test_iw_link_rssi_parser():
    example='Connected to aa:bb:cc:dd:ee:ff (on wlan0)\n\tSSID: TestNetwork\n\tfreq: 5180\n\tsignal: -55 dBm\n'
    assert extract_link(example) == ('TestNetwork', -55.)


def test_iw_link_disconnected():
    try:
        extract_link('Not connected.\n')
        assert False
    except ValueError:
        pass
