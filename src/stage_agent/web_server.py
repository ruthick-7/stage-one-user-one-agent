"""Local authenticated API and static website for the offline assessment pipeline."""
import argparse
import hashlib
import hmac
import json
import mimetypes
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter, OrderedDict, defaultdict
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from .common import jsonl, ts, IST
from .web_auth import Accounts, AuthError, SESSION_SECONDS

ROOT = Path(__file__).resolve().parents[2]
REPORTS = {
    'final_report.md': ('Final report', 'Run summary and remaining limitations'),
    'impact_report.md': ('Impact report', 'Randomized comparisons and observation limits'),
    'latency_report.json': ('Latency report', 'Processing time and decision budgets'),
    'data_quality.json': ('Data quality', 'Duplicates, source conflicts and abstention reasons'),
    'artifact_audit.json': ('Artifact audit', 'Independent checks on exported actions'),
    'sim/simulator_report.json': ('Simulator report', 'Accepted pages and reported policy violations'),
}
COOKIE = 'stage_session'


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


class Runs:
    def __init__(self, root, accounts):
        self.root, self.accounts = Path(root), accounts
        self.cache, self.lock = OrderedDict(), threading.RLock()

    def list(self, user_id):
        rows = [{'id': 'sample', 'label': 'Included sample', 'sample': True}] if (self.root/'sample_run/final_report.md').exists() else []
        with self.accounts.connection() as db:
            jobs = db.execute("SELECT id,seed,created_at FROM jobs WHERE user_id=? AND status='completed' ORDER BY created_at DESC", (user_id,)).fetchall()
        return rows + [{'id': r['id'], 'label': 'Replay · '+r['seed'], 'sample': False, 'created_at': r['created_at']} for r in jobs]

    def path(self, user_id, run_id):
        if run_id == 'sample':
            path = self.root/'sample_run'
        else:
            with self.accounts.connection() as db:
                job = db.execute("SELECT output_path FROM jobs WHERE id=? AND user_id=? AND status='completed'", (run_id, user_id)).fetchone()
            if not job:
                raise AuthError('This run is unavailable.', 404)
            path = Path(job['output_path'])
        if not (path/'final_report.md').is_file():
            raise AuthError('No completed results are available yet.', 404)
        return path

    def load(self, user_id, run_id):
        path = self.path(user_id, run_id)
        key = str(path.resolve())
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
            decisions = jsonl(path/'decisions.jsonl')
            outcomes = jsonl(path/'outcomes.jsonl')
            actions = jsonl(path/'actions.jsonl')
            cohort = jsonl(path/'cohort_outcomes.jsonl')
            by_user, user_outcomes = defaultdict(list), defaultdict(list)
            arms = {r['user_id']: r['arm'] for r in cohort}
            for d in decisions:
                by_user[d['viewer_id']].append(d)
            for j in outcomes:
                user_outcomes[j['user_id']].append(j)
            hours = Counter(ts(d['published_at']).astimezone(IST).strftime('%H:00') for d in decisions)
            viewers = []
            for user, history in sorted(by_user.items()):
                last = history[-1]
                viewers.append({'id': user, 'arm': arms.get(user, 'unknown'), 'decisions': len(history),
                                'actions': sum(d['action'] == 'HOME_PAGE' for d in history),
                                'dialect': last['dialect']['used'], 'last_action': last['action'],
                                'goal': (last['goal'] or {}).get('id'), 'last_seen': last['trigger']['deliver_at']})
            data = {'path': path, 'decisions': decisions, 'outcomes': outcomes, 'actions': actions,
                    'cohort': cohort, 'by_user': by_user, 'user_outcomes': user_outcomes, 'viewers': viewers,
                    'summary': {'decisions': len(decisions), 'actions': len(actions),
                                'abstentions': sum(d['action'] == 'NO_ACTION' for d in decisions),
                                'viewers': len(viewers), 'outcomes': dict(Counter(j['status'] for j in outcomes)),
                                'fallbacks': sum(d['fallback_used'] for d in decisions),
                                'timeline': [{'hour': h, 'count': hours.get(h, 0)} for h in [f'{i:02d}:00' for i in range(24)]],
                                'latency': read_json(path/'latency_report.json', {}),
                                'quality': read_json(path/'data_quality.json', {}),
                                'simulator': read_json(path/'sim/simulator_report.json', {}),
                                'audit': read_json(path/'artifact_audit.json', {}),
                                'impact': read_json(path/'impact_metrics.json', {})}}
            self.cache[key] = data
            while len(self.cache) > 4:
                self.cache.popitem(last=False)
            return data


class Jobs:
    def __init__(self, root, pack, data_dir, accounts):
        self.root, self.pack, self.data_dir, self.accounts = Path(root), Path(pack), Path(data_dir), accounts
        self.lock, self.active, self.process = threading.RLock(), None, None

    def available(self):
        return all((self.pack/p).is_file() for p in ('data/catalogue.csv', 'replay/triggers.jsonl', 'simulator/simulate_outcomes.py'))

    def list(self, user_id):
        with self.accounts.connection() as db:
            rows = db.execute('SELECT id,status,seed,created_at,finished_at,error FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 20', (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def start(self, user_id, seed):
        if not isinstance(seed, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', seed):
            raise AuthError('Use 1–64 letters, numbers, dots, hyphens or underscores for the seed.')
        if not self.available():
            raise AuthError('Extract the supplied assignment pack into data_pack/ before starting a replay.', 409)
        with self.lock:
            if self.active:
                raise AuthError('A replay is already running. Wait for it to finish before starting another.', 409)
            key = uuid.uuid4().hex
            folder = self.data_dir/'runs'/str(user_id)/key
            folder.parent.mkdir(parents=True, exist_ok=True)
            log = folder.with_suffix('.log')
            with self.accounts.connection() as db:
                db.execute('INSERT INTO jobs(id,user_id,status,seed,output_path,log_path,created_at) VALUES(?,?,?,?,?,?,?)',
                           (key, user_id, 'queued', seed, str(folder), str(log), int(time.time())))
            self.active = key
            threading.Thread(target=self._run, args=(key, folder, log, seed), daemon=True).start()
        return key

    def _run(self, key, folder, log_path, seed):
        error, status = None, 'failed'
        try:
            with self.lock:
                with self.accounts.connection() as db:
                    row = db.execute('SELECT status FROM jobs WHERE id=?', (key,)).fetchone()
                    if row['status'] == 'cancelled':
                        return
                    db.execute("UPDATE jobs SET status='running' WHERE id=?", (key,))
                with log_path.open('w', encoding='utf-8') as log:
                    self.process = subprocess.Popen([sys.executable, str(self.root/'run.py'), '--pack', str(self.pack),
                                                     '--out', str(folder), '--seed', seed], cwd=self.root,
                                                    stdout=log, stderr=subprocess.STDOUT)
            code = self.process.wait()
            with self.accounts.connection() as db:
                cancelled = db.execute('SELECT status FROM jobs WHERE id=?', (key,)).fetchone()['status'] == 'cancelled'
            if cancelled:
                status = 'cancelled'
            elif code == 0:
                with log_path.open('a', encoding='utf-8') as log:
                    audit = subprocess.run([sys.executable, str(self.root/'audit_run.py'), '--pack', str(self.pack),
                                            '--run', str(folder)], cwd=self.root, stdout=log, stderr=subprocess.STDOUT)
                if audit.returncode:
                    error = 'The replay finished but its independent audit failed. Check the local run log.'
                else:
                    status = 'completed'
            else:
                error = 'The replay could not finish. Check the data pack and the local run log.'
        except (OSError, ValueError) as exc:
            error = 'Unable to run the replay: ' + type(exc).__name__
        finally:
            with self.lock:
                with self.accounts.connection() as db:
                    current = db.execute('SELECT status FROM jobs WHERE id=?', (key,)).fetchone()['status']
                    db.execute('UPDATE jobs SET status=?,finished_at=?,error=? WHERE id=?',
                               ('cancelled' if current == 'cancelled' else status, int(time.time()), error, key))
                self.active, self.process = None, None

    def cancel(self, user_id, key):
        with self.lock:
            with self.accounts.connection() as db:
                job = db.execute('SELECT status FROM jobs WHERE id=? AND user_id=?', (key, user_id)).fetchone()
                if not job:
                    raise AuthError('Run not found.', 404)
                if job['status'] not in ('queued', 'running'):
                    raise AuthError('Only queued or running replays can be cancelled.', 409)
                db.execute("UPDATE jobs SET status='cancelled',finished_at=? WHERE id=?", (int(time.time()), key))
            if self.active == key and self.process and self.process.poll() is None:
                self.process.terminate()

    def shutdown(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()


class WebApplication:
    def __init__(self, root=ROOT, pack=None, data_dir=None):
        self.root = Path(root).resolve()
        self.pack = Path(pack or self.root/'data_pack').resolve()
        self.data_dir = Path(data_dir or self.root/'.local/web').resolve()
        self.accounts = Accounts(self.data_dir/'accounts.sqlite3')
        self.runs = Runs(self.root, self.accounts)
        self.jobs = Jobs(self.root, self.pack, self.data_dir, self.accounts)
        self.attempts, self.attempt_lock = {}, threading.Lock()

    def rate_limit(self, ip, email):
        key, now = hashlib.sha256((ip+str(email)).encode()).hexdigest(), time.time()
        with self.attempt_lock:
            self.attempts = {k: [t for t in times if t > now-60] for k, times in self.attempts.items() if times and times[-1] > now-60}
            times = self.attempts.setdefault(key, [])
            if len(times) >= 8:
                raise AuthError('Too many attempts. Wait a minute and try again.', 429)
            times.append(now)


class Handler(BaseHTTPRequestHandler):
    server_version = 'StageLocal/1.0'

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    @property
    def app(self):
        return self.server.app

    def headers_for(self, status, content_type='application/json; charset=utf-8', extra=None, size=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if size is not None:
            self.send_header('Content-Length', str(size))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def respond(self, value, status=200, extra=None):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.headers_for(status, extra=extra, size=len(body))
        self.wfile.write(body)

    def token(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            return ''
        return cookie[COOKIE].value if COOKIE in cookie else ''

    def user(self):
        user = self.app.accounts.session(self.token())
        if not user:
            raise AuthError('Sign in to continue.', 401)
        return user

    def body(self):
        if self.headers.get_content_type() != 'application/json':
            raise AuthError('Send JSON with Content-Type application/json.', 415)
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise AuthError('Invalid request length.') from None
        if size < 0 or size > 32768:
            raise AuthError('Request is too large.', 413)
        try:
            value = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeError):
            raise AuthError('The request is not valid JSON.') from None
        if not isinstance(value, dict):
            raise AuthError('Expected a JSON object.')
        return value

    def check_origin(self):
        port = self.server.server_port
        allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if self.headers.get('Host') not in allowed:
            raise AuthError('Unrecognized local host.', 403)
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://{host}' for host in allowed}:
            raise AuthError('Cross-origin requests are not allowed.', 403)

    def do_GET(self):
        try:
            self.check_origin()
            parsed = urlsplit(self.path)
            path, query = unquote(parsed.path), parse_qs(parsed.query)
            if path in ('/', '/index.html', '/assets/app.js', '/assets/style.css', '/assets/favicon.svg'):
                name = 'index.html' if path in ('/', '/index.html') else path.rsplit('/', 1)[-1]
                data = (self.app.root/'web'/name).read_bytes()
                self.headers_for(200, mimetypes.guess_type(name)[0] or 'application/octet-stream', size=len(data))
                self.wfile.write(data)
                return
            if path == '/api/health':
                return self.respond({'status': 'ok'})
            user = self.user()
            uid = user['id']
            if path == '/api/auth/me':
                return self.respond({'user': user})
            if path == '/api/runs':
                return self.respond({'runs': self.app.runs.list(uid), 'can_run': self.app.jobs.available()})
            if path == '/api/jobs':
                return self.respond({'jobs': self.app.jobs.list(uid)})
            run_id = query.get('run', ['sample'])[0]
            data = self.app.runs.load(uid, run_id)
            if path == '/api/summary':
                return self.respond(data['summary'])
            if path == '/api/viewers':
                search = query.get('q', [''])[0].strip().lower()[:100]
                arm = query.get('arm', [''])[0]
                page = max(1, min(10000, int(query.get('page', ['1'])[0])))
                rows = [v for v in data['viewers'] if (not search or search in v['id'].lower()) and (not arm or v['arm'] == arm)]
                return self.respond({'viewers': rows[(page-1)*20:page*20], 'total': len(rows), 'page': page, 'page_size': 20})
            if path.startswith('/api/viewers/'):
                viewer = path.removeprefix('/api/viewers/')
                if viewer not in data['by_user']:
                    raise AuthError('Viewer not found.', 404)
                return self.respond({'viewer': next(v for v in data['viewers'] if v['id'] == viewer),
                                     'decisions': data['by_user'][viewer], 'outcomes': data['user_outcomes'][viewer],
                                     'actions': [a for a in data['actions'] if a['user_id'] == viewer]})
            if path == '/api/decisions':
                action = query.get('action', [''])[0]
                q = query.get('q', [''])[0].strip().lower()[:100]
                page = max(1, min(10000, int(query.get('page', ['1'])[0])))
                rows = [d for d in reversed(data['decisions']) if (not action or d['action'] == action) and
                        (not q or q in d['viewer_id'].lower() or q in d['decision_id'].lower())]
                brief = [{k: d[k] for k in ('decision_id', 'viewer_id', 'action', 'no_action_reason', 'goal', 'dialect', 'decided_in_ms', 'fallback_used', 'published_at')} for d in rows[(page-1)*20:page*20]]
                return self.respond({'decisions': brief, 'total': len(rows), 'page': page, 'page_size': 20})
            if path == '/api/experiments':
                from .cohort import summarize
                groups = {}
                for gid in sorted({r['goal']['id'] for r in data['cohort'] if r['goal']}):
                    groups[gid] = summarize([r for r in data['cohort'] if r['goal'] and r['goal']['id'] == gid])
                return self.respond({'metrics': data['summary']['impact'], 'goals': groups})
            if path == '/api/reports':
                return self.respond({'reports': [{'file': f, 'title': title, 'description': description}
                                                for f, (title, description) in REPORTS.items() if (data['path']/f).is_file()]})
            if path == '/api/report':
                name = query.get('file', [''])[0]
                if name not in REPORTS or not (data['path']/name).is_file():
                    raise AuthError('Report not found.', 404)
                payload = (data['path']/name).read_bytes()
                extra = {'Content-Disposition': f'attachment; filename="{Path(name).name}"'} if query.get('download') == ['1'] else None
                self.headers_for(200, 'text/plain; charset=utf-8', extra, len(payload))
                self.wfile.write(payload)
                return
            raise AuthError('Not found.', 404)
        except AuthError as exc:
            self.respond({'error': str(exc)}, exc.status)
        except ValueError:
            self.respond({'error': 'Invalid request parameter.'}, 400)
        except (OSError, sqlite3.Error, KeyError):
            self.respond({'error': 'These results are unavailable or incomplete. Try another completed run.'}, 500)

    def do_POST(self):
        try:
            self.check_origin()
            path = urlsplit(self.path).path
            body = self.body()
            if path in ('/api/auth/signup', '/api/auth/signin'):
                self.app.rate_limit(self.client_address[0], body.get('email'))
                if path.endswith('signup'):
                    uid = self.app.accounts.register(body.get('name'), body.get('email'), body.get('password'))
                else:
                    uid = self.app.accounts.login(body.get('email'), body.get('password'))
                old = self.token()
                if old:
                    self.app.accounts.logout(old)
                token = self.app.accounts.new_session(uid)
                return self.respond({'user': self.app.accounts.session(token)}, extra={'Set-Cookie': f'{COOKIE}={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_SECONDS}'})
            user = self.user()
            csrf = self.headers.get('X-CSRF-Token', '')
            if not hmac.compare_digest(csrf, user['csrf']):
                raise AuthError('Your session could not be verified. Refresh the page and try again.', 403)
            if path == '/api/auth/signout':
                self.app.accounts.logout(self.token())
                return self.respond({'ok': True}, extra={'Set-Cookie': f'{COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'})
            if path == '/api/auth/revoke-others':
                self.app.accounts.revoke_other_sessions(user['id'], self.token())
                return self.respond({'ok': True})
            if path == '/api/account':
                self.app.accounts.update(user['id'], body.get('name'), body.get('current_password'), body.get('new_password'), self.token())
                return self.respond({'user': self.app.accounts.session(self.token())})
            if path == '/api/jobs':
                key = self.app.jobs.start(user['id'], body.get('seed', 'oua-practice'))
                return self.respond({'job_id': key}, 202)
            match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})/cancel', path)
            if match:
                self.app.jobs.cancel(user['id'], match[1])
                return self.respond({'ok': True})
            raise AuthError('Not found.', 404)
        except AuthError as exc:
            self.respond({'error': str(exc)}, exc.status)
        except (OSError, sqlite3.Error):
            self.respond({'error': 'Local storage is unavailable. Check the terminal and retry.'}, 503)


def create_server(app, port=8000):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.app = app
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--pack', type=Path, default=ROOT/'data_pack')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'.local/web')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    try:
        server = create_server(None, args.port)
    except OSError as exc:
        parser.error(f'Cannot open port {args.port}: {exc}. Try --port 8001 if another app uses it.')
    try:
        app = WebApplication(pack=args.pack, data_dir=args.data_dir)
        server.app = app
    except Exception:
        server.server_close()
        raise
    print(f'STAGE website: http://127.0.0.1:{server.server_port}', flush=True)
    print('Press Ctrl+C to stop. Accounts and private runs are stored locally.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.jobs.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
