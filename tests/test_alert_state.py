import unittest
from alert_state import AlertState, weather_window


def weather(items, fetched=100):
    return {'weather':dict(items=items,fetched=fetched)}


def warning(title='Amber warning of wind', **extra):
    return dict(title=title,colour='amber',url='https://example.org/warning',**extra)


class AlertTests(unittest.TestCase):
    def test_new_warning_stays_after_announcement_and_clears_on_verified_empty(self):
        state=AlertState()
        self.assertEqual(state.update(weather([]),(),100),[])
        row=state.update(weather([warning()],101),(),101)[0]
        self.assertTrue(row['new'])
        self.assertFalse(state.update(weather([warning()],200),(),200)[0]['new'])
        self.assertEqual(state.update(weather([],201),(),201),[])

    def test_failure_or_missing_data_never_clears_warning(self):
        state=AlertState()
        state.update(weather([warning()]),(),100)
        self.assertTrue(state.update(weather([],101),{'weather'},101)[0]['stale'])
        self.assertTrue(state.update({},(),200)[0]['stale'])
        self.assertEqual(state.update(weather([],202),(),202),[])

    def test_cache_startup_is_not_a_new_event_and_escalation_is(self):
        state=AlertState()
        self.assertFalse(state.update(weather([warning()]),(),100)[0]['new'])
        raised=warning();raised['colour']='red'
        self.assertTrue(state.update(weather([raised],101),(),101)[0]['new'])

    def test_validity_upcoming_active_expired_and_year_rollover(self):
        row=warning(description='valid from 2300 Thu 31 Dec to 0200 Fri 01 Jan')
        row['url']='https://www.metoffice.gov.uk/weather#?date=2026-12-31&id=test'
        start,end=weather_window(row)
        self.assertEqual(end-start,10800)
        state=AlertState()
        self.assertTrue(state.update(weather([row],start-60),(),start-60)[0]['detail'].startswith('UPCOMING'))
        self.assertTrue(state.update(weather([row],start),(),start)[0]['detail'].startswith('IN FORCE'))
        self.assertEqual(state.update(weather([row],end),(),end),[])

    def test_unknown_validity_is_explicit_and_news_never_alerts(self):
        state=AlertState()
        self.assertIn('CHECK VALIDITY',state.update(weather([warning()]),(),100)[0]['detail'])
        self.assertEqual(AlertState().update({'news':{'fetched':100,'items':[warning()]}},(),100),[])
