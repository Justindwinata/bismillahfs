"""Inspect an explicitly selected real Android device, without ordering."""
import argparse
import json

from appium import webdriver
from appium.options.android import UiAutomator2Options

from .android_doctor import diagnose


def inspect_device(serial):
    report = diagnose()
    if not any(d['serial'] == serial and d['state'] == 'device' for d in report['devices']):
        raise ValueError('Perangkat yang dipilih belum terhubung/diotorisasi melalui ADB.')
    if not report['ready_for_inspection']:
        raise ValueError('Prasyarat Android belum lengkap: ' + ' '.join(report['blockers']))
    options = UiAutomator2Options().load_capabilities({
        'platformName': 'Android', 'appium:automationName': 'UiAutomator2',
        'appium:udid': serial, 'appium:deviceName': serial,
        'appium:noReset': True, 'appium:fullReset': False,
        'appium:autoLaunch': False, 'appium:newCommandTimeout': 60,
        'appium:dontStopAppOnReset': True,
    })
    driver = webdriver.Remote('http://127.0.0.1:4723', options=options)
    try:
        # Do not print page text, credentials, or complete UI hierarchy.
        return {'connected': True, 'current_package': driver.current_package,
                'window': driver.get_window_size(), 'ui_source_available': bool(driver.page_source)}
    finally:
        driver.quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Periksa satu perangkat Android nyata tanpa membuat pesanan.')
    parser.add_argument('--device', required=True)
    args = parser.parse_args()
    print(json.dumps(inspect_device(args.device), indent=2))
