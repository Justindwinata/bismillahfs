from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Asia/Jakarta')
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / '.local'


@dataclass
class Job:
    url: str
    starts_at: str
    profile: str
    max_total: str
    adapter: dict

    def validate(self):
        parsed = urlparse(self.url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Gunakan URL produk HTTPS tanpa kredensial.')
        hosts = self.adapter.get('hosts', [])
        if parsed.hostname not in hosts:
            raise ValueError('Hostname produk harus tercantum tepat dalam hosts adapter.')
        if not self.profile or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in self.profile):
            raise ValueError('Nama profil hanya boleh berisi huruf, angka, _ dan -.')
        if not Decimal(self.max_total).is_finite() or Decimal(self.max_total) <= 0:
            raise ValueError('Batas total harus angka positif dalam rupiah.')
        when = datetime.fromisoformat(self.starts_at)
        if when.tzinfo is None:
            raise ValueError('Jadwal harus menyertakan zona waktu.')
        for key in ('ready_selector', 'total_selector', 'submit_selector', 'pending_selector', 'order_id_selector'):
            if not self.adapter.get(key):
                raise ValueError(f'Adapter belum lengkap: {key}.')
        for step in self.adapter.get('steps', []):
            if step.get('action') not in ('click', 'fill', 'select') or not step.get('selector'):
                raise ValueError('Step hanya mendukung click, fill, atau select dengan selector.')
            if step['selector'] == self.adapter['submit_selector']:
                raise ValueError('Tombol pembentukan pesanan hanya boleh di submit_selector.')


def rupiah(value: str) -> Decimal:
    """Parse Indonesian rupiah, rejecting ambiguous/foreign representations."""
    import re
    value = re.sub(r'(?i)rp\.?\s*', '', value).strip().replace('\u00a0', '')
    if not re.fullmatch(r'(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?', value):
        raise ValueError(f'Total tidak dapat dibaca sebagai rupiah: {value!r}')
    return Decimal(value.replace('.', '').replace(',', '.'))


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or DATA / 'orders.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, profile TEXT, url TEXT, state TEXT, order_id TEXT, created TEXT)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, job: Job) -> int:
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT id FROM attempts WHERE profile=? AND url=? AND state IN ('SUBMITTING','UNKNOWN','PENDING_PAYMENT')", (job.profile, job.url)).fetchone()
            if row:
                raise ValueError(f'Percobaan #{row[0]} perlu ditinjau sebelum memesan produk ini lagi.')
            cursor = db.execute('INSERT INTO attempts(profile,url,state,created) VALUES(?,?,?,?)', (job.profile, job.url, 'SUBMITTING', datetime.now(ZONE).isoformat()))
            return cursor.lastrowid

    def finish(self, attempt: int, state: str, order_id: str = ''):
        with self.connect() as db:
            db.execute('UPDATE attempts SET state=?,order_id=? WHERE id=?', (state, order_id, attempt))

    def rows(self):
        with self.connect() as db:
            return db.execute('SELECT id,profile,state,order_id,created FROM attempts ORDER BY id DESC').fetchall()

    def reviewed(self, attempt: int):
        with self.connect() as db:
            db.execute("UPDATE attempts SET state='REVIEWED' WHERE id=?", (attempt,))
