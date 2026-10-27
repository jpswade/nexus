import unittest
from unittest.mock import patch
from preparedness import cvss_scores, enrich_scores, score_label

class ScoreTests(unittest.TestCase):
    def test_version_and_assessor_preference_not_highest_score(self):
        def metric(score,version,kind):
            return dict(type=kind,source='assessor',cvssData=dict(baseScore=score,version=version))
        raw={'vulnerabilities':[{'cve':{'id':'CVE-2026-1234','metrics':{
            'cvssMetricV40':[metric(10,'4.0','Secondary'),metric(9.2,'4.0','Primary')],
            'cvssMetricV31':[metric(9.8,'3.1','Primary')]}}}]}
        row=cvss_scores(raw)['CVE-2026-1234']
        self.assertEqual(row['score'],9.2)
        self.assertEqual(row['severity'],'CRITICAL')
        self.assertEqual(row['cvss_version'],'4.0')
        raw['vulnerabilities'][0]['cve']['vulnStatus']='Rejected'
        self.assertEqual(cvss_scores(raw),{})

    def test_failed_scoring_retains_last_score_without_hiding_new_advisories(self):
        old={'scores_checked':1,'items':[dict(id='CVE-2026-1234',score=8.1,severity='HIGH',cvss_version='3.1')]}
        result={'items':[{'id':'CVE-2026-1234'},{'id':'CVE-2026-5678'}]}
        with patch('preparedness.urllib.request.urlopen',side_effect=OSError):
            enrich_scores(result,old,100000)
        self.assertEqual(result['items'][0]['score'],8.1)
        self.assertTrue(result['items'][0]['score_cached'])
        self.assertEqual(score_label(result['items'][1]),'CVSS NOT AVAILABLE')

    def test_recent_scores_do_not_refetch(self):
        old={'scores_checked':100000,'items':[dict(id='CVE-2026-1234',score=0,severity='NONE',cvss_version='3.1')]}
        result={'items':[{'id':'CVE-2026-1234'}]}
        with patch('preparedness.urllib.request.urlopen') as fetch:
            enrich_scores(result,old,100001)
            fetch.assert_not_called()
        self.assertEqual(score_label(result['items'][0]),'0.0 NONE / v3.1')
