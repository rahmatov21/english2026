"""
Topic History Manager - Tracks used topics to avoid repetition
"""

import json
import os
from config import TOPIC_HISTORY_FILE, HISTORY_RESET_AFTER


class TopicHistory:
    def __init__(self):
        self.history_file = TOPIC_HISTORY_FILE
        self.max_history = HISTORY_RESET_AFTER
        self.topics = self._load_history()

    def _load_history(self) -> list:
        """Load topic history from file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('topics', [])
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save_history(self):
        """Save topic history to file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'topics': self.topics,
                    'count': len(self.topics)
                }, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving history: {e}")

    def add_topic(self, topic: str):
        """Add a new topic to history"""
        # Normalize topic for comparison
        normalized = topic.lower().strip()
        
        # History will no longer be reset automatically to ensure no repetition
        if len(self.topics) >= self.max_history:
            # We just log it now, but do not reset
            pass
        
        # Add topic if not already in history
        if normalized not in [t.lower() for t in self.topics]:
            self.topics.append(topic)
            self._save_history()
            print(f"Added topic: {topic} (Total: {len(self.topics)}/{self.max_history})")

    def get_used_topics(self) -> list:
        """Get list of all used topics"""
        return self.topics.copy()

    def get_history_count(self) -> int:
        """Get current history count"""
        return len(self.topics)

    def should_reset(self) -> bool:
        """Check if history should be reset"""
        return len(self.topics) >= self.max_history

    def reset_history(self):
        """Manually reset history"""
        self.topics = []
        self._save_history()
        print("Topic history has been reset!")
