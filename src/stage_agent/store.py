"""SQLite is the durable ledger; publication and decision share one transaction."""
import json
import sqlite3
from collections import defaultdict


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, user_id TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS decisions(trigger_id TEXT PRIMARY KEY, user_id TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS actions(action_id TEXT PRIMARY KEY, user_id TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS goals(instance_id TEXT PRIMARY KEY, user_id TEXT, status TEXT, payload TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS one_open_goal ON goals(user_id) WHERE status='open';
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, payload TEXT);
        ''')
        self.history = defaultdict(list)
        for (payload,) in self.db.execute('SELECT payload FROM events'):
            e = json.loads(payload)
            self.history[e['user_id']].append(e)
        self.goals = [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM goals')]

    def ingest(self, e):
        cur = self.db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?)',
                              (e['event_id'], e['user_id'], json.dumps(e)))
        if cur.rowcount:
            self.history[e['user_id']].append(e)
        return bool(cur.rowcount)

    def decision(self, trigger):
        row = self.db.execute('SELECT payload FROM decisions WHERE trigger_id=?', (trigger,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_goals(self):
        # Close old rows before inserting replacements: enforce one open goal in the DB too.
        for g in sorted(self.goals, key=lambda g: g['status'] == 'open'):
            self.db.execute('INSERT OR REPLACE INTO goals VALUES(?,?,?,?)',
                            (g['instance_id'], g['user_id'], g['status'], json.dumps(g)))

    def publish(self, e, d, action):
        self.save_goals()
        self.db.execute('INSERT INTO decisions VALUES(?,?,?)', (e['event_id'], e['user_id'], json.dumps(d)))
        if action:
            self.db.execute('INSERT INTO actions VALUES(?,?,?)',
                            (action['action_id'], e['user_id'], json.dumps(action)))
        self.db.commit()

    def audit(self, entry):
        self.db.execute('INSERT INTO audit(payload) VALUES(?)', (json.dumps(entry),))

    def rows(self, table):
        if table not in {'decisions', 'actions', 'audit'}:
            raise ValueError('Unknown ledger')
        return [json.loads(r[0]) for r in self.db.execute(f'SELECT payload FROM {table}')]
