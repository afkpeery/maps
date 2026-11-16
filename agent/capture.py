#!/usr/bin/env python3
"""Opt-in, local, manual-coordinate RSSI collection for Linux NetworkManager.

Usage:
 python agent/capture.py --ssid YourNetwork --tx-x 2 --tx-y 2 --rx-x 5 --rx-y 3 --output readings.csv

IMPORTANT: nmcli signal percentage is NOT calibrated RSSI dBm. This agent only
records adapter signal percentage and never silently converts it into dBm.
Use a device/driver exposing calibrated RSSI to produce valid reconstruction input.
"""
import argparse
import csv
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssid', required=True)
    parser.add_argument('--tx-x', type=float, required=True)
    parser.add_argument('--tx-y', type=float, required=True)
    parser.add_argument('--rx-x', type=float, required=True)
    parser.add_argument('--rx-y', type=float, required=True)
    parser.add_argument('--output', default='signal-survey.csv')
    args = parser.parse_args()
    confirmation = input('Confirm you own or are authorized to survey this local network and building [yes/no]: ')
    if confirmation.lower().strip() != 'yes':
        raise SystemExit('Survey cancelled: authorization not confirmed.')
    proc = subprocess.run(['nmcli','-t','-f','IN-USE,SSID,SIGNAL','dev','wifi','list', '--rescan', 'no'],
                          capture_output=True,text=True,check=True,timeout=15)
    networks=[]
    for row in proc.stdout.splitlines():
        fields=row.split(':')
        if len(fields)<3: continue
        signal=fields[-1]
        ssid=':'.join(fields[1:-1])
        if ssid==args.ssid:
            networks.append({'ssid':ssid,'signal_percent':signal,'tx_x':args.tx_x,'tx_y':args.tx_y,'rx_x':args.rx_x,'rx_y':args.rx_y})
    if not networks:
        raise SystemExit('SSID not present in locally cached NetworkManager scan.')
    path=Path(args.output)
    append=path.exists()
    with path.open('a',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(networks[0]))
        if not append: writer.writeheader()
        writer.writerows(networks)
    print(f'Saved {len(networks)} signal percentage record(s) to {path}.')
    print('This is diagnostic-only. Percent signal IS NOT RSSI in dBm; do not import as calibrated measurements.')


if __name__=='__main__':main()
