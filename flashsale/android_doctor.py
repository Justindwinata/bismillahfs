"""Read-only diagnostics for a real Android / emulator connection."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlopen

from .core import ROOT


def parse_devices(output):
    devices = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2 and not line.startswith(('List of', '*')):
            devices.append({'serial': fields[0], 'state': fields[1]})
    return devices


def diagnose():
    adb = shutil.which('adb')
    report = {'adb_installed': bool(adb), 'devices': [], 'appium_running': False,
              'sdk_present': False, 'ready_for_inspection': False, 'blockers': []}
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or str(Path.home() / 'Library/Android/sdk')
    report['sdk_present'] = (Path(sdk) / 'platform-tools/adb').exists()
    if adb:
        try:
            result = subprocess.run([adb, 'devices', '-l'], capture_output=True, text=True, timeout=10, check=True)
            report['devices'] = parse_devices(result.stdout)
        except (subprocess.SubprocessError, OSError):
            report['blockers'].append('ADB tidak dapat membaca daftar perangkat.')
    else:
        report['blockers'].append('ADB belum tersedia.')
    available = [d for d in report['devices'] if d['state'] == 'device']
    if not available:
        report['blockers'].append('Belum ada Android/emulator terhubung dan diotorisasi melalui ADB.')
    if any(d['state'] == 'unauthorized' for d in report['devices']):
        report['blockers'].append('Perangkat meminta otorisasi debugging dari pengguna.')
    if not report['sdk_present']:
        report['blockers'].append('Android SDK platform-tools belum ditemukan dalam SDK standar/ANDROID_HOME.')
    try:
        with urlopen('http://127.0.0.1:4723/status', timeout=2) as response:
            status = json.load(response)
        report['appium_running'] = status.get('value', {}).get('ready') is True
    except (OSError, ValueError):
        pass
    if not report['appium_running']:
        report['blockers'].append('Server Appium lokal belum siap pada port 4723.')
    try:
        result = subprocess.run([str(ROOT / '.tools/appium/node_modules/.bin/appium'), 'driver', 'list', '--installed', '--json'],
                                capture_output=True, text=True, timeout=15,
                                env={**os.environ, 'APPIUM_HOME': str(ROOT / '.tools/appium-home')})
        installed = json.loads(result.stdout)
        report['uiautomator2_installed'] = 'uiautomator2' in installed
    except (OSError, ValueError, subprocess.SubprocessError):
        report['uiautomator2_installed'] = False
    if not report['uiautomator2_installed']:
        report['blockers'].append('Driver Appium UiAutomator2 belum tersedia.')
    report['ready_for_inspection'] = bool(available) and not report['blockers']
    return report


if __name__ == '__main__':
    print(json.dumps(diagnose(), indent=2, ensure_ascii=False))
