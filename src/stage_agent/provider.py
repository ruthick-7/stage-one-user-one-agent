"""Local provider contract with bounded deterministic fault injection. No external calls."""
import json
import time
from dataclasses import dataclass


@dataclass
class Budget:
    max_model: int = 8
    max_tools: int = 20
    model_calls: int = 0
    tool_calls: int = 0

    def take(self, kind):
        attr = 'model_calls' if kind == 'model' else 'tool_calls'
        limit = self.max_model if kind == 'model' else self.max_tools
        if getattr(self, attr) >= limit:
            raise TimeoutError(kind + '_budget_exhausted')
        setattr(self, attr, getattr(self, attr) + 1)


class MockProvider:
    def propose(self, trigger, candidate, faults, unavailable, budget, timeout_s=0.02):
        budget.take('model')
        if unavailable:
            raise ConnectionError('model_provider:503')
        fault = faults.get(trigger['event_id'])
        if fault:
            if fault['fault'] == 'timeout':
                time.sleep(min(timeout_s, fault.get('seconds', timeout_s)))
                raise TimeoutError('model_timeout_bounded')
            output = fault['model_output']
            return json.loads(output) if isinstance(output, str) else output
        return {'goal_id': candidate['id'] if candidate else None,
                'evidence': candidate['eligibility_evidence'] if candidate else [], 'eligible': bool(candidate)}
