"""Authenticated loopback bridge for the user-selected Shopee Chrome tab."""
import base64
import concurrent.futures
import json
import re
import secrets
import threading
import time
from collections import deque
from urllib.parse import urlparse

from websockets.sync.server import serve


class ChromeBridge:
    def __init__(self, port=8765):
        self.token = secrets.token_urlsafe(32)
        self.port = port
        self.connected = threading.Event()
        self.pending = {}
        self.lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.client = None
        self.client_protocol = 0
        self.metrics = deque(maxlen=200)
        self.server = serve(self.handle, '127.0.0.1', port,
                            origins=[re.compile(r'chrome-extension://[a-p]{32}')],
                            max_size=8 * 1024 * 1024, compression=None)
        self.port = self.server.socket.getsockname()[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def handle(self, socket):
        try:
            hello = json.loads(socket.recv(timeout=5))
            if not secrets.compare_digest(str(hello.get('token', '')), self.token):
                socket.close(1008, 'Invalid pairing code')
                return
            with self.lock:
                if self.client is not None:
                    socket.close(1008, 'Already paired')
                    return
                self.client = socket
                self.client_protocol = hello.get('protocol', 1)
                self.connected.set()
            socket.send(json.dumps({'type': 'paired'}))
            for raw in socket:
                message = json.loads(raw)
                if message.get('type') == 'ping':
                    socket.send('{"type":"pong"}')
                    continue
                with self.lock:
                    future = self.pending.get(message.get('id'))
                if future and not future.done():
                    if message.get('error'):
                        future.set_exception(ValueError(str(message['error'])))
                    elif 'result' in message:
                        future.set_result(message['result'])
                    else:
                        future.set_exception(ValueError('Ekstensi tidak mengembalikan hasil DOM. Periksa kompatibilitas selector atau muat ulang ekstensi.'))
        except Exception:
            pass
        finally:
            with self.lock:
                if self.client is socket:
                    self.client = None
                    self.client_protocol = 0
                    self.connected.clear()
                    futures = list(self.pending.values())
                else:
                    futures = []
            for future in futures:
                if not future.done():
                    future.set_exception(ConnectionError('Ekstensi Chrome terputus.'))

    def request(self, operation, timeout=15, **arguments):
        if not self.connected.is_set():
            raise ConnectionError('Ekstensi Chrome belum terhubung.')
        identity = secrets.token_hex(12)
        future = concurrent.futures.Future()
        started = time.monotonic()
        succeeded = False
        with self.lock:
            self.pending[identity] = future
            client = self.client
        try:
            with self.send_lock:
                if client is None:
                    raise ConnectionError('Koneksi Chrome berakhir sebelum permintaan dikirim.')
                client.send(json.dumps({'id': identity, 'operation': operation,
                                        'expiresAt': int((time.time() + timeout) * 1000), **arguments}))
            result = future.result(timeout=timeout)
            succeeded = True
            return result
        finally:
            self.metrics.append({'operation': operation, 'milliseconds': round((time.monotonic() - started) * 1000, 1), 'ok': succeeded})
            with self.lock:
                self.pending.pop(identity, None)

    def close(self):
        if self.client:
            self.client.close()
        self.server.shutdown()
        self.thread.join(timeout=3)


def matcher(value):
    if isinstance(value, re.Pattern):
        return {'regex': value.pattern, 'flags': 'i' if value.flags & re.I else ''}
    return {'text': str(value)}


class ChromeLocator:
    def __init__(self, page, query):
        self.page, self.query = page, query

    @property
    def first(self):
        return self.nth(0)

    def nth(self, index):
        return ChromeLocator(self.page, {'kind': 'nth', 'base': self.query, 'index': index})

    def locator(self, selector):
        if selector == 'xpath=following-sibling::*[1]':
            return ChromeLocator(self.page, {'kind': 'sibling', 'base': self.query})
        return ChromeLocator(self.page, {'kind': 'child', 'base': self.query, 'css': selector})

    def filter(self, has_text):
        return ChromeLocator(self.page, {'kind': 'filter', 'base': self.query, 'name': matcher(has_text)})

    def action(self, action, **kwargs):
        return self.page.bridge.request('dom', query=self.query, action=action, **kwargs)

    def count(self):
        result = self.action('count')
        if isinstance(result, bool) or not isinstance(result, int) or result < 0:
            raise ValueError('Hasil pembacaan jumlah elemen dari ekstensi tidak valid.')
        return result

    def is_visible(self):
        return self.action('visible')

    def is_enabled(self):
        return self.action('enabled')

    def is_checked(self):
        return self.action('checked')

    def inner_text(self):
        return self.action('text')

    def get_attribute(self, name):
        return self.action('attribute', name=name)

    def click(self, timeout=12000):
        self.wait_for(timeout=timeout)
        return self.action('click')

    def fill(self, value):
        return self.action('fill', value=value)

    def input_value(self):
        if self.page.bridge.client_protocol < 2:
            raise ValueError('Muat ulang ekstensi Flashsale Lokal lalu hubungkan ulang tab. Pembacaan jumlah membutuhkan ekstensi versi 0.2.0.')
        return self.action('value')

    def check(self):
        if not self.is_checked():
            self.click()

    def wait_for(self, state='visible', timeout=15000):
        deadline = time.monotonic() + timeout / 1000
        while time.monotonic() < deadline:
            if self.is_visible():
                return
            time.sleep(.15)
        raise TimeoutError('Elemen Shopee belum terlihat.')


class ChromePage:
    def __init__(self, bridge):
        self.bridge = bridge

    @property
    def url(self):
        return self.bridge.request('info')['url']

    def locator(self, selector):
        return ChromeLocator(self, {'kind': 'css', 'css': selector})

    def get_by_role(self, role, name=None, exact=False):
        return ChromeLocator(self, {'kind': 'role', 'role': role, 'name': matcher(name) if name is not None else None, 'exact': exact})

    def get_by_text(self, name, exact=False):
        return ChromeLocator(self, {'kind': 'text', 'name': matcher(name), 'exact': exact})

    def goto(self, url, **kwargs):
        if self.bridge.client_protocol >= 3:
            info = self.bridge.request('navigate', timeout=50, url=url)
            if not isinstance(info, dict) or urlparse(info.get('url', '')).hostname != 'shopee.co.id' or not info.get('complete'):
                raise ValueError('Tujuan navigasi belum terkonfirmasi sebagai halaman Shopee yang selesai dimuat.')
            return
        self.bridge.request('navigate', url=url)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            info = self.bridge.request('info')
            if info['url'] == url and info.get('complete'):
                return
            # Share links redirect; the final Shopee page is verified by caller.
            if info.get('complete') and urlparse(info['url']).hostname == 'shopee.co.id' and info['url'] != 'about:blank':
                return
            time.sleep(.2)
        raise TimeoutError('Navigasi Shopee belum selesai.')

    def screenshot(self, **kwargs):
        value = self.bridge.request('screenshot', timeout=5)
        return base64.b64decode(value.split(',', 1)[1])

    def bring_to_front(self):
        self.bridge.request('focus')

    def browser_state(self):
        state = self.bridge.request('state', timeout=3)
        if not isinstance(state, dict) or not isinstance(state.get('url'), str) or not isinstance(state.get('challenge'), bool):
            raise ValueError('Status halaman dari ekstensi tidak valid; muat ulang ekstensi dan hubungkan kembali.')
        return state

    def checkout_snapshot(self):
        return self.bridge.request('checkout', timeout=3)

    def promotion_snapshot(self):
        return self.bridge.request('promotion', timeout=5)

    def open_pending_orders(self):
        return self.bridge.request('orders', timeout=50)

    def evaluate(self, source):
        # Only the fixed variant-group reader used by extract_product is exposed.
        return self.bridge.request('groups')
