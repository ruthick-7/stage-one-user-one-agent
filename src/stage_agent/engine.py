"""One serialized owner per viewer; plans, reactions and atomic ledger publication."""
import copy
import json
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
            affected = [a['action_id'] for rows in self.actions.values() for a in rows
                        if a['type'] == 'home_page' and ts(a['published_at']) + timedelta(minutes=120) > at
                        and c['title_id'] in [a.get('hero_title_id')] +
                        [t for r in a['rows'] for t in r['title_ids']]]
            self.store.audit({'at': c['at'], 'type': c['type'], 'affected_live_pages': affected,
                              'note': 'Future publication blocked; existing pages require platform revocation (not implemented).'})
        elif c['type'] in ('dependency_unavailable', 'dependency_degraded'):
            self.dependencies[c['dependency']] = c
            self.store.audit(c)
        self.store.save_goals()
        self.store.db.commit()

    def unavailable(self, name, at):
        c = self.dependencies.get(name)
        return bool(c and ts(c['at']) <= at < ts(c['until']))

    def decide(self, e):
        previous = self.store.decision(e['event_id'])
        if previous:
            return previous
        started = time.perf_counter()
        at, user = ts(e['deliver_at']), e['user_id']
        budget = Budget(self.max_model, self.max_tools)
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
        decision = {'decision_id': d_id, 'viewer_id': user,
                    'trigger': {'event_id': e['event_id'], 'event': e['event'], 'received_at': e['received_at'],
                                'deliver_at': e['deliver_at'], 'event_age_s': trigger_age(e)},
                    'goal': copy.deepcopy(goal), 'action': 'HOME_PAGE' if action else 'NO_ACTION',
                    'no_action_reason': no_action, 'dialect': {'used': value(state, 'dialect'),
                        'source': state['facts'].get('dialect', {}).get('source'),
                        'conflicts': [c for c in state['conflicts'] if c['fact'] == 'dialect']},
                    'facts': state['facts'], 'conflicts': state['conflicts'],
                    'content': ['title:' + t for t in content],
                    'evidence': list(state['facts'].values()) +
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
            else:
                self.store.db.execute('UPDATE actions SET payload=? WHERE action_id=?',
                                      (json.dumps(action), action['action_id']))
        self.store.db.execute('UPDATE decisions SET payload=? WHERE trigger_id=?',
                              (json.dumps(decision), e['event_id']))
        self.store.db.commit()
        return decision
