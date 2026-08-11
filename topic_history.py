"""
Topic History Manager - Tracks used topics and lesson contents to avoid repetition
"""

import json
import os
import re
from datetime import datetime
from config import TOPIC_HISTORY_FILE, HISTORY_RESET_AFTER


class TopicHistory:
    def __init__(self):
        self.history_file = TOPIC_HISTORY_FILE
        self.max_history = HISTORY_RESET_AFTER
        self.topics = []
        self.history = []
        self._load_history()

    def _load_history(self):
        """Load topic and detailed lesson history from file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.topics = data.get('topics', [])
                    self.history = data.get('history', [])
            except (json.JSONDecodeError, IOError):
                self.topics = []
                self.history = []
        else:
            self.topics = []
            self.history = []

    def _save_history(self):
        """Save topic and detailed lesson history to file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'topics': self.topics,
                    'history': self.history,
                    'count': len(self.topics),
                    'history_count': len(self.history)
                }, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving history: {e}")

    def _extract_summary(self, content: str) -> str:
        """Extract key examples, vocabulary, or rules from lesson markdown/text"""
        if not content:
            return ""

        # Extract italicized sentences _..._ (commonly used for examples in lessons)
        italics = re.findall(r'_(.*?)_', content)
        
        # Extract lines starting with emojis or bullet markers
        important_lines = []
        for line in content.split('\n'):
            line_str = line.strip()
            if any(line_str.startswith(icon) for icon in ['✍️', '✅', '🎯', '💡', '📝', '⭐', '🔥', '📚', '•', '-']):
                # Clean markdown characters for readable summary
                cleaned = line_str.replace('_', '').replace('*', '').strip()
                if cleaned:
                    important_lines.append(cleaned)

        parts = []
        if italics:
            part_italics = ", ".join([f"'{it.strip()}'" for it in italics[:5]])
            parts.append(f"Examples used: {part_italics}")
        if important_lines:
            part_lines = " | ".join(important_lines[:4])
            parts.append(f"Key points: {part_lines}")

        if parts:
            return " ".join(parts)

        # Fallback snippet
        clean_content = content.replace('\n', ' ').strip()
        return clean_content[:150]

    def add_lesson_entry(self, topic: str, content: str, summary: str = None):
        """Add detailed lesson record to history"""
        normalized = topic.lower().strip()
        if normalized not in [t.lower() for t in self.topics]:
            self.topics.append(topic)

        extracted_summary = summary or self._extract_summary(content)
        entry = {
            "topic": topic,
            "type": "lesson",
            "timestamp": datetime.now().isoformat(),
            "summary": extracted_summary,
            "content_snippet": content[:300] if content else ""
        }
        self.history.append(entry)
        self._save_history()
        print(f"Recorded lesson history for: {topic} (Total records: {len(self.history)})")

    def add_test_entry(self, topic_or_name: str, question: str, answer: str):
        """Add test record to history"""
        normalized = topic_or_name.lower().strip()
        if normalized not in [t.lower() for t in self.topics]:
            self.topics.append(topic_or_name)

        entry = {
            "topic": topic_or_name,
            "type": "test",
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": answer
        }
        self.history.append(entry)
        self._save_history()
        print(f"Recorded test history: {question[:30]}")

    def add_topic(self, topic: str):
        """Legacy compatibility method to add a topic name"""
        normalized = topic.lower().strip()
        if normalized not in [t.lower() for t in self.topics]:
            self.topics.append(topic)
            self._save_history()

    def get_history_summary(self, limit: int = 15) -> str:
        """Format recent history into concise text summary for AI prompt context"""
        if not self.history and not self.topics:
            return "No previous lessons recorded yet."

        summary_lines = []
        
        # Pull recent entries from self.history
        recent_entries = self.history[-limit:] if self.history else []
        for item in recent_entries:
            item_type = item.get('type', 'lesson')
            t_name = item.get('topic', 'General')
            if item_type == 'lesson':
                summ = item.get('summary', '')
                if summ:
                    summary_lines.append(f"• Lesson Topic: \"{t_name}\" | {summ}")
                else:
                    summary_lines.append(f"• Lesson Topic: \"{t_name}\"")
            elif item_type == 'test':
                q = item.get('question', '')
                a = item.get('answer', '')
                summary_lines.append(f"• Test Question: \"{q}\" (Answer: {a})")

        # Include remaining topic names if history was sparse
        if len(summary_lines) < limit and self.topics:
            used_topic_names = [t for t in self.topics if not any(t.lower() in line.lower() for line in summary_lines)]
            for t_name in used_topic_names[:(limit - len(summary_lines))]:
                summary_lines.append(f"• Used Topic: \"{t_name}\"")

        return "\n".join(summary_lines)

    def get_used_topics(self) -> list:
        """Get list of all used topics"""
        return self.topics.copy()

    def get_history_count(self) -> int:
        """Get current history count"""
        return len(self.topics)

    def get_detailed_history_count(self) -> int:
        """Get total detailed history records count"""
        return len(self.history)

    def should_reset(self) -> bool:
        """Check if history should be reset"""
        return len(self.topics) >= self.max_history

    def reset_history(self):
        """Manually reset history"""
        self.topics = []
        self.history = []
        self._save_history()
        print("Topic and lesson history has been reset!")

