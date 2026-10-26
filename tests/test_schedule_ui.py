import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
from datetime import datetime
from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QApplication

from flashsale.app import Window
from flashsale.core import ZONE


class ScheduleUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = Window(auto_open=False)
        self.window.product_data = {'url': 'https://shopee.co.id/product/1/2', 'groups': []}
        self.window.payment.setCurrentText('QRIS')
        self.window.purchase_section.setEnabled(True)
        self.sent = []
        self.window.send = lambda command, value=None: self.sent.append((command, value))

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_expired_schedule_explicitly_rejected(self):
        self.window.schedule.setDateTime(QDateTime.currentDateTime().addSecs(-120))
        self.window.start_job()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.window.state.text(), 'PERIKSA JADWAL')
        self.assertIn('Jalankan sekarang', self.window.message.text())

    def test_run_now_ignores_unused_expired_schedule_and_dispatches_once(self):
        self.window.schedule.setDateTime(QDateTime.currentDateTime().addSecs(-120))
        self.window.execution.setCurrentIndex(1)
        self.window.start_job()
        self.window.start_job()
        self.assertEqual(len(self.sent), 1)
        command, config = self.sent[0]
        self.assertEqual(command, 'schedule')
        self.assertTrue(config['immediate'])
        self.assertLess(abs((datetime.fromisoformat(config['time']) - datetime.now(ZONE)).total_seconds()), 2)
        self.assertEqual(self.window.state.text(), 'MENGIRIM TUGAS')

    def test_future_schedule_preserves_selected_time(self):
        self.window.schedule.setDateTime(QDateTime.currentDateTime().addSecs(600))
        expected = self.window.schedule.dateTime().toSecsSinceEpoch()
        self.window.start_job()
        config = self.sent[0][1]
        self.assertFalse(config['immediate'])
        self.assertEqual(int(datetime.fromisoformat(config['time']).timestamp()), expected)
