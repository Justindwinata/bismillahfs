import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from flashsale.core import Job, Store, rupiah


class CoreTests(unittest.TestCase):
    def job(self):
        return Job('https://shop.example/product', '2026-12-01T12:00:00+07:00', 'utama', '100000', {
            'hosts': ['shop.example'], 'ready_selector': '#ready', 'total_selector': '#total',
            'submit_selector': '#submit', 'pending_selector': '#pending', 'order_id_selector': '#id'})

    def test_currency(self):
        self.assertEqual(rupiah('Rp100.000,50'), Decimal('100000.50'))
        for value in ('Rp -100', 'Rp 1,000.00', 'gratis', 'NaN', 'Rp10 Rp20'):
            with self.assertRaises(ValueError):
                rupiah(value)

    def test_validation(self):
        job = self.job()
        job.validate()
        job.url = 'https://shop.example.attacker.test/product'
        with self.assertRaises(ValueError):
            job.validate()
        job = self.job()
        job.profile = '../escape'
        with self.assertRaises(ValueError):
            job.validate()

    def test_duplicate_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.sqlite'
            store = Store(path)
            attempt = store.reserve(self.job())
            for state in ('SUBMITTING', 'UNKNOWN', 'PENDING_PAYMENT'):
                store.finish(attempt, state)
                with self.assertRaises(ValueError):
                    Store(path).reserve(self.job())
            store.reviewed(attempt)
            self.assertGreater(store.reserve(self.job()), attempt)


if __name__ == '__main__':
    unittest.main()
