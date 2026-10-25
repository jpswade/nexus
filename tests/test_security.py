import unittest
from security import parse_security, php_priority
from workspaces import WorkspaceCycle, terminal_progress, window_progress


class SecurityTests(unittest.TestCase):
    def advisory(self, **changes):
        row={'ghsa_id':'GHSA-test-test-test','cve_id':'CVE-2026-12345',
             'state':'published','withdrawn_at':None,'summary':'Test advisory',
             'severity':'critical','published_at':'2026-10-21T13:00:00Z',
             'html_url':'https://github.com/php/php-src/security/advisories/example',
             'cvss_severities':{'cvss_v4':{'score':9.2},'cvss_v3':{'score':8.1}},
             'vulnerabilities':[{'patched_versions':'8.3.36'},{'patched_versions':'8.3.36'}, {'patched_versions':'8.4.27'}]}
        row.update(changes)
        return row

    def test_vendor_cvss_version_and_patch_values_are_preserved(self):
        item=parse_security('php',[self.advisory()])['items'][0]
        self.assertEqual((item['score'],item['cvss_version']),(9.2,'4.0'))
        self.assertEqual(item['patches'],['8.3.36','8.4.27'])

    def test_withdrawn_records_and_missing_score(self):
        rows=[self.advisory(withdrawn_at='2026-10-22T00:00:00Z'),
              self.advisory(cvss_severities={},cve_id=None)]
        items=parse_security('php',rows)['items']
        self.assertEqual(len(items),1)
        self.assertIsNone(items[0]['score'])
        self.assertEqual(items[0]['id'],'GHSA-test-test-test')

    def test_priority_does_not_treat_similar_cve_ids_as_kev_matches(self):
        item=parse_security('php',[self.advisory()])['items'][0]
        other=dict(item,id='CVE-2026-55555',severity='medium')
        result=php_priority([item,other],{'CVE-2026-55555'},item['published']+100)
        self.assertEqual(result[0]['id'],other['id'])
        self.assertNotIn(item['id'],{'CVE-2026-123456'})

    def test_official_followup_notice_is_captured_without_full_advisory(self):
        html='''<article class="newsItem"><time datetime="2026-10-23T10:12:28+00:00"></time>
        <h2><a href="https://www.php.net/archive/2026.php#notice">Informational advisory: Session upload progress</a></h2>
        <p>Follow-up for CVE-2026-109619, full advisory for CVE-2026-115560 later.</p></article>'''
        item=parse_security('phpnews',html)['items'][0]
        self.assertEqual(item['cves'],['CVE-2026-109619','CVE-2026-115560'])
        self.assertIn('Session upload',item['title'])
        self.assertNotIn('body',item)
        with self.assertRaises(ValueError):parse_security('phpnews','<html>layout changed</html>')

    def test_catalog_entries_are_sorted_by_addition_not_cve_year(self):
        def row(cve,added):
            return dict(cveID=cve,vendorProject='Test',product='Test',vulnerabilityName='Test',dateAdded=added)
        data=parse_security('kev',{'dateReleased':'2026-10-23T19:30:18Z',
                                 'vulnerabilities':[row('CVE-2026-33333','2026-10-20'),row('CVE-2012-1234','2026-10-23')]})
        self.assertEqual(data['items'][0]['id'],'CVE-2012-1234')
        self.assertEqual(data['items'][0]['ransomware'],'Unknown')


class WorkspaceTests(unittest.TestCase):
    def test_auto_cycle_has_no_drift_and_wraps(self):
        cycle=WorkspaceCycle(32)
        self.assertEqual(cycle.tick(33),(1,1))
        self.assertEqual(cycle.tick(129),(0,1))

    def test_manual_selection_gets_a_full_interval(self):
        cycle=WorkspaceCycle(32)
        cycle.select(2,20)
        self.assertEqual(cycle.tick(51),(2,31))
        self.assertEqual(cycle.tick(52),(3,0))
        cycle.automatic=False
        self.assertEqual(cycle.tick(500)[0],3)

    def test_popup_opens_then_closes(self):
        self.assertEqual(terminal_progress(6),0)
        self.assertGreater(terminal_progress(7.2),0)
        self.assertEqual(terminal_progress(12),1)
        self.assertLess(terminal_progress(22.8),1)
        self.assertEqual(terminal_progress(23),0)
        self.assertEqual(window_progress(0,.2),0)


if __name__=='__main__':unittest.main()
