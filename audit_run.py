#!/usr/bin/env python3
"""Independently audit exported replay artifacts without calling the production verifier."""
import argparse
import csv
import json
from pathlib import Path
from datetime import datetime


def read(path):
    with Path(path).open(encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def instant(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pack', type=Path, default=Path('data_pack'))
    p.add_argument('--run', type=Path, default=Path('sample_run'))
    args = p.parse_args()
    with (args.pack / 'data/catalogue.csv').open(encoding='utf-8', newline='') as f:
        catalogue = {r['title_id']: r for r in csv.DictReader(f)}
    with (args.pack / 'replay/arms.csv').open(encoding='utf-8', newline='') as f:
        arms = {r['user_id']: r['arm'] for r in csv.DictReader(f)}
    controls = read(args.pack / 'replay/control_events.jsonl')
    withdrawn = {r['title_id']: instant(r['at']) for r in controls if r['type'] == 'title_withdrawn'}
    decisions, actions = read(args.run / 'decisions.jsonl'), read(args.run / 'actions.jsonl')
    cohort = read(args.run / 'cohort_outcomes.jsonl')
    errors = []

    def require(ok, message):
        if not ok:
            errors.append(message)

    require(len(decisions) == len({d['trigger']['event_id'] for d in decisions}), 'duplicate decisions')
    require(len(actions) == len({a['trigger_event_id'] for a in actions}), 'duplicate actions')
    require(len(cohort) == len(arms) == len({r['user_id'] for r in cohort}), 'cohort denominator mismatch')
    for row in cohort:
        require(row['arm'] == arms.get(row['user_id']), 'cohort arm changed')
        if row['observation_reason'] == 'not_simulated_no_followup':
            require(row['status'] == 'inconclusive', 'missing outcome counted as failed')
    by_decision = {d['decision_id']: d for d in decisions}
    for action in actions:
        prefix = action['action_id'] + ': '
        require(arms.get(action['user_id']) == 'agent', prefix+'holdout/unknown action')
        require(action.get('publication_state') == 'ready', prefix+'unreleased action')
        require(by_decision.get(action['decision_id'], {}).get('action') == 'HOME_PAGE', prefix+'missing parent decision')
        ids = [action.get('hero_title_id')] + [t for row in action.get('rows', []) for t in row['title_ids']]
        require(all(t in catalogue for t in ids), prefix+'unknown title')
        if not all(t in catalogue for t in ids):
            continue
        titles = [catalogue[t] for t in ids]
        at = instant(action['published_at'])
        require(len(ids) == len({t['content_slug'] for t in titles}), prefix+'duplicate content_slug')
        require(all(t['dialect'] == action['dialect'] for t in titles), prefix+'wrong dialect')
        require(all(instant(t['available_from']) <= at and
                    (not t['available_until'] or at < instant(t['available_until'])) and
                    (t['title_id'] not in withdrawn or at < withdrawn[t['title_id']]) for t in titles), prefix+'unavailable title')
        require(len(action['rows']) <= 6 and all(3 <= len(r['title_ids']) <= 10 for r in action['rows']), prefix+'row limits')
        for row in action['rows']:
            require(row['row_type'] in {'next_episode', 'because_you_watched', 'popular_in_dialect', 'new_releases', 'genre'}, prefix+'row type')
            if row.get('genre'):
                require(all(row['genre'] in catalogue[t]['genres'].split('|') for t in row['title_ids']), prefix+'genre mismatch')
    for decision in decisions:
        require(decision['action'] == 'HOME_PAGE' or bool(decision.get('no_action_reason')), 'unexplained abstention')
        require(decision['model_calls'] <= 8 and decision['tool_calls'] <= 20, 'call budget exceeded')
        require(decision['decided_in_ms'] < 60000, 'decision exceeded 60 seconds')
    simulator = json.loads((args.run / 'sim/simulator_report.json').read_text(encoding='utf-8'))
    require(simulator['policy_problem_count'] == 0, 'simulator policy violations')
    require(simulator['counts'].get('home_page_accepted', 0) == len(actions), 'simulator rejected a page')
    report = {'decisions': len(decisions), 'actions': len(actions), 'randomized_users': len(cohort),
              'errors': errors, 'passed': not errors}
    (args.run / 'artifact_audit.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(report)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
