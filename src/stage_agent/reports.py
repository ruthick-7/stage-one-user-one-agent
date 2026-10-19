"""Outcome attribution and randomized-arm comparisons with explicit denominators."""
import math
from collections import Counter, defaultdict
from datetime import timedelta
from .common import csv_rows, ts, iso, write_json, write_jsonl
from .goals import judge
from .cohort import evaluate_cohort, summarize, describe


def compare(rows, treatment='agent'):
    counts = {}
    for arm in (treatment, 'holdout'):
        values = [int(r['success']) for r in rows if r['arm'] == arm]
        n, k = len(values), sum(values)
        counts[arm] = {'n': n, 'successes': k, 'rate': k / n if n else None}
    a, b = counts[treatment], counts['holdout']
    if not a['n'] or not b['n']:
        return dict(counts=counts, difference=None, ci95=None)
    diff = a['rate'] - b['rate']
    # Newcombe interval using Wilson score limits; remains nondegenerate for zero successes.
    def wilson(k, n):
        z, p = 1.959963984540054, k / n
        center = (p + z*z/(2*n)) / (1 + z*z/n)
        half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
        return center-half, center+half
    al, au = wilson(a['successes'], a['n'])
    bl, bu = wilson(b['successes'], b['n'])
    lo = diff - math.sqrt((a['rate']-al)**2 + (bu-b['rate'])**2)
    hi = diff + math.sqrt((au-a['rate'])**2 + (b['rate']-bl)**2)
    return {'counts': counts, 'difference': diff, 'ci95': [lo, hi]}


def result_line(name, result):
    groups = '; '.join(f"{a}: {v['successes']}/{v['n']} ({v['rate']:.2%})" if v['n'] else f'{a}: n=0'
                       for a, v in result['counts'].items())
    if result['difference'] is None:
        return f'- {name}: {groups}. Difference unavailable.\n'
    lo, hi = result['ci95']
    return f"- {name}: {groups}. Difference {100*result['difference']:.2f} pp; 95% CI [{100*lo:.2f}, {100*hi:.2f}] pp.\n"


def pilot_report(pack):
    assignments = {r['user_id']: r for r in csv_rows(pack.path / 'pilot/pilot_assignment.csv')}
    rows = csv_rows(pack.path / 'pilot/pilot_outcomes.csv')
    if len({r['user_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate pilot outcomes would invalidate user-level rates')
    observed = {r['user_id']: r for r in rows}
    if not set(assignments) <= set(observed):
        raise ValueError('Missing pilot outcomes: cannot silently count missing as failed')
    itt = compare([{'arm': a['arm'], 'success': observed[u]['succeeded'] == 'true'}
                   for u, a in assignments.items()], 'treatment')
    biased = compare([{'arm': 'agent' if r['served'] == 'true' else 'holdout',
                       'success': r['succeeded'] == 'true'} for r in rows])
    return ('## Pilot re-analysis\n\n' + result_line('Randomized assignment (ITT)', itt) +
            result_line('Served vs all others (biased)', biased) +
            '\nI show the served comparison to illustrate selection bias: active, reachable viewers are more likely to be served. '
            'Randomized treatment includes unserved viewers; excluding them destroys the randomized comparison.\n')


def measure(pack, store, out, replay_start, horizon, sim_events, controls=(), observed_users=None):
    events = defaultdict(dict)
    for user, rows in store.history.items():
        for e in rows:
            events[user][e['event_id']] = e
    for e in sim_events:
        events[e['user_id']][e['event_id']] = e
    decisions = store.rows('decisions')
    first = {}
    for d in decisions:
        first.setdefault(d['viewer_id'], d)
    judgments = []
    for g in store.goals:
        # A plan invalidated before deadline has a censored observation window.
        stop = min(horizon, ts(g['judged_at'])) if g.get('closed_reason') else horizon
        status, evidence = judge(g, list(events[g['user_id']].values()), pack, stop)
        if g.get('closed_reason') and status != 'succeeded':
            status = 'inconclusive'
        judgments.append({'instance_id': g['instance_id'], 'user_id': g['user_id'], 'goal_id': g['id'],
                          'status': status, 'evidence': evidence, 'deadline': g['deadline'],
                          'rule_version': g['rule_version'],
                          'learning': 'Goal success is observed, not proof this action caused it.' if status == 'succeeded'
                          else 'No attributable success; review evidence coverage before changing policy.'})
        g.update(status=status, judged_at=iso(stop), outcome_evidence=evidence,
                 learning=judgments[-1]['learning'])
    by_instance = {j['instance_id']: j for j in judgments}
    # Fixed-horizon, universally defined observable endpoint: a recorded completion in seven days.
    endpoint_end = replay_start + timedelta(days=7)
    # Fixed endpoint uses simulator follow-up only, not buffered historical receipts.
    followup = defaultdict(list)
    for e in sim_events:
        followup[e['user_id']].append(e)
    rows = [{'user_id': u, 'arm': arm, 'success': any(e['event'] == 'episode_completed' and
             replay_start <= ts(e['received_at']) <= endpoint_end for e in followup[u])}
            for u, arm in pack.arms.items()]
    full = compare(rows)
    triggered = compare([r for r in rows if r['user_id'] in first])
    cohort = evaluate_cohort(store.rows('cohort'), events, controls, pack, horizon,
                             set(first) if observed_users is None else observed_users)
    goal_itt = summarize(cohort)
    eligible_itt = summarize([r for r in cohort if r['goal']])
    write_jsonl(out / 'cohort_outcomes.jsonl', cohort)
    report = '# Impact report\n\n## Primary: baseline-goal success by randomized arm\n\n'
    report += ('I freeze measurement goals for every randomized user before the first intervention, '
               'using only already-arrived facts. They are separate from adaptive treatment goals. '
               'I keep all assigned users in their arm, including viewers who receive no action. No eligible goal, '
               'missing simulator follow-up, and incomplete goal windows are **inconclusive**, not failed. '
               'With these unknown outcomes, I cannot identify a full-population point estimate.\n\n')
    report += describe('All randomized users', goal_itt)
    report += describe('Pre-intervention eligible-goal cohort', eligible_itt)
    report += '\n### Baseline goal breakdown\n\n'
    for gid in sorted({r['goal']['id'] for r in cohort if r['goal']}):
        report += describe(gid, summarize([r for r in cohort if r['goal'] and r['goal']['id'] == gid]))
    report += ('\nI calculate bounds by assigning each unknown outcome both possible values. The sampling envelope adds '
               'Newcombe/Wilson uncertainty at those extremes. It is not a missing-data correction or evidence '
               'of rollout benefit. I retain unserved viewers too. The denominators are in cohort_outcomes.jsonl.\n\n'
               '## Secondary: seven-day recorded completion\n\n')
    report += ('For my secondary endpoint, fixed before analysis, I use at least one **recorded episode completion** in the seven days '
               'from replay start. Every randomized user stays in their assigned arm, including abstentions. '
               'This endpoint does not depend on the goal or whether an action was served.\n\n')
    report += result_line('All randomized users: recorded-completion ITT', full)
    report += result_line('Triggered-user subset (includes all abstentions)', triggered)
    missing = sum(u not in first for u in pack.arms)
    report += (f'\nCoverage: {len(first)} triggered / {len(pack.arms)} randomized; {missing} users are not simulated. '
               'Their endpoint is zero **recorded** completions, not evidence they did not watch. '
               'The full-assignment estimate measures this simulator observation process; it must not be presented '
               'as population watch uplift in production. The triggered subset is selected before the first action '
               'but does not estimate impact on untriggered users. No causal claim beyond this synthetic experiment.\n\n')
    report += '## Initial goal outcomes (descriptive, by baseline goal)\n\n'
    report += ('For this descriptive comparison, I keep each viewer\'s first-decision goal fixed before their first intervention. I do not substitute a later goal. '
               'Inconclusive outcomes remain in the denominator and are separately counted; these are recorded-success '
               'contrasts, not an estimate of success for censored goals. Goal groups are small; no multiple-testing correction.\n\n')
    goal_rows = defaultdict(list)
    for u, d in first.items():
        g = d['goal']
        if g:
            outcome = by_instance[g['instance_id']]
            goal_rows[g['id']].append({'arm': pack.arms.get(u), 'success': outcome['status'] == 'succeeded',
                                      'status': outcome['status']})
    for gid, group in sorted(goal_rows.items()):
        report += result_line(gid, compare(group))
        report += f"  Outcome counts: {dict(Counter(r['status'] for r in group))}.\n"
    report += '\nI calculate confidence intervals using Newcombe differences of Wilson limits, treating viewers as independent. '
    report += 'One simulation seed is not a production experiment; intervals omit simulator/model uncertainty.\n\n'
    report += pilot_report(pack)
    (out / 'impact_report.md').write_text(report, encoding='utf-8')
    write_json(out / 'impact_metrics.json', {'baseline_goal_itt': goal_itt, 'baseline_eligible_goal_itt': eligible_itt,
                                           'all_randomized': full, 'triggered': triggered,
                                           'untriggered_without_simulated_outcomes': missing})
    write_jsonl(out / 'outcomes.jsonl', judgments)
    state_dir = out / 'viewer_state'
    state_dir.mkdir()
    from .facts import resolve
    all_actions = store.rows('actions')
    for u in sorted(first):
        ujudgments = [j for j in judgments if j['user_id'] == u]
        write_json(state_dir / f'{u}.json', {'viewer_id': u,
                   'facts_at_followup_horizon': resolve(pack, list(events[u].values()), u, horizon),
                   'goals': [g for g in store.goals if g['user_id'] == u],
                   'decision_ids': [d['decision_id'] for d in decisions if d['viewer_id'] == u],
                   'action_ids': [a['action_id'] for a in all_actions if a['user_id'] == u],
                   'outcomes': ujudgments, 'learnings': [j['learning'] for j in ujudgments]})
    # Outcome judgments and learning are also durable in SQLite, not just exported files.
    store.db.execute('CREATE TABLE IF NOT EXISTS outcomes(instance_id TEXT PRIMARY KEY, payload TEXT)')
    import json
    for j in judgments:
        store.db.execute('INSERT OR REPLACE INTO outcomes VALUES(?,?)', (j['instance_id'], json.dumps(j)))
    store.save_goals()
    store.db.commit()
    write_walkthrough(out, decisions, judgments, events)
    return judgments


def write_walkthrough(out, decisions, judgments, events):
    """Generate an explainable trace from this run, rather than hard-coding a viewer."""
    outcomes = {j['instance_id']: j for j in judgments}
    candidates = [d for d in decisions if d['action'] == 'HOME_PAGE' and d['goal'] and
                  outcomes[d['goal']['instance_id']]['status'] == 'succeeded']
    candidates.sort(key=lambda d: d['goal']['id'] != 'G02')
    lines = ['# How I trace a viewer through this run\n']
    if candidates:
        d = candidates[0]
        g = d['goal']
        j = outcomes[g['instance_id']]
        event = events[d['viewer_id']][j['evidence'][0]]
        lines += [f"Viewer `{d['viewer_id']}`, decision `{d['decision_id']}`.\n",
                  f"1. Trigger `{d['trigger']['event_id']}` arrived at `{d['trigger']['deliver_at']}`.\n",
                  f"2. App dialect `{d['dialect']['used']}` came from `{d['dialect']['source']}`. I check the conflicts and source ages in the decision record.\n",
                  f"3. Goal `{g['id']}` ({g['name']}) started `{g['started_at']}`, with deadline `{g['deadline']}`. Its signal is `{g['success_signal']['event']}`.\n",
                  f"4. Home page action `A-{d['trigger']['event_id']}` passed the independent checks. I can trace its hero and genre rows in actions.jsonl.\n",
                  f"5. Judgment: `{j['status']}`. Event `{event['event_id']}` was `{event['event']}` at `{event['received_at']}`, inside the goal window.\n",
                  '6. I count this as observed goal success. To assess impact, I turn to the randomized-arm report; this single outcome cannot establish causation.\n',
                  f"\nOpen `viewer_state/{d['viewer_id']}.json`, decisions.jsonl, actions.jsonl, outcomes.jsonl and sim/outcome_events.jsonl to locate these records.\n"]
    else:
        lines.append('No published goal succeeded in this run, so my review starts with the failed and inconclusive outcomes.\n')
    abstained = next((d for d in decisions if d['no_action_reason'] == 'stale_trigger_over_600s'), None)
    if abstained:
        lines += ['\n## Abstention example\n',
                  f"Viewer `{abstained['viewer_id']}`, trigger `{abstained['trigger']['event_id']}`, "
                  f"estimated age {abstained['trigger']['event_age_s']} seconds. "
                  f"Reason: `{abstained['no_action_reason']}`. My agent takes no action for this trigger.\n"]
    (out / 'viewer_walkthrough.md').write_text('\n'.join(lines), encoding='utf-8')
