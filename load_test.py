#!/usr/bin/env python3
"""Measure a burst of real replay triggers using isolated per-viewer process shards.

Example: python load_test.py --pack data_pack --out load_run --requests 1000 --workers 4
This is a local cold-start benchmark, not a production capacity guarantee.
"""
import argparse
import hashlib
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from stage_agent.common import jsonl, ts, write_json


def run_shard(pack_path, output, requests, submitted_at):
    from stage_agent.data import Pack
    from stage_agent.store import Store
    from stage_agent.engine import Engine
    pack = Pack(pack_path)
    store = Store(Path(output) / 'state.sqlite3')
    engine = Engine(pack, store)
    users = {e['user_id'] for e in requests}
    events = jsonl(Path(pack_path) / 'data/events.jsonl') + jsonl(Path(pack_path) / 'replay/live_events.jsonl')
    timeline = [(ts(e.get('deliver_at', e['received_at'])), 1, 'event', e)
                for e in events if e['user_id'] in users]
    timeline += [(ts(c['at']), 0, 'control', c) for c in jsonl(Path(pack_path) / 'replay/control_events.jsonl')]
    timeline += [(ts(e['deliver_at']), 2, 'trigger', e) for e in requests]
    timeline.sort(key=lambda item: (item[0], item[1]))
    records = []
    for _, _, kind, item in timeline:
        if kind == 'event':
            engine.ingest(item)
        elif kind == 'control':
            engine.control(item)
        else:
            begin = time.perf_counter()
            d = engine.decide(item)
            finish = time.perf_counter()
            records.append({'event_id': item['event_id'], 'user_id': item['user_id'],
                            'action': d['action'], 'service_ms': (finish-begin)*1000,
                            'end_to_end_ms': (finish-submitted_at)*1000,
                            'queue_and_setup_ms': (begin-submitted_at)*1000})
    store.db.commit()
    store.db.close()
    return records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pack', type=Path, default=Path('data_pack'))
    p.add_argument('--out', type=Path, default=Path('load_run'))
    p.add_argument('--requests', type=int, default=1000)
    p.add_argument('--workers', type=int, default=4)
    args = p.parse_args()
    if args.requests < 1 or args.workers < 1:
        p.error('requests and workers must be positive')
    if args.out.exists() and any(args.out.iterdir()):
        p.error('Choose an empty output directory')
    selected = {}
    for e in jsonl(args.pack / 'replay/triggers.jsonl'):
        selected.setdefault(e['event_id'], e)
        if len(selected) == args.requests:
            break
    if len(selected) < args.requests:
        p.error('Not enough unique triggers in pack')
    args.out.mkdir(parents=True, exist_ok=True)
    shards = [[] for _ in range(args.workers)]
    for e in selected.values():
        index = int(hashlib.sha256(e['user_id'].encode()).hexdigest()[:8], 16) % args.workers
        shards[index].append(e)
    paths = []
    for i in range(args.workers):
        directory = args.out / f'shard_{i}'
        directory.mkdir()
        paths.append(directory)
    submitted = time.perf_counter()  # every request is queued here, including process/setup time
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_shard, str(args.pack), str(path), shard, submitted)
                   for path, shard in zip(paths, shards)]
        records = [r for f in futures for r in f.result()]
    elapsed = time.perf_counter()-submitted
    if len(records) != args.requests or len({r['event_id'] for r in records}) != args.requests:
        raise RuntimeError('Incomplete or duplicate load-test results')
    values = sorted(r['end_to_end_ms'] for r in records)
    report = {'requests': len(records), 'workers': args.workers, 'elapsed_s': elapsed,
              'throughput_requests_per_s': len(records)/elapsed,
              'p50_end_to_end_ms': values[int((len(values)-1)*.5)],
              'p95_end_to_end_ms': values[int((len(values)-1)*.95)],
              'p99_end_to_end_ms': values[int((len(values)-1)*.99)],
              'max_end_to_end_ms': max(values), 'over_60s': sum(v > 60000 for v in values),
              'actions': dict(Counter(r['action'] for r in records)),
              'scope': 'All selected triggers queued at once; includes process startup, pack loading, history ingestion, queue wait and durable decision release. Stable viewer hashing gives one owner per viewer. Separate SQLite per shard; mock provider; not shared-database or production load.'}
    write_json(args.out / 'load_report.json', report)
    write_json(args.out / 'request_timings.json', records)
    print(report)
    if report['over_60s']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
