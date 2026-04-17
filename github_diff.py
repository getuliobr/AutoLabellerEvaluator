"""Shared GitHub PR diff fetcher with adaptive rate-limit throttle.

Used by generateGPTCode.py and qp3.py. Wraps the authenticated REST API
(/repos/{repo}/pulls/{number} with Accept: application/vnd.github.diff) and
caches results in MongoDB collection {repo}_diff.

Throttle strategy:
  - Enforce >=0.8s between requests (~4500/hr ceiling under the 5000/hr limit).
  - Track x-ratelimit-remaining/reset; if remaining drops below _LOW_WATER,
    sleep until the reset window.
  - On 403/429 with remaining=0, sleep until reset and retry once.
"""

import json
import time

import requests

from config import config


GITHUB_TOKEN = config['GITHUB']['TOKEN']
_HEADERS = {
    'Accept': 'application/vnd.github.diff',
    'Authorization': f'Bearer {GITHUB_TOKEN}',
    'X-GitHub-Api-Version': '2022-11-28',
}

_MIN_INTERVAL = 0.8
_LOW_WATER = 50
_MAX_CACHE_BYTES = 15_000_000

_last_request_ts = 0.0
_remaining = None
_reset_ts = None


def _sleep_for_throttle():
    """Block until it is safe to issue the next request."""
    global _last_request_ts

    now_wall = time.time()
    if _remaining is not None and _reset_ts is not None \
            and _remaining < _LOW_WATER and _reset_ts > now_wall:
        wait = (_reset_ts - now_wall) + 1
        print(f'  [github_diff] rate-limit low ({_remaining} left); sleeping {wait:.0f}s until reset')
        time.sleep(wait)

    elapsed = time.monotonic() - _last_request_ts
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)


def _update_rate_state(response):
    global _remaining, _reset_ts
    rem = response.headers.get('x-ratelimit-remaining')
    rst = response.headers.get('x-ratelimit-reset')
    if rem is not None:
        try:
            _remaining = int(rem)
        except ValueError:
            pass
    if rst is not None:
        try:
            _reset_ts = int(rst)
        except ValueError:
            pass


def _fetch_pr_diff(repo, pr_number, _retry=False):
    """GET one PR's diff. Returns (text, reason). reason is None on success."""
    global _last_request_ts

    _sleep_for_throttle()
    url = f'https://api.github.com/repos/{repo}/pulls/{pr_number}'
    response = requests.get(url, headers=_HEADERS)
    _last_request_ts = time.monotonic()
    _update_rate_state(response)

    if response.status_code == 200:
        return response.text, None

    if response.status_code in (403, 429) and not _retry:
        if _remaining == 0 and _reset_ts is not None:
            wait = max(0, _reset_ts - time.time()) + 1
            print(f'  [github_diff] hit rate limit on {repo}#{pr_number}; sleeping {wait:.0f}s')
            time.sleep(wait)
            return _fetch_pr_diff(repo, pr_number, _retry=True)

    if response.status_code == 404:
        reason = '404 (PR missing/transferred)'
    elif response.status_code == 406:
        reason = '406 (diff too large)'
    else:
        reason = f'HTTP {response.status_code}: {response.text[:200]}'
    print(f'  [github_diff] {repo}#{pr_number}: {reason}')
    return '', reason


def get_diff(repo, number, db):
    """Return (diff_list, errors).

    diff_list: one unified-diff string per PR linked to the issue. Failed PRs
        appear as empty strings so cache shape stays stable.
    errors: list of (pr_number, reason) for PRs that couldn't be fetched. Empty
        list on full success. For pre-schema cached docs without an 'errors'
        field, any empty diff entries are surfaced as ('?', 'cached empty diff').
    """
    diffCollection = db[f'{repo}_diff']
    issueCollection = db[repo]

    cached = diffCollection.find_one({'number': number})
    if cached:
        diff = cached['diff']
        errors = list(cached.get('errors', []))
        if not errors and any(not d for d in diff):
            errors = [('?', 'cached empty diff')]
        return diff, errors

    issue = issueCollection.find_one({'number': number})
    if not issue:
        return [], [(number, 'issue not in database')]

    diff = []
    errors = []
    for pr in issue['prs']:
        text, reason = _fetch_pr_diff(repo, pr)
        diff.append(text)
        if reason:
            errors.append((pr, reason))

    doc = {'number': number, 'diff': diff, 'errors': errors}
    doc_size = len(json.dumps(doc, default=str).encode('utf-8'))
    if doc_size > _MAX_CACHE_BYTES:
        print(f'  [github_diff] {repo}#{number} ~{doc_size/1e6:.1f}MB; skipping MongoDB cache.')
    else:
        diffCollection.insert_one(doc)
    return diff, errors
