"""Read-only pack access; free text is never executable policy."""
import json
from collections import defaultdict
from pathlib import Path
from .common import csv_rows, jsonl, ts


class Pack:
    def __init__(self, path):
        self.path = Path(path)
        self.catalogue = {r['title_id']: r for r in csv_rows(self.path / 'data/catalogue.csv')}
        self.episodes = defaultdict(list)
        for r in csv_rows(self.path / 'data/episodes.csv'):
            self.episodes[r['content_slug']].append(r)
        for rows in self.episodes.values():
            rows.sort(key=lambda r: (int(r['season']), int(r['episode'])))
        self.profiles = defaultdict(list)
        for i, r in enumerate(csv_rows(self.path / 'data/profiles_snapshot.csv'), 2):
            r['_ref'] = f'profiles_snapshot.csv:line:{i}'
            self.profiles[r['user_id']].append(r)
        self.goals = {g['goal_id']: g for g in json.loads((self.path / 'config/goals.json').read_text())['goals']}
        self.interventions = json.loads((self.path / 'config/interventions.json').read_text())
        self.arms = {r['user_id']: r['arm'] for r in csv_rows(self.path / 'replay/arms.csv')}
        self.withdrawn = {}
        self.faults = {r['trigger_event_id']: r for r in jsonl(self.path / 'replay/model_faults.jsonl')}
        # Diagnostic heuristic only. Safety comes from never using descriptions in prompts/copy.
        self.suspicious = [t['title_id'] for t in self.catalogue.values()
                           if any(s in t['description'].lower() for s in
                                  ('ignore', 'instruction', 'system prompt', 'message every'))]

    def profile(self, user, at):
        rows = [r for r in self.profiles.get(user, [])
                if ts(r['snapshot_at']) <= at and ts(r['updated_at']) <= at]
        return max(rows, key=lambda r: (ts(r['updated_at']), ts(r['snapshot_at']), r['_ref']), default=None)

    def available(self, title_id, at, dialect=None):
        t = self.catalogue.get(title_id)
        return bool(t and (dialect is None or t['dialect'] == dialect)
                    and ts(t['available_from']) <= at
                    and (not t['available_until'] or at < ts(t['available_until']))
                    and (title_id not in self.withdrawn or at < ts(self.withdrawn[title_id])))
