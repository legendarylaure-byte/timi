import time
import random
import threading
from utils.firebase_status import get_firestore_client, is_agent_enabled, update_pipeline_status

class AgentControlListener:
    """Polls Firestore for agent control signals (pause/resume) and pipeline triggers."""

    def __init__(self, check_interval: int = 15, max_backoff: int = 60):
        self.check_interval = check_interval
        self.max_backoff = max_backoff
        self._running = False
        self._thread = None
        self._paused_agents = set()
        self._on_trigger = None
        self._consecutive_errors = 0
        self._last_error_time = 0

    def set_trigger_handler(self, handler):
        """Set callback for pipeline triggers from dashboard."""
        self._on_trigger = handler

    def start(self):
        """Start background polling thread."""
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        print(f"[CONTROL] Agent control listener started (interval: {self.check_interval}s)")

    def stop(self):
        """Stop background polling thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        print("[CONTROL] Agent control listener stopped")

    def _poll_loop(self):
        while self._running:
            try:
                self._check_agent_pauses()
                self._check_pipeline_triggers()
                self._consecutive_errors = 0
            except Exception as e:
                self._consecutive_errors += 1
                self._last_error_time = time.time()
                backoff = min(self.max_backoff, self.check_interval * (2 ** (self._consecutive_errors - 1)))
                jitter = random.uniform(0, backoff * 0.3)
                sleep_time = backoff + jitter
                print(f"[CONTROL] Error (#{self._consecutive_errors}), backing off {sleep_time:.1f}s: {type(e).__name__}")
                time.sleep(sleep_time)
                continue

            time.sleep(self.check_interval)

    def _check_agent_pauses(self):
        db = get_firestore_client()
        agents_ref = db.collection('agent_status')
        docs = agents_ref.stream(timeout=30)

        for doc in docs:
            data = doc.to_dict()
            agent_id = doc.id
            enabled = data.get('enabled', True)

            if not enabled and agent_id not in self._paused_agents:
                self._paused_agents.add(agent_id)
                print(f"[CONTROL] Agent '{agent_id}' PAUSED by user")
            elif enabled and agent_id in self._paused_agents:
                self._paused_agents.discard(agent_id)
                print(f"[CONTROL] Agent '{agent_id}' RESUMED by user")

    def _check_pipeline_triggers(self):
        """Check for pipeline run requests from the dashboard."""
        db = get_firestore_client()
        triggers_ref = db.collection('pipeline_triggers')
        docs = list(triggers_ref.stream(timeout=30))

        pending = [d for d in docs if d.to_dict().get('status') == 'pending']
        if not pending:
            return

        pending.sort(key=lambda d: d.to_dict().get('created_at', None) or __import__('datetime').datetime.min)
        trigger_doc = pending[0]
        trigger_data = trigger_doc.to_dict()
        trigger_id = trigger_doc.id

        topic = trigger_data.get('topic', '')
        category = trigger_data.get('category', 'science')
        format_type = trigger_data.get('format', 'shorts')
        publish_at = trigger_data.get('publish_at', None)

        print(f"[CONTROL] Pipeline trigger received: {format_type} - {topic}{f' (scheduled: {publish_at})' if publish_at else ''}")

        trigger_doc.reference.update({'status': 'processing', 'started_at': __import__('time').time()})

        if self._on_trigger:
            self._on_trigger(topic, category, format_type, trigger_id, publish_at)

    def is_paused(self, agent_id: str) -> bool:
        """Check if an agent is currently paused."""
        return agent_id in self._paused_agents
