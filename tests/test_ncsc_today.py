import datetime as dt
import unittest
from preparedness import display_items, parse_feed

class NCSCTodayTests(unittest.TestCase):
    def test_uk_day_boundary_missing_and_future_dates(self):
        now=dt.datetime(2026,7,2,0,30,tzinfo=dt.timezone.utc).timestamp()
        rows=[{'published':now-3600},{'published':now-7200},{'published':None},{'published':now+60}]
        sample={'items':rows,'item_dates':True}
        self.assertEqual(display_items('ncsc',sample,now),rows[:1])
        self.assertEqual(display_items('ncsc',sample,now+86400),[])
        self.assertEqual(display_items('news',sample,now),rows)
        self.assertEqual(display_items('ncsc',{'items':rows},now),[])

    def test_feed_build_date_is_not_article_publication_date(self):
        sample=parse_feed('ncsc','<rss><channel><pubDate>Mon, 26 Oct 2026 10:00:00 GMT</pubDate><item><title>Undated</title></item></channel></rss>')
        self.assertIsNone(sample['items'][0]['published'])
        self.assertTrue(sample['item_dates'])
