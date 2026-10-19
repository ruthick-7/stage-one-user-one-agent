"""SQLite is the durable ledger; publication and decision share one transaction."""
import json
import sqlite3
import tempfile
from collections import defaultdict
from pathlib import Path
from .recovery import RecoveryJournal


class Store:
    def __init__(self, path):
        recovery_path = (Path(tempfile.mkdtemp(prefix='stage-recovery-')) if str(path) == ':memory:'
                         else Path(path).parent / 'recovery')
        self.recovery = RecoveryJournal(recovery_path)
        self.db = sqlite3.connect(path)
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, user_id TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS decisions(trigger_id TEXT PRIMARY KEY, user_id TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS actions(action_id TEXT PRIMARY KEY, user_id TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS goals(instance_id TEXT PRIMARY KEY, user_id TEXT, status TEXT, payload TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS one_open_goal ON goals(user_id) WHERE status='open';
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, payload TEXT);
        CREATE TABLE IF NOT EXISTS cohort(user_id TEXT PRIMARY KEY, payload TEXT);
        CREATE TABLE IF NOT EXISTS revocations(action_id TEXT PRIMARY KEY, payload TEXT);
        ''')
        # A crash before release must never expose a staged page as a published action.
        for trigger, payload in self.db.execute('SELECT trigger_id,payload FROM decisions').fetchall():
            d = json.loads(payload)
            if d.get('publication_state') == 'pending':
                d.update(action='NO_ACTION', status='ABSTAINED', content=[], publication_state='ready',
                         no_action_reason='interrupted_publication')
                self.db.execute('DELETE FROM actions WHERE action_id=?', ('A-' + trigger,))
                self.db.execute('UPDATE decisions SET payload=? WHERE trigger_id=?', (json.dumps(d), trigger))
        self.db.commit()
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

    def release(self, e, decision, action):
        """Only ready entries can leave the local outbox."""
        decision['publication_state'] = 'ready'
        self.db.execute('UPDATE decisions SET payload=? WHERE trigger_id=?',
                        (json.dumps(decision), e['event_id']))
        if action:
            action['publication_state'] = 'ready'
            self.db.execute('UPDATE actions SET payload=? WHERE action_id=?',
                            (json.dumps(action), action['action_id']))
        self.db.commit()

    def revoke(self, action, at, reason):
        record = {'action_id': action['action_id'], 'user_id': action['user_id'],
                  'revoked_at': at, 'reason': reason}
        self.db.execute('INSERT OR IGNORE INTO revocations VALUES(?,?)',
                        (action['action_id'], json.dumps(record)))
        action['revoked_at'] = at
        self.db.execute('UPDATE actions SET payload=? WHERE action_id=?',
                        (json.dumps(action), action['action_id']))
        return record

    def audit(self, entry):
        self.db.execute('INSERT INTO audit(payload) VALUES(?)', (json.dumps(entry),))

    def rows(self, table):
        if table not in {'decisions', 'actions', 'audit', 'cohort', 'revocations'}:
            raise ValueError('Unknown ledger')
        rows = [json.loads(r[0]) for r in self.db.execute(f'SELECT payload FROM {table}')]
        if table in ('decisions', 'actions'):
            recovery = {d['trigger']['event_id']: d for d in self.recovery.rows()}
            key = (lambda r: r['trigger']['event_id']) if table == 'decisions' else (lambda r: r['trigger_event_id'])
            rows = [r for r in rows if r.get('publication_state', 'ready') == 'ready' and key(r) not in recovery]
            if table == 'decisions':
                rows += list(recovery.values())
            rows.sort(key=lambda r: (r['published_at'], r.get('decision_id', r.get('action_id'))))
        return rows
