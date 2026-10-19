"""Run a complete local replay, supplied simulator, judgments and reports."""
import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from datetime import timedelta
from .common import jsonl, ts, iso, write_json, write_jsonl
from .data import Pack
from .store import Store
from .engine import Engine
from .reports import measure
from .cohort import freeze_cohort


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, default=Path('data_pack'))
    parser.add_argument('--out', type=Path, default=Path('run_output'))
    parser.add_argument('--seed', default='oua-practice')
    parser.add_argument('--max-model-calls', type=int, default=8)
    parser.add_argument('--max-tool-calls', type=int, default=20)
    args = parser.parse_args()
    if min(args.max_model_calls, args.max_tool_calls) < 0:
        parser.error('Budgets must be nonnegative')
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Output directory must be empty; select a new --out to preserve previous evidence')
    required = ['data/catalogue.csv', 'data/episodes.csv', 'data/profiles_snapshot.csv', 'data/events.jsonl',
                'config/goals.json', 'config/interventions.json', 'replay/triggers.jsonl',
                'replay/live_events.jsonl', 'replay/control_events.jsonl', 'replay/model_faults.jsonl',
                'replay/arms.csv', 'simulator/simulate_outcomes.py']
    missing = [str(args.pack / p) for p in required if not (args.pack / p).is_file()]
    if missing:
        parser.error('Incomplete data pack. Extract the supplied ZIP and point --pack at the folder containing data/, config/, replay/. Missing: ' + ', '.join(missing))
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    pack = Pack(args.pack)
    store = Store(args.out / 'state.sqlite3')
    engine = Engine(pack, store, args.max_model_calls, args.max_tool_calls)
    triggers = jsonl(args.pack / 'replay/triggers.jsonl')
    if not triggers:
        parser.error('Replay has no triggers')
    controls = jsonl(args.pack / 'replay/control_events.jsonl')
    live = jsonl(args.pack / 'replay/live_events.jsonl')
    historical = jsonl(args.pack / 'data/events.jsonl')
    start = min(ts(e['deliver_at']) for e in triggers)
    timeline = []
    for e in historical + live:
        timeline.append((ts(e.get('deliver_at', e['received_at'])), 1, 'event', e))
    for c in controls:
        timeline.append((ts(c['at']), 0, 'control', c))
    for e in triggers:
        timeline.append((ts(e['deliver_at']), 2, 'trigger', e))
    timeline.sort(key=lambda item: (item[0], item[1]))
    end = max(ts(e['deliver_at']) for e in triggers)
    processed, duplicates = set(), 0
    baseline_frozen = False
    print('Replaying server-time timeline...', flush=True)
    for at, _, kind, item in timeline:
        if at >= start and not baseline_frozen:
            freeze_cohort(pack, store, start)
            baseline_frozen = True
        if kind == 'control':
            engine.control(item)
        elif kind == 'event':
            engine.ingest(item)
        else:
            duplicates += int(item['event_id'] in processed)
            processed.add(item['event_id'])
            engine.decide(item)
    store.save_goals()
    store.db.commit()
    decisions, actions = store.rows('decisions'), store.rows('actions')
    write_jsonl(args.out / 'decisions.jsonl', decisions)
    write_jsonl(args.out / 'actions.jsonl', actions)
    write_jsonl(args.out / 'audit.jsonl', store.rows('audit'))
    write_jsonl(args.out / 'revocations.jsonl', store.rows('revocations'))
    write_jsonl(args.out / 'latency_observations.jsonl', engine.timings.values())
    latencies = sorted(engine.timings[d['trigger']['event_id']]['durable_completion_ms'] for d in decisions)
    def percentile(p):
        return latencies[min(len(latencies)-1, int((len(latencies)-1)*p))]
    latency = {'unique_decisions': len(decisions), 'input_triggers': len(triggers),
               'duplicate_triggers': duplicates, 'p50_ms': percentile(.5), 'p95_ms': percentile(.95),
               'p99_ms': percentile(.99), 'max_ms': max(latencies),
               'over_60s': sum(v > 60000 for v in latencies), 'over_5min': sum(v > 300000 for v in latencies),
               'max_model_calls': max(d['model_calls'] for d in decisions),
               'max_tool_calls': max(d['tool_calls'] for d in decisions),
               'scope': 'Measured entry-to-durable-release processing, including both commits and recovery writes; accelerated single-worker replay, excluding production queue latency. Decision published_at marks the release request; latency_observations.jsonl measures its completed commit.',
               'fault_timing': '45s model timeout bounded to 20ms; 8s store reads rejected by fail-fast circuit, no external I/O.'}
    write_json(args.out / 'latency_report.json', latency)
    write_json(args.out / 'data_quality.json', {
        'historical_lines': len(historical),
        'duplicate_historical_events': len(historical)-len({e['event_id'] for e in historical}),
        'duplicate_profile_rows': sum(len(r)-1 for r in pack.profiles.values()),
        'catalogue_records': len(pack.catalogue),
        'extra_content_variants': len(pack.catalogue)-len({t['content_slug'] for t in pack.catalogue.values()}),
        'suspicious_description_title_ids': pack.suspicious,
        'no_action_reasons': dict(Counter(d['no_action_reason'] for d in decisions if d['no_action_reason'])),
        'fallback_decisions': sum(d['fallback_used'] for d in decisions),
        'unobservable_goals': ['G10', 'G11']})
    print('Running supplied simulator...', flush=True)
    subprocess.run([sys.executable, str(args.pack / 'simulator/simulate_outcomes.py'),
                    '--pack', str(args.pack), '--actions', str(args.out / 'actions.jsonl'),
                    '--out', str(args.out / 'sim'), '--seed', args.seed], check=True)
    sim_events = jsonl(args.out / 'sim/outcome_events.jsonl')
    # Simulator contract: 14 days after the replay's first IST day, not its last event timestamp.
    from .common import IST
    midnight = start.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    horizon = midnight + timedelta(days=15)  # exclusive end of the simulator's day 14
    outcomes = measure(pack, store, args.out, start, horizon, sim_events, controls,
                       {e['user_id'] for e in triggers})
    sim_report = json.loads((args.out / 'sim/simulator_report.json').read_text())
    report = ('# Final report\n\n'
              f'{len(decisions)} unique decisions; {len(actions)} home pages; '
              f'{sum(d["action"] == "NO_ACTION" for d in decisions)} abstentions.\n\n'
              f'Outcome judgments: {dict(Counter(j["status"] for j in outcomes))}.\n\n'
              f'Local maximum decision latency: {max(latencies):.2f} ms. '
              f'Simulator policy problems: {sim_report["policy_problem_count"]}.\n\n'
              'See data_quality.json for measured traps, audit.jsonl for control reactions, '
              'impact_report.md for randomized comparisons, and ../KNOWN_LIMITATIONS.md for scope. '
              'See impact_report.md for baseline-goal ITT with missing-outcome bounds. '
              'Page revocation and safe replacement are implemented locally; the supplied simulator has no revocation API. '
              'No outbound messages or hosted provider is enabled.\n')
    (args.out / 'final_report.md').write_text(report, encoding='utf-8')
    store.db.close()
    print(f'Complete: {args.out}; {time.perf_counter()-started:.1f}s total', flush=True)


if __name__ == '__main__':
    main()
