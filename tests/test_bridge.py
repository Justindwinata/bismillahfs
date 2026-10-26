import json
import threading
import unittest

from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed

from flashsale.bridge import ChromeBridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = ChromeBridge(port=0)
        self.url = f'ws://127.0.0.1:{self.bridge.port}'
        self.origin = 'chrome-extension://' + 'a' * 32

    def tearDown(self):
        self.bridge.close()

    def test_wrong_pairing_code_rejected(self):
        with connect(self.url, origin=self.origin) as client:
            client.send(json.dumps({'token': 'wrong-code'}))
            with self.assertRaises(ConnectionClosed):
                client.recv(timeout=2)
        self.assertFalse(self.bridge.connected.is_set())

    def test_authenticated_request_and_response(self):
        failures = []

        def extension():
            try:
                with connect(self.url, origin=self.origin) as client:
                    client.send(json.dumps({'token': self.bridge.token}))
                    self.assertEqual(json.loads(client.recv())['type'], 'paired')
                    request = json.loads(client.recv(timeout=3))
                    self.assertEqual(request['operation'], 'info')
                    client.send(json.dumps({'id': request['id'], 'result': {'url': 'https://shopee.co.id/'}}))
            except Exception as exc:
                failures.append(exc)

        thread = threading.Thread(target=extension)
        thread.start()
        self.assertTrue(self.bridge.connected.wait(3))
        result = self.bridge.request('info', timeout=3)
        self.assertEqual(result['url'], 'https://shopee.co.id/')
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertFalse(failures)

    def test_no_client_fails_without_sending(self):
        with self.assertRaises(ConnectionError):
            self.bridge.request('info')
