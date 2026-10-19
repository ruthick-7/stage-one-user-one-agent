"""Local accounts and opaque cookie sessions; credentials never enter replay artifacts."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

ITERATIONS = 600_000
SESSION_SECONDS = 7 * 24 * 3600


class AuthError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS)
    return salt.hex() + ':' + digest.hex()


def password_matches(password, encoded):
    salt, _ = encoded.split(':')
    return hmac.compare_digest(password_hash(password, bytes.fromhex(salt)), encoded)


def validate_password(password):
    if not isinstance(password, str) or not 10 <= len(password) <= 128:
        raise AuthError('Use a password between 10 and 128 characters.')


def validate_name(name):
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 60 or any(ord(c) < 32 for c in name):
        raise AuthError('Enter a name between 2 and 60 characters.')
    return name.strip()


class Accounts:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, created_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(
                token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, status TEXT NOT NULL,
                seed TEXT NOT NULL, output_path TEXT NOT NULL, log_path TEXT NOT NULL,
                created_at INTEGER NOT NULL, finished_at INTEGER, error TEXT);
            ''')
            db.execute("UPDATE jobs SET status='failed', error='The website restarted before this run finished.', finished_at=? WHERE status IN ('running','queued')", (int(time.time()),))

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def email(value):
        if not isinstance(value, str) or len(value) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value.strip()):
            raise AuthError('Enter a valid email address.')
        return value.strip().casefold()

    def register(self, name, email, password):
        name, email = validate_name(name), self.email(email)
        validate_password(password)
        encoded = password_hash(password)
        try:
            with self.connection() as db:
                cur = db.execute('INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)',
                                 (name, email, encoded, int(time.time())))
                return cur.lastrowid
        except sqlite3.IntegrityError:
            raise AuthError('An account with this email already exists. Sign in instead.', 409) from None

    def login(self, email, password):
        email = self.email(email)
        if not isinstance(password, str) or len(password) > 128:
            raise AuthError('Email or password is incorrect.', 401)
        with self.connection() as db:
            row = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        encoded = row['password_hash'] if row else ('00'*16 + ':' + '00'*32)
        valid = password_matches(password, encoded)
        if not row or not valid:
            raise AuthError('Email or password is incorrect.', 401)
        return row['id']

    def new_session(self, user_id):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE expires_at<=?', (int(time.time()),))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), user_id, csrf, int(time.time())+SESSION_SECONDS))
        return token

    def session(self, token):
        if not token or len(token) > 128:
            return None
        with self.connection() as db:
            row = db.execute('''SELECT users.id,users.name,users.email,users.created_at,sessions.csrf
                FROM sessions JOIN users ON sessions.user_id=users.id
                WHERE token_hash=? AND expires_at>?''',
                (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        return dict(row) if row else None

    def logout(self, token):
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def update(self, user_id, name, current_password=None, new_password=None, current_token=None):
        name = validate_name(name)
        encoded = None
        if new_password:
            validate_password(new_password)
            with self.connection() as db:
                old = db.execute('SELECT password_hash FROM users WHERE id=?', (user_id,)).fetchone()
            if not isinstance(current_password, str) or len(current_password) > 128 or not password_matches(current_password, old['password_hash']):
                raise AuthError('Your current password is incorrect.', 403)
            encoded = password_hash(new_password)
        with self.connection() as db:
            db.execute('UPDATE users SET name=? WHERE id=?', (name, user_id))
            if encoded:
                db.execute('UPDATE users SET password_hash=? WHERE id=?', (encoded, user_id))
                db.execute('DELETE FROM sessions WHERE user_id=? AND token_hash<>?',
                           (user_id, hashlib.sha256(current_token.encode()).hexdigest()))

    def revoke_other_sessions(self, user_id, token):
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE user_id=? AND token_hash<>?',
                       (user_id, hashlib.sha256(token.encode()).hexdigest()))
