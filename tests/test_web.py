"""HTTP tests for the local website: authentication, isolation and artifact-backed results."""
import hashlib
import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from stage_agent.web_server import WebApplication, create_server

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = 'Test-account-password-42'


class WebsiteTests(unittest.TestCase):
    def setUp(self):
        self.logs = patch('stage_agent.web_server.Handler.log_message')
        self.logs.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.app = WebApplication(ROOT, pack=Path(self.tmp.name)/'missing-pack', data_dir=Path(self.tmp.name)/'web')
        self.server = create_server(self.app, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port
        self.cookie, self.csrf = '', ''

    def tearDown(self):
        self.app.jobs.shutdown()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()
        self.logs.stop()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        sent = {'Content-Type':'application/json', 'Cookie':self.cookie}
        if self.csrf:
            sent['X-CSRF-Token'] = self.csrf
        sent.update(headers or {})
        conn.request(method,path,json.dumps(body).encode() if body is not None else None,sent)
        response = conn.getresponse()
        payload, result_headers, status = response.read(), dict(response.getheaders()), response.status
        conn.close()
        if result_headers.get('Content-Type','').startswith('application/json'):
            payload = json.loads(payload)
        return status,payload,result_headers

    def signup(self, email='owner@example.test', name='Test Owner'):
        status,data,headers = self.request('POST','/api/auth/signup',{'name':name,'email':email,'password':PASSWORD})
        self.assertEqual(status,200,data)
        self.cookie = headers['Set-Cookie'].split(';')[0]
        self.csrf = data['user']['csrf']
        return data,headers

    def test_public_assets_and_protected_data(self):
        self.assertEqual(self.request('GET','/')[0],200)
        self.assertEqual(self.request('GET','/assets/app.js')[0],200)
        self.assertEqual(self.request('GET','/api/summary')[0],401)

    def test_signup_hashes_password_and_stores_only_hashed_session(self):
        data,headers = self.signup()
        self.assertIn('HttpOnly',headers['Set-Cookie'])
        self.assertIn('SameSite=Lax',headers['Set-Cookie'])
        self.assertNotIn('password',data['user'])
        with self.app.accounts.connection() as db:
            user = db.execute('SELECT password_hash FROM users').fetchone()
            token = db.execute('SELECT token_hash FROM sessions').fetchone()
        self.assertNotEqual(user['password_hash'],PASSWORD)
        raw = self.cookie.split('=',1)[1]
        self.assertEqual(token['token_hash'],hashlib.sha256(raw.encode()).hexdigest())
        self.assertEqual(self.request('GET','/api/auth/me')[1]['user']['email'],'owner@example.test')

    def test_duplicate_email_weak_password_and_wrong_login(self):
        self.assertEqual(self.request('POST','/api/auth/signup',{'name':'Owner','email':'owner@example.test','password':'short'})[0],400)
        self.signup()
        self.assertEqual(self.request('POST','/api/auth/signup',{'name':'Another','email':'OWNER@example.test','password':PASSWORD})[0],409)
        self.assertEqual(self.request('POST','/api/auth/signin',{'email':'owner@example.test','password':'incorrect'})[0],401)

    def test_csrf_origin_and_signout(self):
        self.signup()
        self.assertEqual(self.request('POST','/api/auth/signout',{}, {'X-CSRF-Token':''})[0],403)
        self.assertEqual(self.request('POST','/api/auth/signout',{}, {'Origin':'https://untrusted.example'})[0],403)
        self.assertEqual(self.request('POST','/api/auth/signout',{})[0],200)
        self.assertEqual(self.request('GET','/api/auth/me')[0],401)

    def test_expired_session_is_rejected(self):
        self.signup()
        with self.app.accounts.connection() as db:
            db.execute('UPDATE sessions SET expires_at=?',(int(time.time())-1,))
        self.assertEqual(self.request('GET','/api/auth/me')[0],401)

    def test_account_and_session_survive_application_recreation(self):
        self.signup()
        self.app = WebApplication(ROOT, pack=Path(self.tmp.name)/'missing-pack', data_dir=Path(self.tmp.name)/'web')
        self.server.app = self.app
        status, data, _ = self.request('GET','/api/auth/me')
        self.assertEqual(status,200)
        self.assertEqual(data['user']['email'],'owner@example.test')
        self.assertEqual(data['user']['csrf'],self.csrf)

    def test_password_change_revokes_other_sessions_and_new_login_works(self):
        data,_ = self.signup()
        second = self.app.accounts.new_session(data['user']['id'])
        self.assertEqual(self.request('POST','/api/account',{'name':'Updated Owner','current_password':'wrong','new_password':'Changed-password-42'})[0],403)
        self.assertEqual(self.request('POST','/api/account',{'name':'Updated Owner','current_password':PASSWORD,'new_password':'Changed-password-42'})[0],200)
        self.assertIsNone(self.app.accounts.session(second))
        self.assertEqual(self.request('GET','/api/auth/me')[1]['user']['name'],'Updated Owner')
        self.assertEqual(self.request('POST','/api/auth/signin',{'email':'owner@example.test','password':PASSWORD})[0],401)
        self.assertEqual(self.request('POST','/api/auth/signin',{'email':'owner@example.test','password':'Changed-password-42'})[0],200)

    def test_sample_dashboard_search_and_report_allowlist(self):
        self.signup()
        status,summary,_ = self.request('GET','/api/summary')
        self.assertEqual(status,200)
        self.assertEqual(summary['decisions'],2679)
        self.assertEqual(summary['actions'],917)
        self.assertEqual(summary['simulator']['policy_problem_count'],0)
        rows = self.request('GET','/api/viewers?q=U-02825')[1]
        self.assertEqual([r['id'] for r in rows['viewers']],['U-02825'])
        viewer = self.request('GET','/api/viewers/U-02825')[1]
        self.assertTrue(viewer['decisions'])
        self.assertEqual(self.request('GET','/api/report?file=../../.local/accounts.sqlite3')[0],404)
        status,content,headers = self.request('GET','/api/report?file=impact_report.md&download=1')
        self.assertEqual(status,200)
        self.assertIn(b'baseline-goal',content)
        self.assertIn('attachment',headers['Content-Disposition'])

    def test_completed_runs_and_jobs_are_isolated_by_owner(self):
        first,_ = self.signup()
        key='a'*32
        with self.app.accounts.connection() as db:
            db.execute('INSERT INTO jobs(id,user_id,status,seed,output_path,log_path,created_at) VALUES(?,?,?,?,?,?,?)',
                       (key,first['user']['id'],'completed','test',str(ROOT/'sample_run'),'unused',int(time.time())))
        self.assertEqual(self.request('GET','/api/summary?run='+key)[0],200)
        self.signup('other@example.test','Other Owner')
        self.assertEqual(self.request('GET','/api/summary?run='+key)[0],404)
        self.assertEqual(self.request('GET','/api/jobs')[1]['jobs'],[])
        self.assertEqual(self.request('POST','/api/jobs/'+key+'/cancel',{})[0],404)

    def test_replay_requires_pack_and_rejects_command_injection(self):
        self.signup()
        self.assertEqual(self.request('POST','/api/jobs',{'seed':'hello; touch hacked'})[0],400)
        self.assertEqual(self.request('POST','/api/jobs',{'seed':'valid-seed'})[0],409)
        self.assertFalse(self.app.jobs.available())

    def test_auth_attempts_are_rate_limited(self):
        for _ in range(8):
            status,_,_ = self.request('POST','/api/auth/signin',{'email':'missing@example.test','password':PASSWORD})
            self.assertEqual(status,401)
        self.assertEqual(self.request('POST','/api/auth/signin',{'email':'missing@example.test','password':PASSWORD})[0],429)


if __name__=='__main__':
    unittest.main()
