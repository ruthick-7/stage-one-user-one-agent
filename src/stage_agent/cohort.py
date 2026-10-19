"""Pre-intervention goal assignment and missing-outcome-aware randomized measurement."""
import copy
import json
from collections import Counter
from .common import ts
from .facts import resolve
from .goals import choose, judge


def freeze_cohort(pack, store, at):
    """Assign measurement goals to ALL randomized users before the first intervention.

    This table is independent of the adaptive treatment policy. Holdout receives the
    same eligibility evaluation but no action. No follow-up fact is visible here.
    """
    for user, arm in sorted(pack.arms.items()):
        history = [e for e in store.history.get(user, [])
                   if ts(e['received_at']) <= at and ts(e.get('deliver_at', e['received_at'])) <= at]
        state = resolve(pack, history, user, at)
        goal = choose(pack, state, history, user, at, 'baseline')
        row = {'user_id': user, 'arm': arm, 'goal': goal,
               'assignment_reason': 'eligible_at_baseline' if goal else 'no_measurable_goal_at_baseline'}
        store.db.execute('INSERT INTO cohort VALUES(?,?)', (user, json.dumps(row)))
    store.db.commit()


def evaluate_cohort(cohort, events, controls, pack, horizon, observed_users):
    result = []
    corrections = sorted((c for c in controls if c['type'] == 'goal_rule_corrected'), key=lambda c: ts(c['at']))
    for row in cohort:
        goal = copy.deepcopy(row['goal'])
        history = list(events.get(row['user_id'], {}).values())
        status, evidence = 'inconclusive', []
        reason = 'no_measurable_goal_at_baseline'
        if goal:
            for control in corrections:
                at = ts(control['at'])
                if goal['id'] != control['goal_id'] or at < ts(goal['started_at']):
                    continue
                known = [e for e in history if ts(e.get('deliver_at', e['received_at'])) <= at]
                before, _ = judge(goal, known, pack, at)
                if before == 'inconclusive':
                    goal['success_signal'].update(control['new_success'])
                    goal['rule_version'] = control['at']
            status, evidence = judge(goal, history, pack, horizon)
            reason = 'complete_followup'
            if status != 'succeeded' and row['user_id'] not in observed_users:
                status, reason = 'inconclusive', 'not_simulated_no_followup'
            elif status == 'inconclusive':
                reason = 'goal_deadline_after_followup'
        result.append({**row, 'goal': goal, 'status': status, 'evidence': evidence, 'observation_reason': reason})
    return result


def summarize(rows):
    """Keep missing outcomes in ITT denominators and report identification bounds.

    Lower/upper differences consider all possible binary outcomes for the unknowns.
    The sampling envelope combines Wilson/Newcombe limits at these worst cases.
    """
    from .reports import compare
    counts, worst_low, worst_high = {}, [], []
    for arm in ('agent', 'holdout'):
        group = [r for r in rows if r['arm'] == arm]
        c = Counter(r['status'] for r in group)
        n = len(group)
        unknown = c['inconclusive']
        counts[arm] = {'n': n, 'succeeded': c['succeeded'], 'failed': c['failed'],
                       'inconclusive': unknown,
                       'success_rate_bounds': [c['succeeded']/n, (c['succeeded']+unknown)/n] if n else None}
        for row in group:
            success = row['status'] == 'succeeded'
            missing = row['status'] == 'inconclusive'
            worst_low.append({'arm': arm, 'success': success or (missing and arm == 'holdout')})
            worst_high.append({'arm': arm, 'success': success or (missing and arm == 'agent')})
    low, high = compare(worst_low), compare(worst_high)
    if low['difference'] is None:
        return {'counts': counts, 'difference': None, 'difference_bounds': None, 'ci95_envelope': None}
    bounds = [low['difference'], high['difference']]
    return {'counts': counts,
            'difference': bounds[0] if not any(c['inconclusive'] for c in counts.values()) else None,
            'difference_bounds': bounds, 'ci95_envelope': [low['ci95'][0], high['ci95'][1]]}


def describe(name, summary):
    groups = '; '.join(f"{arm}: n={c['n']}, succeeded={c['succeeded']}, failed={c['failed']}, "
                       f"inconclusive={c['inconclusive']}" for arm, c in summary['counts'].items())
    bounds = summary['difference_bounds']
    if bounds is None:
        return f'- {name}: {groups}. Difference unavailable (empty arm).\n'
    lo, hi = summary['ci95_envelope']
    return (f'- {name}: {groups}. Success difference bounds [{100*bounds[0]:.2f}, {100*bounds[1]:.2f}] pp; '
            f'95% sampling envelope [{100*lo:.2f}, {100*hi:.2f}] pp.\n')
