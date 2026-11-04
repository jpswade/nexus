"""Shared header-source metadata and cached history presentation."""
from source_history import detail
from preparedness import LINKS, MAX_AGES
from grid_notices import URL as GRID_URL, MAX_AGE as GRID_AGE
from emergency_alerts import MAX_AGE as GOV_AGE

HEADERS = ('gov', 'grid', 'weather', 'floods')
META = {
    'gov': ('GOV.UK ALERTS', 'https://www.gov.uk/alerts', GOV_AGE,
            'Published web alerts; not a live cell-broadcast receiver.'),
    'grid': ('GRID NOTICES', GRID_URL, GRID_AGE,
             'GB system bulletins; active status and local outages unconfirmed.'),
    'weather': ('MET OFFICE', LINKS['weather'], MAX_AGES['weather'],
                'Regional warning feed; no returned items is not an all-clear.'),
    'floods': ('ENVIRONMENT AGENCY', LINKS['floods'], MAX_AGES['floods'],
               'Configured England flood area; not complete UK flood coverage.'),
}


def describe(source, records, data, emergency, now):
    name, url, max_age, caveat = META[source]
    sample = emergency if source == 'gov' else data.get(source)
    record = records.get(source, {})
    state, attempted, successful = detail(record, sample, now, max_age)
    return name, url, caveat, state, attempted, successful, record.get('events', [])
