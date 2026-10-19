"""Explicit eligibility and outcome predicates, never inferred from model prose."""
from datetime import timedelta
from .common import ts, iso, day
from .facts import value

PRIORITY = ['G01', 'G03', 'G04', 'G07', 'G02', 'G06', 'G09', 'G08', 'G05', 'G12']
ASSUMPTIONS = [
    'No prior event means none in the supplied 30-day observation window, not lifetime certainty.',
    'G06 recently lapsed means within 30 days, evidenced by lapse or plan end.',
    'G09 day counts use IST; G07 unwatched means episode not completed, including a partial episode.',
    'G10 is undefined and G11 is unobservable; neither can be selected.',
]


def eligibility(pack, state, history, gid, at, trigger_id=None):
    events = sorted((e for e in history if ts(e['received_at']) <= at and e['event_id'] != trigger_id
                     and ts(e.get('deliver_at', e['received_at'])) <= at),
                    key=lambda e: (ts(e['received_at']), e['event_id']))
    ev = lambda name: [e for e in events if e['event'] == name]
    status = value(state, 'subscription_status')
    signup = ts(value(state, 'signup_at'))
    sub_age = state['facts'].get('subscription_status', {}).get('age_s', float('inf'))
    refs = [f['source'] for f in state['facts'].values()]
    if gid not in pack.goals or gid in ('G10', 'G11'):
        return False, None, []
    if gid in ('G01', 'G03'):
        days = 7 if gid == 'G01' else 2
        ok = bool(signup and timedelta(0) <= at - signup <= timedelta(days=days))
        if gid == 'G01':
            ok = ok and not ev('play_started')
        return ok, None, refs
    if gid == 'G02':
        return bool(events) and not ev('episode_completed'), None, refs
    if gid in ('G04', 'G05', 'G06', 'G08', 'G09'):
        wanted = {'G04': 'trial_active', 'G05': 'never', 'G06': 'lapsed',
                  'G08': 'active', 'G09': 'active'}[gid]
        if status != wanted or sub_age > 48 * 3600:
            return False, None, refs
        if gid == 'G05' and any(not e['properties'].get('is_trial', False)
                                for e in events if e['event'] in ('purchase_completed', 'subscription_renewed')):
            return False, None, refs
        if gid == 'G06':
            lapse = ev('subscription_lapsed')
            p = pack.profile(events[0]['user_id'], at) if events else None
            dates = [ts(e['received_at']) for e in lapse]
            if p and p['plan_ends_at']:
                dates.append(ts(p['plan_ends_at']))
            if not any(timedelta(0) <= at - t <= timedelta(days=30) for t in dates):
                return False, None, refs
        if gid == 'G09':
            days = {day(ts(e['received_at'])) for e in ev('play_started')
                    if ts(e['received_at']) >= at - timedelta(days=14)}
            if len(days) > 1:
                return False, None, refs
        return True, None, refs
    if gid == 'G07':
        by_slug = {}
        for e in ev('play_started'):
            title = pack.catalogue.get(e['properties'].get('title_id'))
            if title and title['content_type'] in ('show', 'micro_drama'):
                by_slug[title['content_slug']] = e
        for slug, last in sorted(by_slug.items()):
            completed = {e['properties'].get('episode_id') for e in ev('episode_completed')}
            remaining = [ep['episode_id'] for ep in pack.episodes.get(slug, []) if ep['episode_id'] not in completed]
            if remaining and at - ts(last['received_at']) >= timedelta(days=3):
                return True, {'content_slug': slug, 'next_episode_id': remaining[0]}, [
                    'event:' + last['event_id'], 'episodes:' + slug,
                    'catalogue:' + last['properties']['title_id']]
        return False, None, refs
    if gid == 'G12':
        # Absence needs at least 14 days of known history, not merely an empty new profile.
        covered = signup and signup <= at - timedelta(days=14)
        recent = any(ts(e['received_at']) >= at - timedelta(days=14) for e in ev('app_open'))
        return bool(covered and events and not recent), None, refs
    return False, None, refs


def choose(pack, state, history, user, at, trigger_id):
    for gid in PRIORITY:
        ok, context, refs = eligibility(pack, state, history, gid, at, trigger_id)
        if ok:
            rule = pack.goals[gid]
            return {'instance_id': f'{user}:{trigger_id}:{gid}', 'user_id': user, 'id': gid,
                    'name': rule['name'], 'started_at': iso(at),
                    'deadline': iso(at + timedelta(hours=rule['success']['window_hours'])),
                    'success_signal': dict(rule['success']), 'rule_version': rule.get('_version', '2026-09-30'),
                    'context': context, 'eligibility_evidence': refs, 'status': 'open'}
    return None


def matching_events(goal, events, pack, until):
    start, end = ts(goal['started_at']), min(ts(goal['deadline']), until)
    hits = []
    for e in events:
        at = ts(e['received_at'])
        if not start <= at <= end or e['event'] != goal['success_signal']['event']:
            continue
        # Buffered evidence received in-window may describe behavior from before commitment.
        if e.get('sent_at') and e.get('occurred_at'):
            buffered = max(timedelta(0), ts(e['sent_at']) - ts(e['occurred_at']))
            if at - buffered < start:
                continue
        gid, props = goal['id'], e.get('properties', {})
        if gid == 'G03' and day(at) <= day(start):
            continue
        if gid in ('G04', 'G05', 'G06') and props.get('is_trial', True):
            continue
        if gid == 'G07':
            t = pack.catalogue.get(props.get('title_id'), {})
            if t.get('content_slug') != (goal.get('context') or {}).get('content_slug'):
                continue
        if gid == 'G08':
            title = pack.catalogue.get(props.get('title_id'))
            if not title:
                continue
            release = ts(title['release_date'] + 'T00:00:00Z')
            if not start - timedelta(days=30) <= release <= start:
                continue
        hits.append(e)
    if goal['id'] == 'G09' and len({day(ts(e['received_at'])) for e in hits}) < 3:
        return []
    return hits


def judge(goal, events, pack, until):
    hits = matching_events(goal, events, pack, until)
    if hits:
        return 'succeeded', [e['event_id'] for e in hits]
    if until < ts(goal['deadline']):
        return 'inconclusive', []
    return 'failed', []


def correct_rule(goals, pack, control):
    gid = control['goal_id']
    rule = pack.goals[gid]
    rule['success'].update(control['new_success'])
    rule['_version'] = control['at']
    affected = []
    for g in goals:
        if g['id'] == gid and g['status'] == 'open':
            g['success_signal'].update(control['new_success'])
            g['rule_version'] = control['at']
            affected.append(g['instance_id'])
    return affected
