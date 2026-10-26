import unittest
from flashsale.android_doctor import parse_devices


class AndroidDeviceTests(unittest.TestCase):
    def test_distinguishes_authorized_offline_and_unauthorized(self):
        output = 'List of devices attached\nemulator-5554 device product:sdk\nphone123 unauthorized\n127.0.0.1:5555 offline\n'
        self.assertEqual([d['state'] for d in parse_devices(output)], ['device', 'unauthorized', 'offline'])

    def test_empty_adb_result_has_no_device(self):
        self.assertEqual(parse_devices('List of devices attached\n\n'), [])
