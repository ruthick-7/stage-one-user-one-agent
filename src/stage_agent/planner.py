"""One conservative intervention: a fresh-session home page, no unsolicited messaging."""
from .facts import value
from .common import ts


def plan_page(pack, state, goal, at):
    dialect = value(state, 'dialect')
    seen, titles = set(), []
    # Goal context first, then recent releases; no claim these are 'popular'.
    target = (goal.get('context') or {}).get('content_slug')
    candidates = sorted(pack.catalogue.values(), key=lambda t:
                        (t['content_slug'] != target, -ts(t['release_date'] + 'T00:00:00Z').timestamp(), t['title_id']))
    for t in candidates:
        if not pack.available(t['title_id'], at, dialect) or t['content_slug'] in seen:
            continue
        if value(state, 'subscription_status') not in ('active', 'trial_active') and t['is_premium'] == 'true':
            continue
        seen.add(t['content_slug'])
        titles.append(t['title_id'])
        if len(titles) == 21:
            break
    if len(titles) < 4:
        return None
    rows = []
    for offset in range(1, len(titles), 10):
        group = titles[offset:offset + 10]
        if len(group) >= 3:
            rows.append({'row_type': 'genre', 'title_ids': group})
    return {'type': 'home_page', 'dialect': dialect, 'hero_title_id': titles[0], 'rows': rows,
            'ttl_minutes': pack.interventions['home_page']['ttl_minutes']}
