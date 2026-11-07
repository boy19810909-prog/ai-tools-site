import datetime as dt
import json
import unittest
from unittest import mock

from scripts import update_market_close as mc
from scripts import update_official_news as nn

class FakeResponse:
    def __init__(self, data, url=mc.SOURCE):
        self.data=json.dumps(data).encode('utf-8')
        self.url=url
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def geturl(self):return self.url
    def read(self,max_bytes):return self.data[:max_bytes]

class DataIntegrity(unittest.TestCase):
    def test_roc_date(self):
        self.assertEqual(mc.parse_date('1151106'),dt.date(2026,11,6))
        with self.assertRaises(ValueError):mc.parse_date('20261106')

    def test_price_number(self):
        self.assertEqual(mc.nfloat('+1,234.56'),1234.56)

    def test_latest_trading_day_not_today_guess(self):
        payload=[
            {'Date':'1151105','TAIEX':'40,000','Change':'+99','TradeValue':'200000000000'},
            {'Date':'1151106','TAIEX':'39,500','Change':'-500','TradeValue':'300000000000'},
        ]
        with mock.patch.object(mc,'urlopen',return_value=FakeResponse(payload)):
            out=mc.fetch(dt.datetime(2026,11,7,tzinfo=dt.timezone.utc))
        self.assertEqual(out['date'],'2026-11-06')
        self.assertEqual(out['taiex'],39500)
        self.assertEqual(out['change'],-500)

    def test_stale_data_rejected(self):
        payload=[{'Date':'1150807','TAIEX':'43,000','Change':'10','TradeValue':'300000000000'}]
        with mock.patch.object(mc,'urlopen',return_value=FakeResponse(payload)):
            with self.assertRaisesRegex(ValueError,'recent'):mc.fetch(dt.datetime(2026,11,7,tzinfo=dt.timezone.utc))

    def test_untrusted_redirect_rejected(self):
        with mock.patch.object(mc,'urlopen',return_value=FakeResponse([],url='https://example.com/fake')):
            with self.assertRaisesRegex(ValueError,'origin'):mc.fetch(dt.datetime(2026,11,7,tzinfo=dt.timezone.utc))

    def test_rss_link_allowlist(self):
        allowed=getattr(nn, 'allowed', getattr(nn,'allowed_url',None))
        self.assertTrue(allowed('https://www.twse.com.tw/zh/index.html','twse.com.tw'))
        self.assertFalse(allowed('https://twse.com.tw.evil.com/','twse.com.tw'))
        self.assertFalse(allowed('http://twse.com.tw/','twse.com.tw'))

    def test_rss_date(self):
        parse=getattr(nn, 'parse_date', getattr(nn,'date_utc',None))
        self.assertEqual(parse('Fri, 06 Nov 2026 09:59:00 GMT').date(),dt.date(2026,11,6))
        self.assertEqual(parse('2026-11-06T09:59:00Z').date(),dt.date(2026,11,6))

if __name__=='__main__':unittest.main()
