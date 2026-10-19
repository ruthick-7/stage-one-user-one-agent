"""Independent fsynced abstention journal when the primary SQLite ledger fails."""
import hashlib
import json
import os
import tempfile
from pathlib import Path


class RecoveryJournal:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path(self, trigger_id):
        key = hashlib.sha256(trigger_id.encode()).hexdigest()
        return self.directory / (key + '.json')

    def get(self, trigger_id):
        path = self.path(trigger_id)
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def save(self, decision):
        target = self.path(decision['trigger']['event_id'])
        if target.exists():
            return self.get(decision['trigger']['event_id'])
        fd, temporary = tempfile.mkstemp(dir=self.directory, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(decision, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return decision

    def rows(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(self.directory.glob('*.json'))]
