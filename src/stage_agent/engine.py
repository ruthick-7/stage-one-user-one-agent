"""One serialized owner per viewer; plans, reactions and atomic ledger publication."""
import copy
import hashlib
import sqlite3
import time
from collections import defaultdict
from datetime import timedelta
from .common import ts, iso, trigger_age
from .facts import resolve, value
from .goals import choose, judge, correct_rule, ASSUMPTIONS
from .planner import plan_page
from .provider import MockProvider, Budget
from .verifier import verify_action, verify_proposal


class Engine:
    def __init__(self, pack, store, max_model=8, max_tools=20):
        self.pack, self.store = pack, store
        self.max_model, self.max_tools = max_model, max_tools
        self.provider = MockProvider()
        self.dependencies = {}
        self.storage_failed = False
        self.timings = {}
        self.actions = defaultdict(list)
        for a in store.rows('actions'):
            self.actions[a['user_id']].append(a)

    def active(self, user):
        return next((g for g in self.store.goals if g['user_id'] == user and g['status'] == 'open'), None)

    def refresh(self, user, at):
        goal = self.active(user)
        if not goal:
            return
        events = self.store.history[user]
        status, evidence = judge(goal, events, self.pack, at)
        if status != 'inconclusive':
            goal.update(status=status, judged_at=iso(at), outcome_evidence=evidence)
        else:
            state = resolve(self.pack, events, user, at)
            sub = value(state, 'subscription_status')
            invalid = (goal['id'] == 'G04' and sub != 'trial_active' or
                       goal['id'] == 'G05' and sub != 'never' or
                       goal['id'] == 'G06' and sub != 'lapsed' or
                       goal['id'] in ('G08', 'G09') and sub != 'active')
            if invalid:
                goal.update(status='inconclusive', closed_reason='eligibility_changed', judged_at=iso(at))
                self.store.audit({'at': iso(at), 'type': 'goal_invalidated', 'instance_id': goal['instance_id'],
                                  'pending_message_count': 0, 'reason': 'subscription_changed'})

    def ingest(self, e):
        old_goal = self.active(e['user_id'])
        if self.store.ingest(e):
            at = ts(e.get('deliver_at', e['received_at']))
            self.refresh(e['user_id'], at)
            if old_goal and e['event'] in ('purchase_completed', 'subscription_renewed', 'subscription_lapsed') and not self.active(e['user_id']):
                state = resolve(self.pack, self.store.history[e['user_id']], e['user_id'], at)
                replacement = choose(self.pack, state, self.store.history[e['user_id']], e['user_id'], at, e['event_id'])
                if replacement:
                    self.store.goals.append(replacement)
                self.store.audit({'at': iso(at), 'type': 'billing_replan', 'user_id': e['user_id'],
                                  'old_instance': old_goal['instance_id'],
                                  'new_instance': replacement['instance_id'] if replacement else None})
                self.store.save_goals()
                self.store.db.commit()

    def control(self, c):
        at = ts(c['at'])
        # Settle goals with already-arrived evidence before deciding whether they are open.
        if c['type'] == 'goal_rule_corrected':
            for g in list(self.store.goals):
                if g['id'] == c['goal_id'] and g['status'] == 'open':
                    self.refresh(g['user_id'], at)
            affected = correct_rule(self.store.goals, self.pack, c)
            self.store.audit({'at': c['at'], 'type': c['type'], 'affected_instances': affected})
        elif c['type'] == 'title_withdrawn':
            self.pack.withdrawn[c['title_id']] = c['at']
            affected = [a for rows in self.actions.values() for a in rows
                        if a['type'] == 'home_page' and ts(a['published_at']) + timedelta(minutes=120) > at
                        and not a.get('revoked_at')
                        and c['title_id'] in [a.get('hero_title_id')] +
                        [t for r in a['rows'] for t in r['title_ids']]]
            for action in affected:
                self.store.revoke(action, c['at'], 'title_withdrawn:' + c['title_id'])
            self.store.db.commit()
            replacements = []
            for user in sorted({a['user_id'] for a in affected}):
                if not self.active(user):
                    continue  # serving falls back to default when there is no active plan
                state = resolve(self.pack, self.store.history[user], user, at)
                eid = 'withdraw-' + hashlib.sha256((user + c['title_id'] + c['at']).encode()).hexdigest()[:24]
                d = self.decide({'event_id': eid, 'user_id': user, 'event': 'catalogue_changed',
                                 'occurred_at': c['at'], 'sent_at': c['at'], 'received_at': c['at'],
                                 'deliver_at': c['at'], 'app_dialect': value(state, 'dialect'), 'properties': {}})
                if d['action'] == 'HOME_PAGE':
                    replacements.append(d['decision_id'])
            self.store.audit({'at': c['at'], 'type': c['type'],
                              'affected_live_pages': [a['action_id'] for a in affected],
                              'replacement_decisions': replacements, 'fallback': 'default_page_if_no_replacement'})
        elif c['type'] in ('dependency_unavailable', 'dependency_degraded'):
            self.dependencies[c['dependency']] = c
            self.store.audit(c)
        self.store.save_goals()
        self.store.db.commit()

    def unavailable(self, name, at):
        c = self.dependencies.get(name)
        return bool(c and ts(c['at']) <= at < ts(c['until']))

    def current_page(self, user, at):
        """Local serving contract: a revoked or expired page can never be shown."""
        if self.storage_failed:
            return None
        pages = [a for a in self.actions[user] if a['type'] == 'home_page'
                 and a.get('publication_state', 'ready') == 'ready'
                 and ts(a['published_at']) <= at < ts(a['published_at']) + timedelta(minutes=a['ttl_minutes'])
                 and (not a.get('revoked_at') or at < ts(a['revoked_at']))]
        page = max(pages, key=lambda a: a['published_at'], default=None)
        if not page:
            return None
        ids = [page['hero_title_id']] + [t for row in page['rows'] for t in row['title_ids']]
        return page if all(self.pack.available(t, at, page['dialect']) for t in ids) else None

    def decide(self, e):
        """Fail closed into a separate durable journal if any primary-store operation fails."""
        started = time.perf_counter()
        recovered = self.store.recovery.get(e['event_id'])
        if recovered:
            return recovered
        user = e['user_id']
        old_goals = copy.deepcopy([g for g in self.store.goals if g['user_id'] == user])
        old_history = list(self.store.history[user])
        old_actions = copy.deepcopy(self.actions[user])
        self._current_budget = None
        try:
            if self.storage_failed:
                raise sqlite3.OperationalError('primary_store_circuit_open_after_actual_failure')
            decision = self._decide(e)
            self.timings.setdefault(e['event_id'], {'trigger_event_id': e['event_id'],
                                    'durable_completion_ms': (time.perf_counter()-started)*1000})
            return decision
        except (sqlite3.Error, OSError) as exc:
            self.storage_failed = True
            try:
                self.store.db.rollback()
            except sqlite3.Error:
                pass
            self.store.goals[:] = [g for g in self.store.goals if g['user_id'] != user] + old_goals
            self.store.history[user] = old_history
            self.actions[user] = old_actions
            elapsed = (time.perf_counter() - started) * 1000
            d = {'decision_id': 'D-' + e['event_id'], 'viewer_id': user,
                 'trigger': {'event_id': e['event_id'], 'event': e['event'],
                             'received_at': e['received_at'], 'deliver_at': e['deliver_at'],
                             'event_age_s': trigger_age(e)},
                 'goal': None, 'action': 'NO_ACTION', 'no_action_reason': 'primary_storage_failure',
                 'dialect': {'used': None, 'source': None, 'conflicts': []}, 'content': [],
                 'facts': {}, 'conflicts': [], 'evidence': [], 'assumptions': [],
                 'confidence': 0, 'confidence_reason': 'Required primary state could not be trusted or persisted.',
                 'checks': {'passed': [], 'failed': ['primary_storage']}, 'fallback_used': True,
                 'proposal_rejections': [type(exc).__name__],
                 'model_calls': self._current_budget.model_calls if self._current_budget else 0,
                 'tool_calls': self._current_budget.tool_calls if self._current_budget else 0,
                 'decided_in_ms': elapsed,
                 'published_at': iso(ts(e['deliver_at']) + timedelta(milliseconds=elapsed)),
                 'status': 'ABSTAINED', 'publication_state': 'ready', 'durability': 'recovery_journal',
                 'rule_version': None}
            # Failure here is intentionally fatal: never claim durability if both stores fail.
            decision = self.store.recovery.save(d)
            self.timings.setdefault(e['event_id'], {'trigger_event_id': e['event_id'],
                                    'durable_completion_ms': (time.perf_counter()-started)*1000})
            return decision

    def _decide(self, e):
        previous = self.store.decision(e['event_id'])
        if previous:
            if previous.get('publication_state') == 'pending':
                raise sqlite3.OperationalError('interrupted publication requires recovery')
            return previous
        started = time.perf_counter()
        at, user = ts(e['deliver_at']), e['user_id']
        budget = Budget(self.max_model, self.max_tools)
        self._current_budget = budget
        self.ingest(e)
        state = resolve(self.pack, self.store.history[user], user, at, e)
        goal = self.active(user)
        no_action, fallback, failures = None, False, []
        page, proposal = None, None
        try:
            budget.take('tool')
            if self.unavailable('user_data_store', at):
                # Fail-fast circuit: the fixture's 8s reads exceed our 20ms local timeout.
                raise TimeoutError('user_data_store_circuit_open: injected_8s_latency')
            if trigger_age(e) > 600:
                no_action = 'stale_trigger_over_600s'
            else:
                if not goal:
                    goal = choose(self.pack, state, self.store.history[user], user, at, e['event_id'])
                    if goal:
                        self.store.goals.append(goal)
                # Always exercise named faults, even if an existing goal is retained.
                proposal = self.provider.propose(e, goal, self.pack.faults,
                                                self.unavailable('model_provider', at), budget)
                failures = verify_proposal(proposal, goal, self.pack, state,
                                           self.store.history[user], at, e['event_id'])
                if failures:
                    fallback = True
                if self.pack.arms.get(user) != 'agent':
                    no_action = 'randomized_holdout' if user in self.pack.arms else 'unknown_arm'
                elif not goal:
                    no_action = 'no_eligible_measurable_goal'
                else:
                    budget.take('tool')
                    page = plan_page(self.pack, state, goal, at)
                    if not page:
                        no_action = 'insufficient_valid_content'
        except (TimeoutError, ConnectionError, ValueError, TypeError) as exc:
            fallback = True
            failures.append(str(exc))
            # Data failures and exhausted tool budgets cannot safely publish.
            if ('user_data_store' in str(exc) or 'tool_budget' in str(exc)):
                no_action = 'required_data_unavailable'
            elif self.pack.arms.get(user) != 'agent':
                no_action = 'randomized_holdout'
            elif goal and trigger_age(e) <= 600 and budget.tool_calls < budget.max_tools:
                budget.take('tool')
                page = plan_page(self.pack, state, goal, at)
            else:
                no_action = 'safe_fallback_no_action'
        d_id = 'D-' + e['event_id']
        action = None
        checks = {'passed': [], 'failed': []}
        if page and not no_action:
            action = dict(page, action_id='A-' + e['event_id'], decision_id=d_id, user_id=user,
                          trigger_event_id=e['event_id'], published_at=iso(at))
            checks = verify_action(action, goal, self.pack, state, self.store.history[user], user, at,
                                   self.actions[user], e['event_id'])
            if checks['failed']:
                no_action, action = 'independent_verifier_rejected', None
        elif not no_action:
            no_action = 'safe_fallback_no_action'
        elapsed = (time.perf_counter() - started) * 1000
        published = at + timedelta(milliseconds=elapsed)
        # Recheck at measured publish time, including availability boundary crossings.
        if action:
            action['published_at'] = iso(published)
            checks = verify_action(action, goal, self.pack, state, self.store.history[user], user, published,
                                   self.actions[user], e['event_id'])
            if checks['failed'] or elapsed > 60000:
                no_action, action = 'publication_gate_rejected', None
        content = ([action['hero_title_id']] + [t for r in action['rows'] for t in r['title_ids']]) if action else []
        goal_evidence = []
        known_events = {x['event_id']: x for x in self.store.history[user]}
        for ref in (goal or {}).get('eligibility_evidence', []):
            event = known_events.get(ref.removeprefix('event:')) if ref.startswith('event:') else None
            when = event['received_at'] if event else (goal or {}).get('started_at', iso(at))
            goal_evidence.append({'source': ref, 'at': when,
                                  'age_s': max(0, (published-ts(when)).total_seconds()),
                                  'time_meaning': 'server_receipt' if event else 'checked_at_goal_commitment'})
        decision = {'decision_id': d_id, 'viewer_id': user,
                    'trigger': {'event_id': e['event_id'], 'event': e['event'], 'received_at': e['received_at'],
                                'deliver_at': e['deliver_at'], 'event_age_s': trigger_age(e)},
                    'goal': copy.deepcopy(goal), 'action': 'HOME_PAGE' if action else 'NO_ACTION',
                    'no_action_reason': no_action, 'dialect': {'used': value(state, 'dialect'),
                        'source': state['facts'].get('dialect', {}).get('source'),
                        'conflicts': [c for c in state['conflicts'] if c['fact'] == 'dialect']},
                    'facts': state['facts'], 'conflicts': state['conflicts'],
                    'content': ['title:' + t for t in content],
                    'evidence': list(state['facts'].values()) + goal_evidence +
                        [{'source': 'catalogue:' + t, 'at': iso(published), 'age_s': 0} for t in content],
                    'confidence': 0.65 if action else 0.3,
                    'confidence_reason': 'Heuristic evidence sufficiency, not a calibrated success probability; history is limited.',
                    'assumptions': ASSUMPTIONS,
                    'checks': checks, 'proposal_rejections': failures, 'fallback_used': fallback,
                    'configured_model_fault': self.pack.faults.get(e['event_id'], {}).get('fault'),
                    'fault_disposition': ('not_called_for_stale_or_unavailable_data' if
                        e['event_id'] in self.pack.faults and not budget.model_calls else None),
                    'model_calls': budget.model_calls, 'tool_calls': budget.tool_calls,
                    'decided_in_ms': elapsed, 'published_at': iso(published),
                    'status': 'PUBLISHED' if action else 'ABSTAINED', 'rule_version': goal['rule_version'] if goal else None}
        decision['publication_state'] = 'pending'
        if action:
            action['publication_state'] = 'pending'
        self.store.publish(e, decision, action)
        if action:
            self.actions[user].append(action)
        # Include ledger commit in trigger-to-publication timing, then persist that measured timestamp.
        elapsed = (time.perf_counter() - started) * 1000
        decision['decided_in_ms'] = elapsed
        decision['published_at'] = iso(at + timedelta(milliseconds=elapsed))
        if action:
            action['published_at'] = decision['published_at']
            final = verify_action(action, goal, self.pack, state, self.store.history[user], user,
                                  ts(action['published_at']), self.actions[user][:-1], e['event_id'])
            if final['failed'] or elapsed > 60000:
                # Local outbox has not been exported/sent; revoke before exposure.
                self.actions[user].pop()
                self.store.db.execute('DELETE FROM actions WHERE action_id=?', (action['action_id'],))
                decision.update(action='NO_ACTION', content=[], status='ABSTAINED',
                                no_action_reason='post_commit_publication_gate', checks=final)
                action = None
        self.store.release(e, decision, action)
        return decision
