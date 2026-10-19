"""Publication gate recomputes policy from evidence; planner/model cannot approve themselves."""
from .common import ts, day, IST
from .facts import value
from .goals import eligibility


def verify_proposal(proposal, candidate, pack, state, history, at, trigger_id):
    if not isinstance(proposal, dict):
        return ['invalid_model_schema']
    if proposal.get('goal_id') is None and candidate is None:
        return []
    gid = proposal.get('goal_id')
    if not isinstance(gid, str):
        return ['invalid_model_goal_id']
    # An active goal retains its original eligibility evidence, not the latest dialect fact.
    if candidate:
        from .facts import resolve
        at = ts(candidate['started_at'])
        state = resolve(pack, history, candidate['user_id'], at)
        trigger_id = candidate['instance_id'].split(':')[1]
    ok, _, refs = eligibility(pack, state, history, gid, at, trigger_id)
    if not ok:
        return ['unsupported_eligibility_claim']
    supplied = proposal.get('evidence')
    if not supplied or not isinstance(supplied, list) or not set(supplied).issubset(set(refs)):
        return ['unsupported_model_claim']
    if not candidate or gid != candidate['id']:
        return ['model_goal_disagrees_with_single_active_plan']
    return []


def verify_action(action, goal, pack, state, history, user, at, prior_actions, trigger_id):
    failed, passed = [], []

    def check(name, ok):
        (passed if ok else failed).append(name)

    check('holdout', pack.arms.get(user) == 'agent')
    # Eligibility is anchored to commitment; later negative-event changes invalidate in the engine.
    start = ts(goal['started_at'])
    start_state = state if start == at else None
    # Resolve independently rather than trusting the goal's stored eligibility Boolean.
    from .facts import resolve
    start_state = start_state or resolve(pack, history, user, start)
    ok, _, _ = eligibility(pack, start_state, history, goal['id'], start,
                            goal['instance_id'].split(':')[1])
    check('eligibility', ok)
    check('measurable_goal', goal['success_signal'].get('event') is not None)
    check('duplicate_action', not any(a['trigger_event_id'] == trigger_id for a in prior_actions))
    typ = action.get('type')
    check('supported_action', typ in ('home_page', 'push', 'whatsapp', 'in_app_message'))
    if typ == 'home_page':
        rows = action.get('rows', [])
        rules = pack.interventions['home_page']['rows']
        ids = [action.get('hero_title_id')] + [tid for row in rows for tid in row['title_ids']]
        check('row_structure', bool(action.get('hero_title_id')) and len(rows) <= rules['max_rows']
              and all(r['row_type'] in rules['row_types'] and
                      rules['min_titles_per_row'] <= len(r['title_ids']) <= rules['max_titles_per_row'] for r in rows))
        slugs = [pack.catalogue[t]['content_slug'] for t in ids if t in pack.catalogue]
        check('content_slug_unique', len(slugs) == len(ids) == len(set(slugs)))
    else:
        ids = [action.get('title_id')]
    check('dialect', action.get('dialect') == value(state, 'dialect') and
          all(t in pack.catalogue and pack.catalogue[t]['dialect'] == value(state, 'dialect') for t in ids))
    check('availability', all(pack.available(t, at) for t in ids))
    if typ in ('push', 'whatsapp'):
        send = ts(action.get('send_at', action['published_at']))
        check('availability_at_send', all(pack.available(t, send) for t in ids))
        field = 'notifications_opt_in' if typ == 'push' else 'whatsapp_opt_in'
        consent = state['facts'].get(field, {})
        check('consent', consent.get('value') is True and consent.get('age_s', 1e9) <= 48 * 3600)
        check('quiet_hours', 8 <= send.astimezone(IST).hour < 22)
        check('frequency_cap', not any(a['type'] in ('push', 'whatsapp') and
              day(ts(a.get('send_at', a['published_at']))) == day(send) for a in prior_actions))
        if typ == 'push':
            text = action.get('text', {})
            check('copy_limits', len(text.get('title', '')) <= 40 and len(text.get('body', '')) <= 120)
            copy = ' '.join(text.values()).lower()
            check('honest_copy', not any(x in copy for x in pack.interventions['push']['copy']['forbidden_phrases'])
                  and not any(x in copy for x in ('₹', 'discount', 'offer', 'free', 'rs.')))
            check('deeplink', action.get('deeplink') == 'ott://title/' + str(action.get('title_id')))
        else:
            templates = {t['template_id']: t for t in pack.interventions['whatsapp']['approved_templates']}
            # Only catalogue-backed recommendation template is implemented.
            t = pack.catalogue.get(action.get('title_id'), {})
            check('approved_template', action.get('template_id') in templates and
                  action.get('template_id') == 'wa_recommend_title_v1' and
                  action.get('variables') == {'title_name': t.get('title'), 'dialect_name': t.get('dialect')})
    if typ == 'in_app_message':
        check('in_app_frequency', not any(a['type'] == typ and day(ts(a['published_at'])) == day(at) for a in prior_actions))
    return {'passed': passed, 'failed': failed}
