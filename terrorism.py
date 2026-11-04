"""Conservative official UK assessment parsing and compact provenance labels."""
import datetime as dt
from html.parser import HTMLParser
import re

GOV_URL = 'https://www.gov.uk/terrorism-national-emergency'
MI5_URL = 'https://www.mi5.gov.uk/threats-and-advice/terrorism-threat-levels'
LEVELS = ('low', 'moderate', 'substantial', 'severe', 'critical')


class AssessmentHTML(HTMLParser):
    """Keep headings/paragraph boundaries; never accept script or style text."""
    def __init__(self):
        super().__init__()
        self.blocks, self.text, self.tag, self.hidden = [], [], None, 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if not self.hidden and tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.tag, self.text = tag, []

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden-1)
        if tag == self.tag:
            self.blocks.append((tag, ' '.join(''.join(self.text).split())))
            self.tag, self.text = None, []

    def handle_data(self, value):
        if self.tag and not self.hidden:
            self.text.append(value)


def parse_assessment(body, mi5=False):
    parser = AssessmentHTML()
    parser.feed(body)
    blocks = parser.blocks
    if mi5:
        headings = [i for i, (tag, text) in enumerate(blocks)
                    if tag.startswith('h') and text.lower() == 'current national threat level']
        if len(headings) != 1:
            raise ValueError('Missing or ambiguous current national heading')
        start = headings[0]+1
        end = next((i for i in range(start, len(blocks)) if blocks[i][0].startswith('h')), len(blocks))
        blocks = blocks[start:end]
    prefix = r'The threat to the UK\s*\(England, Wales, Scotland and Northern Ireland\)\s*from '
    prefix += 'all forms of terrorism is' if mi5 else 'terrorism is'
    candidates = [text for tag, text in blocks if tag == 'p' and re.match(prefix, text, re.I)]
    # Even duplicate statements are ambiguous: do not choose the first match.
    if len(candidates) != 1:
        raise ValueError('Missing or ambiguous national assessment')
    match = re.fullmatch(prefix+r'\s+('+'|'.join(LEVELS)+r')\s*\.\s*\*?', candidates[0], re.I)
    if not match:
        raise ValueError('National assessment wording changed; do not guess')
    return match.group(1).upper()


def threat_details(sample, now, failed=False):
    """Two short persistent lines; checked means last successful source read."""
    if not sample:
        return 'Official source unavailable', 'No successful check'
    name = sample.get('source_name', 'GOV.UK')
    if sample.get('disagreement'):
        values = sample['observations']
        source = f"GOV.UK {values['GOV.UK']['level']} / MI5 {values['MI5']['level']}"
    else:
        source = name + (' / fallback' if name == 'MI5' else '') + ' / Crown copyright'
    stale = failed or now-sample['fetched'] > 7200
    stamp = dt.datetime.fromtimestamp(sample['fetched'], dt.timezone.utc).strftime('%d %b %H:%M UTC')
    return source, ('STALE / last OK ' if stale else 'Checked ')+stamp
