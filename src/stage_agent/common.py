"""Time and file contracts shared by replay and measurement."""
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))


def ts(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None


def iso(value):
    return value.astimezone(UTC).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def day(value):
    return value.astimezone(IST).date().isoformat()


def jsonl(path):
    with Path(path).open(encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def csv_rows(path):
    with Path(path).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def write_jsonl(path, rows):
    with Path(path).open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def trigger_age(e):
    # Device clock offset cancels in sent_at - occurred_at. Queue delay is server based.
    buffered = max(0, (ts(e['sent_at']) - ts(e['occurred_at'])).total_seconds())
    queued = max(0, (ts(e.get('deliver_at', e['received_at'])) - ts(e['received_at'])).total_seconds())
    return buffered + queued
