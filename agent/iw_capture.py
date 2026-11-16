#!/usr/bin/env python3
"""Authorized Linux survey capture using driver-reported RSSI dBm (`iw`).

Captures an *already-associated* Wi-Fi interface at a manually surveyed receiver
position. Does not scan, join, or probe networks. Requires `iw` installed, a Linux
wireless interface and a driver exposing dBm link signal.

Example: python agent/iw_capture.py --interface wlan0 --ssid MyWifi \\
  --tx-x 2 --tx-y 2 --rx-x 7 --rx-y 5 --baseline-dbm-at-1m -39 \\
  --path-loss-exponent 2.3 --output readings.csv
"""
from __future__ import annotations
import argparse
import csv
import re
import subprocess
from pathlib import Path

COLUMNS = ['tx_x','tx_y','rx_x','rx_y','rssi_dbm','baseline_dbm_at_1m','path_loss_exponent']


def extract_link(text: str) -> tuple[str, float]:
    ssid = re.search(r'^\s*SSID:\s*(.*?)\s*$', text, re.MULTILINE)
    dbm = re.search(r'^\s*signal:\s*(-?\d+(?:\.\d+)?)\s*dBm\b', text, re.MULTILINE)
    if not ssid or not dbm:
        raise ValueError('No supported associated network or RSSI dBm signal reported by iw.')
    signal = float(dbm.group(1))
    if not -130 <= signal <= 0:
        raise ValueError('Invalid RSSI dBm reading.')
    return ssid.group(1), signal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--interface',required=True,help='Linux Wi-Fi interface, e.g. wlan0')
    p.add_argument('--ssid',required=True,help='Expected currently associated SSID')
    for field in ('tx-x','tx-y','rx-x','rx-y'):
        p.add_argument('--'+field,required=True,type=float)
    p.add_argument('--baseline-dbm-at-1m',type=float,required=True,help='Calibrated reference RSSI at 1 meter (dBm)')
    p.add_argument('--path-loss-exponent',type=float,required=True,help='Measured/calibrated propagation exponent')
    p.add_argument('--output',default='readings.csv')
    args=p.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,50}',args.interface):
        p.error('Invalid interface name')
    if not all(0 <= value <= 200 for value in (args.tx_x,args.tx_y,args.rx_x,args.rx_y)):
        p.error('Survey coordinates must be in [0,200] meters')
    if not (-100<=args.baseline_dbm_at_1m<=0 and 1<=args.path_loss_exponent<=6):
        p.error('Invalid calibration parameters')
    if input('Are you authorized to survey this building and network? Type YES: ').strip()!='YES':
        raise SystemExit('Survey not authorized; no collection performed.')
    try:
        link=subprocess.run(['iw','dev',args.interface,'link'],text=True,capture_output=True,check=True,timeout=10)
    except (FileNotFoundError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        raise SystemExit(f'Could not read associated Wi-Fi signal: {exc}') from exc
    try:
        ssid,dbm=extract_link(link.stdout)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if ssid!=args.ssid:
        raise SystemExit(f'Connected SSID mismatch (expected {args.ssid!r}, got {ssid!r}); nothing saved.')
    record={'tx_x':args.tx_x,'tx_y':args.tx_y,'rx_x':args.rx_x,'rx_y':args.rx_y,
            'rssi_dbm':dbm,'baseline_dbm_at_1m':args.baseline_dbm_at_1m,
            'path_loss_exponent':args.path_loss_exponent}
    outfile=Path(args.output)
    append=outfile.exists() and outfile.stat().st_size>0
    with outfile.open('a',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=COLUMNS)
        if not append:writer.writeheader()
        writer.writerow(record)
    print(f'Saved verified driver-reported {dbm} dBm measurement on {ssid!r} to {outfile}.')
    print('A single AP / one receiver location cannot reconstruct a building; repeat with calibrated multiple transmitters and positions.')


if __name__=='__main__':main()
