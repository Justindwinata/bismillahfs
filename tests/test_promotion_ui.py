import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtWidgets import QApplication
from flashsale.app import Window

class PromotionUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def test_confirmed_candidate_is_reflected_in_dashboard_choice(self):
        window=Window(auto_open=False)
        data={'url':'https://shopee.co.id/product/1/2','name':'Redmi','groups':[{'name':'Paket','options':[{'label':'Unit','disabled':False},{'label':'Bundel','disabled':False}]}]}
        window.product_changed(data)
        window.promotion_changed({'product_url':data['url'],'candidate':{'choices':['Bundel'],'offers':[{'price':'950000'}]}})
        window.product_changed(data)
        self.assertEqual(window.variant_fields[0].currentData(),'Bundel')
        window.close()

    def test_release_mode_accepts_disabled_target_without_preview_click(self):
        from unittest.mock import MagicMock
        window=Window(auto_open=False)
        window.stock_release.setChecked(True)
        window.send=MagicMock()
        window.product_changed({'url':'https://shopee.co.id/product/1/2','name':'Phone','groups':[{'name':'Model','options':[{'label':'Promo','disabled':True}]}]})
        choice=window.variant_fields[0]
        self.assertTrue(choice.model().item(1).isEnabled())
        choice.setCurrentIndex(1)
        self.assertEqual(choice.currentData(),'Promo')
        window.send.assert_not_called()
        window.close()
