import copy
import unittest
from flashsale.promotions import matching_offers

class PublishedPromotionTests(unittest.TestCase):
    def setUp(self):
        self.target='2026-10-26T12:00:00+07:00'
        self.snapshot={'url':'https://shopee.co.id/product/1/2','title':'Redmi',
            'evidence':['Flash Sale Mulai 12:00','Rp999.000'],
            'published':[{'parent_name':'Redmi','parent_url':'https://shopee.co.id/product/1/2',
                'sku':'phone64black','labels':['4/64GB','Hitam','Unit Saja'],'name':'Flash Sale 12.00',
                'description':'','price':'950000','currency':'IDR','valid_from':self.target,'availability':'https://schema.org/InStock'}]}
        self.choices=['4/64GB','Hitam','Unit Saja']
    def test_explicit_bound_offer_matches_price_time_and_choices(self):
        self.assertEqual(matching_offers(self.snapshot,self.choices,self.target,1000000)[0]['sku'],'phone64black')
    def test_banner_without_sku_offer_does_not_confirm(self):
        self.snapshot['published']=[]
        self.assertEqual(matching_offers(self.snapshot,self.choices,self.target,1000000),[])
    def test_cheap_accessory_is_not_the_phone_promotion(self):
        self.snapshot['published'][0].update(labels=['Charger'],price='10000')
        self.assertEqual(matching_offers(self.snapshot,self.choices,self.target,1000000),[])
    def test_wrong_day_currency_price_availability_and_unbound_parent_rejected(self):
        for changes in ({'valid_from':'2026-10-27T12:00:00+07:00'},{'valid_from':'2026-10-26T12:00:00'},
                        {'currency':'USD'},{'price':'1000001'},{'price':'NaN'},{'availability':'https://schema.org/OutOfStock'},
                        {'parent_url':'https://shopee.co.id/product/99/88'},{'name':'Harga normal'}, {'sku':''}):
            with self.subTest(changes=changes):
                candidate=copy.deepcopy(self.snapshot);candidate['published'][0].update(changes)
                self.assertEqual(matching_offers(candidate,self.choices,self.target,1000000),[])

class ScanSummaryTests(unittest.TestCase):
    def test_announcement_does_not_become_confirmed_sku(self):
        from flashsale.promotions import scan_summary
        result=scan_summary([{'available':True,'evidence':['Mulai pada 12:00, 26 Okt']},
                             {'available':False}])
        self.assertEqual(result['available_combinations'],1)
        self.assertEqual(result['unavailable_combinations'],1)
        self.assertEqual(result['announcements'],['Mulai pada 12:00, 26 Okt'])
        self.assertIn('Jadwal promo terdeteksi',result['reason'])
        self.assertNotIn('candidate',result)

class ScheduleConflictTests(unittest.TestCase):
    def test_wrong_day_is_reported(self):
        from flashsale.promotions import schedule_conflicts
        line='Mulai pada 12:00, 26 Okt'
        self.assertEqual(schedule_conflicts([line],'2026-10-29T12:00:00+07:00'),[line])
        self.assertEqual(schedule_conflicts([line],'2026-10-26T12:00:00+07:00'),[])
    def test_time_and_timezone_are_compared(self):
        from flashsale.promotions import schedule_conflicts
        line='Mulai pada 12:00, 26 Okt'
        self.assertEqual(schedule_conflicts([line],'2026-10-26T05:00:00+00:00'),[])
        self.assertEqual(schedule_conflicts([line],'2026-10-26T13:00:00+07:00'),[line])

class CatalogEvidenceTests(unittest.TestCase):
    def test_catalog_does_not_confuse_model_presence_with_campaign_membership(self):
        from flashsale.promotions import catalog_summary
        result=catalog_summary({'models':[{'model_id':'123','promotion_id':None}],
                                'preview':{'promotion_id':'456'}})
        self.assertEqual(result['model_count'],1)
        self.assertEqual(result['linked_model_ids'],[])
        result=catalog_summary({'models':[{'model_id':'123','promotion_id':456}],
                                'preview':{'promotion_id':'456'}})
        self.assertEqual(result['linked_model_ids'],['123'])
