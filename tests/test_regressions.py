"""Regression cases found by reviewing the assignment beyond the original happy path."""
import copy
import sqlite3
import unittest
from unittest.mock import patch
from datetime import timedelta
from test_agent import AgentFixture, event, AT
from stage_agent.common import iso
from stage_agent.goals import eligibility
from stage_agent.facts import resolve
from stage_agent.store import Store
from stage_agent.engine import Engine
from stage_agent.cohort import freeze_cohort, evaluate_cohort, summarize


class RegressionTests(AgentFixture):
    def test_mixed_timestamp_precision_is_ordered_by_instant(self):
        earlier = event('earlier', received_at='2026-10-01T06:00:00Z', app_dialect='d1')
        later = event('later', at=AT+timedelta(milliseconds=1),
                      received_at='2026-10-01T06:00:00.001Z', app_dialect='d2')
        state = resolve(self.pack, [earlier, later], 'U1', AT+timedelta(seconds=1))
        self.assertEqual(state['facts']['dialect']['value'], 'd2')

    def test_future_delivery_cannot_rewrite_past_fact_snapshot(self):
        late = event('late-paid', 'purchase_completed', AT-timedelta(hours=1),
                     deliver_at=iso(AT+timedelta(hours=1)), properties={'is_trial': False})
        state = resolve(self.pack, [late], 'U1', AT)
        self.assertEqual(state['facts']['subscription_status']['value'], 'never')
        after = resolve(self.pack, [late], 'U1', AT+timedelta(hours=1))
        self.assertEqual(after['facts']['subscription_status']['value'], 'active')

    def test_page_rows_have_catalogue_backed_genres(self):
        self.engine.decide(event())
        action = self.store.rows('actions')[0]
        for row in action['rows']:
            self.assertTrue(all(row['genre'] in self.pack.catalogue[t]['genres'].split('|') for t in row['title_ids']))

    def test_old_play_delivered_after_recent_play_does_not_qualify_for_resume(self):
        self.pack.goals['G07'] = {'goal_id': 'G07'}
        self.pack.episodes['slug1'] = [{'episode_id': 'ep1'}, {'episode_id': 'ep2'}]
        history = [event('recent', 'play_started', AT-timedelta(days=1),
                         properties={'title_id': 'T1', 'episode_id': 'ep1'}),
                   event('late', 'play_started', AT-timedelta(days=5),
                         properties={'title_id': 'T1', 'episode_id': 'ep1'})]
        history[-1]['deliver_at'] = iso(AT)
        for ordered in (history, list(reversed(history))):
            state = resolve(self.pack, ordered, 'U1', AT)
            self.assertFalse(eligibility(self.pack, state, ordered, 'G07', AT)[0])

    def test_real_sqlite_read_failure_is_durable_and_idempotent_after_restart(self):
        self.store.db.commit()
        self.store.db.execute('ALTER TABLE decisions RENAME TO inaccessible_decisions')
        self.store.db.commit()
        d = self.engine.decide(event())
        self.store.db.execute('ALTER TABLE inaccessible_decisions RENAME TO decisions')
        self.store.db.commit()
        self.assertEqual(d['no_action_reason'], 'primary_storage_failure')
        self.assertEqual(d['durability'], 'recovery_journal')
        self.assertFalse(self.store.rows('actions'))
        self.store.db.close()
        self.store = Store(self.path)
        self.engine = Engine(self.pack, self.store)
        self.assertEqual(d, self.engine.decide(event()))
        self.assertEqual(self.store.rows('decisions'), [d])

    def test_actual_sqlite_write_rejection_cannot_publish(self):
        self.store.db.execute("CREATE TRIGGER deny_actions BEFORE INSERT ON actions BEGIN SELECT RAISE(ABORT, 'write failed'); END")
        d = self.engine.decide(event())
        self.assertEqual(d['no_action_reason'], 'primary_storage_failure')
        self.assertFalse(self.store.rows('actions'))
        self.assertEqual(self.engine.decide(event()), d)
        self.assertEqual(self.engine.decide(event('second'))['action'], 'NO_ACTION')

    def test_release_failure_hides_staged_page_and_survives_restart(self):
        with patch.object(self.store, 'release', side_effect=sqlite3.OperationalError('release failed')):
            d = self.engine.decide(event())
        self.assertEqual(d['action'], 'NO_ACTION')
        self.assertFalse(self.store.rows('actions'))
        self.store.db.close()
        self.store = Store(self.path)
        self.engine = Engine(self.pack, self.store)
        self.assertFalse(self.store.rows('actions'))
        self.assertEqual(self.engine.decide(event()), d)

    def test_crash_before_release_becomes_abstention_not_published_page(self):
        # SystemExit represents an interrupted process, not a caught storage exception.
        with patch.object(self.store, 'release', side_effect=SystemExit):
            with self.assertRaises(SystemExit):
                self.engine.decide(event())
        self.assertFalse(self.store.rows('actions'))
        self.store.db.close()
        self.store = Store(self.path)
        self.engine = Engine(self.pack, self.store)
        d = self.engine.decide(event())
        self.assertEqual(d['no_action_reason'], 'interrupted_publication')
        self.assertFalse(self.store.rows('actions'))

    def test_live_page_revocation_rebuilds_without_withdrawn_title(self):
        self.engine.decide(event())
        original = self.store.rows('actions')[0]
        withdrawn = original['hero_title_id']
        control_at = AT+timedelta(minutes=1)
        self.engine.control({'type': 'title_withdrawn', 'at': iso(control_at), 'title_id': withdrawn})
        self.assertEqual(len(self.store.rows('revocations')), 1)
        page = self.engine.current_page('U1', control_at+timedelta(seconds=1))
        self.assertIsNotNone(page)
        ids = [page['hero_title_id']] + [i for row in page['rows'] for i in row['title_ids']]
        self.assertNotIn(withdrawn, ids)
        self.assertNotEqual(page['action_id'], original['action_id'])

    def test_revocation_falls_back_to_default_when_content_runs_out(self):
        self.engine.decide(event())
        original = self.store.rows('actions')[0]
        tid = original['hero_title_id']
        self.pack.catalogue = {tid: self.pack.catalogue[tid]}
        at = AT+timedelta(minutes=1)
        self.engine.control({'type': 'title_withdrawn', 'at': iso(at), 'title_id': tid})
        self.assertIsNone(self.engine.current_page('U1', at+timedelta(seconds=1)))

    def test_engine_correction_updates_only_affected_open_instances(self):
        base = {'started_at': iso(AT-timedelta(hours=1)), 'deadline': iso(AT+timedelta(days=2)),
                'success_signal': {'event': 'app_open'}, 'rule_version': 'v1'}
        g = {**copy.deepcopy(base), 'instance_id': 'U1:a:G03', 'user_id': 'U1', 'id': 'G03', 'status': 'open'}
        other = {**copy.deepcopy(base), 'instance_id': 'U2:a:G02', 'user_id': 'U2', 'id': 'G02', 'status': 'open'}
        closed = {**copy.deepcopy(base), 'instance_id': 'U3:a:G03', 'user_id': 'U3', 'id': 'G03', 'status': 'succeeded'}
        self.store.goals.extend([g, other, closed])
        unchanged = copy.deepcopy([other, closed])
        self.engine.control({'type': 'goal_rule_corrected', 'at': iso(AT), 'goal_id': 'G03',
                             'new_success': {'event': 'play_started'}})
        self.assertEqual(g['success_signal']['event'], 'play_started')
        self.assertEqual([other, closed], unchanged)
        self.assertEqual(self.store.rows('audit')[-1]['affected_instances'], ['U1:a:G03'])

    def test_baseline_assignment_and_missing_followup_are_not_failed_goals(self):
        self.pack.arms['U2'] = 'holdout'
        freeze_cohort(self.pack, self.store, AT)
        cohort = self.store.rows('cohort')
        self.assertEqual({r['user_id'] for r in cohort}, {'U1', 'U2'})
        before = copy.deepcopy(cohort)
        self.engine.decide(event())
        self.assertEqual(self.store.rows('cohort'), before)
        outcomes = evaluate_cohort(cohort, {}, [], self.pack, AT+timedelta(days=15), set())
        self.assertEqual([r['status'] for r in outcomes], ['inconclusive', 'inconclusive'])
        self.assertEqual(summarize(outcomes)['difference_bounds'], [-1, 1])

    def test_goal_measurement_has_correct_denominators_and_missing_bounds(self):
        rows = [{'arm': 'agent', 'status': 'succeeded'}, {'arm': 'agent', 'status': 'inconclusive'},
                {'arm': 'holdout', 'status': 'failed'}, {'arm': 'holdout', 'status': 'failed'}]
        result = summarize(rows)
        self.assertEqual(result['counts']['agent']['n'], 2)
        self.assertEqual(result['difference_bounds'], [.5, 1])
        self.assertIsNone(result['difference'])
