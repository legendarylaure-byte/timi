import time
import threading
from utils.firebase_status import get_firestore_client, is_agent_enabled, update_pipeline_status

class AgentControlListener:
    """Polls Firestore for agent control signals (pause/resume)."""
    
    def __init__(self, check_interval: int = 5):
        self.check_interval = check_interval
        self._running = False
        self._thread = None
        self._paused_agents = set()
    
    def start(self):
        """Start background polling thread."""
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        print("[CONTROL] Agent control listener started")
    
    def stop(self):
        """Stop background polling thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        print("[CONTROL] Agent control listener stopped")
    
    def _poll_loop(self):
        while self._running:
            try:
                db = get_firestore_client()
                agents_ref = db.collection('agent_status')
                docs = agents_ref.stream()
                
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
                
            except Exception as e:
                print(f"[CONTROL] Poll error: {e}")
            
            time.sleep(self.check_interval)
    
    def is_paused(self, agent_id: str) -> bool:
        """Check if an agent is currently paused."""
        return agent_id in self._paused_agents
