"""Build catalogue-backed genre rows with a goal-relevant hero."""
from collections import Counter
from .facts import value
from .common import ts


def plan_page(pack, state, goal, at):
    dialect = value(state, 'dialect')
    if not dialect:
        return None
    target = (goal.get('context') or {}).get('content_slug')
    candidates = sorted(pack.catalogue.values(), key=lambda title:
                        (title['content_slug'] != target,
                         -ts(title['release_date'] + 'T00:00:00Z').timestamp(), title['title_id']))
    seen, valid = set(), []
    for title in candidates:
        if not pack.available(title['title_id'], at, dialect) or title['content_slug'] in seen:
            continue
        if value(state, 'subscription_status') not in ('active', 'trial_active') and title['is_premium'] == 'true':
            continue
        seen.add(title['content_slug'])
        valid.append(title)
    if len(valid) < 4:
        return None
    hero, remaining = valid[0], valid[1:]
    genres = Counter(genre for title in remaining for genre in title.get('genres', '').split('|') if genre)
    rows, used = [], {hero['content_slug']}
    rules = pack.interventions['home_page']['rows']
    for genre, _ in sorted(genres.items(), key=lambda item: (-item[1], item[0])):
        group = [title for title in remaining
                 if genre in title.get('genres', '').split('|') and title['content_slug'] not in used]
        group = group[:rules['max_titles_per_row']]
        if len(group) < rules['min_titles_per_row']:
            continue
        rows.append({'row_type': 'genre', 'genre': genre, 'title_ids': [t['title_id'] for t in group]})
        used.update(t['content_slug'] for t in group)
        if len(rows) == min(2, rules['max_rows']):
            break
    if not rows:
        return None
    return {'type': 'home_page', 'dialect': dialect, 'hero_title_id': hero['title_id'], 'rows': rows,
            'ttl_minutes': pack.interventions['home_page']['ttl_minutes']}
