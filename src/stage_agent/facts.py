"""Fact-specific precedence; server timestamps, references and conflicts stay visible."""
from datetime import timedelta
from .common import ts, iso


def resolve(pack, history, user, at, trigger=None):
    p = pack.profile(user, at)
    events = sorted((e for e in history if ts(e['received_at']) <= at),
                    key=lambda e: (e['received_at'], e['event_id']))
    facts, conflicts = {}, []

    def put(key, value, source, when):
        old = facts.get(key)
        if old and old['value'] != value:
            conflicts.append({'fact': key, 'rejected': old, 'selected_source': source})
        facts[key] = {'value': value, 'source': source, 'at': when,
                      'age_s': max(0, (at - ts(when)).total_seconds())}

    if p:
        for key in ('subscription_status', 'notifications_opt_in', 'whatsapp_opt_in', 'signup_at'):
            value = p[key]
            if key.endswith('opt_in'):
                value = value == 'true'
            put(key, value, p['_ref'], p['updated_at'])
        put('dialect', p['preferred_dialect'], p['_ref'], p['updated_at'])
    signup = next((e for e in events if e['event'] == 'signup_completed'), None)
    if signup:
        put('signup_at', signup['received_at'], 'event:' + signup['event_id'], signup['received_at'])
    if not p and signup:
        put('subscription_status', 'never', 'event:' + signup['event_id'], signup['received_at'])
    billing = [e for e in events if e['event'] in
               ('purchase_completed', 'subscription_renewed', 'subscription_lapsed')]
    for e in billing:
        if p and ts(e['received_at']) <= ts(p['updated_at']):
            continue
        status = ('lapsed' if e['event'] == 'subscription_lapsed' else
                  'trial_active' if e['properties'].get('is_trial') else 'active')
        put('subscription_status', status, 'event:' + e['event_id'], e['received_at'])
    sub = facts.get('subscription_status')
    if (p and p.get('plan_ends_at') and sub and sub['source'] == p['_ref']
            and sub['value'] in ('active', 'trial_active') and ts(p['plan_ends_at']) <= at):
        put('subscription_status', 'lapsed', p['_ref'] + ':plan_ends_at', p['plan_ends_at'])
    # An explicit opt-out is sticky: no opt-in event exists in this schema.
    for e in events:
        if e['event'] == 'notification_opt_out':
            key = {'push': 'notifications_opt_in', 'whatsapp': 'whatsapp_opt_in'}.get(e['properties'].get('channel'))
            if key:
                put(key, False, 'event:' + e['event_id'], e['received_at'])
    settings = [e for e in events if e.get('app_dialect')]
    if settings:
        e = settings[-1]
        put('dialect', e['app_dialect'], 'app_setting:event:' + e['event_id'], e['received_at'])
    if trigger:
        link = trigger.get('properties', {}).get('deeplink', '').split('/')
        if len(link) > 4 and link[2] == 'c':
            linked = link[4]
            if facts.get('dialect', {}).get('value') != linked:
                conflicts.append({'fact': 'dialect', 'rejected': {'value': linked, 'source': 'campaign_link'},
                                  'selected_source': facts.get('dialect', {}).get('source')})
    return {'facts': facts, 'conflicts': conflicts, 'observed_event_count': len(events),
            'as_of': iso(at), 'history_window_days': 30}


def value(state, key):
    return state['facts'].get(key, {}).get('value')
