"""
Topic History & Memory Manager - Complex Multi-Tiered Memory System
Tracks used topics, sliding cooldown windows, and registers all taught vocabulary,
phrasal verbs, idioms, and grammar concepts to permanently prevent repetition.
"""

import json
import os
import re
import sys
import io

# Fix Windows console encoding for Unicode/emojis
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'buffer') and not getattr(sys.stdout, '_is_utf8_wrapped', False):
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stdout._is_utf8_wrapped = True
        except Exception:
            pass

from datetime import datetime
from config import (
    TOPIC_HISTORY_FILE,
    RECENT_TOPICS_COOLDOWN,
    MEMORY_BLACKLIST_LIMIT,
    MEMORY_HISTORY_SUMMARY_LIMIT,
)


class TopicHistory:
    """
    Multi-Tier Memory Architecture:
    1. Cooldown Memory: Sliding window of recent topics (RECENT_TOPICS_COOLDOWN).
    2. Concept & Vocab Registers: Permanent categorized sets of taught items
       (vocabulary, idioms, phrasal_verbs, grammar_rules, collocations, mistakes).
    3. Lesson Archive: Full chronological history with extracted summaries.
    4. Test Archive: Questions and correct answers to prevent quiz duplicates.
    5. Anti-Repetition Blacklist Generator: Feeds forbidden items into AI prompts.
    """

    def __init__(self):
        self.history_file = TOPIC_HISTORY_FILE
        self.cooldown_window = RECENT_TOPICS_COOLDOWN
        self.blacklist_limit = MEMORY_BLACKLIST_LIMIT
        self.summary_limit = MEMORY_HISTORY_SUMMARY_LIMIT

        # Memory containers
        self.topics = []             # All topic strings ever used
        self.recent_topics = []      # Sliding FIFO cooldown queue of recent topics
        self.taught_items = {
            "vocabulary": [],
            "phrasal_verbs": [],
            "idioms": [],
            "grammar_rules": [],
            "collocations": [],
            "mistakes": [],
        }
        self.history = []            # Full lesson history records
        self.tests_history = []      # Full test questions and answers
        self.stats = {
            "total_lessons": 0,
            "total_tests": 0,
            "unique_items_taught": 0,
        }

        self._load_history()

    def _load_history(self):
        """Load and migrate existing history into multi-tier memory schema"""
        if not os.path.exists(self.history_file):
            self._save_history()
            return

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.topics = data.get("topics", [])
            self.recent_topics = data.get("recent_topics", self.topics[-self.cooldown_window:])
            self.history = data.get("history", [])
            self.tests_history = data.get("tests_history", [])

            # Load or initialize categorized registers
            saved_items = data.get("taught_items", {})
            for cat in ["vocabulary", "phrasal_verbs", "idioms", "grammar_rules", "collocations", "mistakes"]:
                self.taught_items[cat] = saved_items.get(cat, [])

            # Migrate legacy lessons if taught_items was empty
            if not any(self.taught_items.values()) and self.history:
                self._migrate_legacy_items()

            self.stats = data.get("stats", {
                "total_lessons": len([h for h in self.history if h.get("type") == "lesson"]),
                "total_tests": len(self.tests_history) + len([h for h in self.history if h.get("type") == "test"]),
                "unique_items_taught": sum(len(items) for items in self.taught_items.values()),
            })

        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading topic history ({e}). Initializing clean memory.")
            self._save_history()

    def _migrate_legacy_items(self):
        """Extract taught items from existing history entries to backfill memory registers"""
        for entry in self.history:
            if entry.get("type") == "lesson":
                content = entry.get("content_snippet", "") + " " + entry.get("summary", "")
                extracted = self.extract_target_items(content)
                self._register_target_items(extracted)

    def _save_history(self):
        """Atomically persist memory state to disk"""
        try:
            self.stats["total_lessons"] = len([h for h in self.history if h.get("type") == "lesson"])
            self.stats["total_tests"] = len(self.tests_history)
            self.stats["unique_items_taught"] = sum(len(items) for items in self.taught_items.values())

            data = {
                "topics": self.topics,
                "recent_topics": self.recent_topics,
                "taught_items": self.taught_items,
                "history": self.history,
                "tests_history": self.tests_history,
                "stats": self.stats,
                "count": len(self.topics),
                "history_count": len(self.history),
                "last_updated": datetime.now().isoformat(),
            }

            temp_file = f"{self.history_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, self.history_file)
        except IOError as e:
            print(f"Error saving topic history: {e}")

    def extract_target_items(self, text: str) -> list[str]:
        """
        Deep extraction of taught expressions, vocabulary, idioms, and rules.
        Recognizes TARGET_ITEMS lines, bold terms (**term** or <b>term</b>), and bullet points.
        """
        if not text:
            return []

        extracted = []

        # 1. Check for explicit TARGET_ITEMS: header
        target_line_match = re.search(r"TARGET_ITEMS:\s*(.*)", text, re.IGNORECASE)
        if target_line_match:
            raw_items = target_line_match.group(1).split(",")
            for it in raw_items:
                clean = it.strip().strip("'\"-•*")
                if clean and len(clean) > 1 and clean.lower() not in [e.lower() for e in extracted]:
                    extracted.append(clean)

        # 2. Extract bold markdown terms: **term** or <b>term</b>
        bold_markdown = re.findall(r"\*\*(.+?)\*\*", text)
        for term in bold_markdown:
            # Filter out non-content headings
            term_clean = term.strip().strip(":#-•")
            if term_clean and len(term_clean.split()) <= 5 and not any(
                skip in term_clean.lower()
                for skip in ["example", "pro tip", "rule", "tip", "note", "challenge", "mini quiz", "don't say"]
            ):
                if term_clean.lower() not in [e.lower() for e in extracted]:
                    extracted.append(term_clean)

        # 3. Extract HTML bold tags
        bold_html = re.findall(r"<b>(.+?)</b>", text, re.IGNORECASE)
        for term in bold_html:
            term_clean = term.strip().strip(":#-•")
            if term_clean and len(term_clean.split()) <= 5 and not any(
                skip in term_clean.lower()
                for skip in ["example", "pro tip", "rule", "tip", "note", "challenge", "mini quiz", "follow us"]
            ):
                if term_clean.lower() not in [e.lower() for e in extracted]:
                    extracted.append(term_clean)

        return extracted[:10]

    def _categorize_item(self, item: str) -> str:
        """Classify a taught expression into appropriate memory register"""
        lower = item.lower()
        words = lower.split()

        # Check for phrasal verb patterns (verb + preposition/particle)
        particles = {"up", "down", "out", "in", "off", "on", "away", "back", "over", "into", "through", "across"}
        if len(words) in (2, 3) and any(p in words[1:] for p in particles):
            return "phrasal_verbs"

        # Check for idioms (phrases with 3+ words or metaphors)
        if len(words) >= 3 and not any(k in lower for k in ["vs", "conditional", "tense", "passive", "clause"]):
            return "idioms"

        # Check for common mistakes & confusing pairs
        if "vs" in lower or "or" in lower or "/" in lower:
            return "mistakes"

        # Check for grammar points
        if any(g in lower for g in ["conditional", "perfect", "past", "present", "modal", "inversion", "passive", "gerund", "infinitive", "clause"]):
            return "grammar_rules"

        # Check for collocations
        if len(words) == 2:
            return "collocations"

        # Default to vocabulary
        return "vocabulary"

    def _register_target_items(self, items: list[str]):
        """Store target items into categorized long-term memory registers without duplicates"""
        for item in items:
            clean = item.strip().strip("\"'")
            if not clean or len(clean) < 2:
                continue

            category = self._categorize_item(clean)
            existing = [it.lower() for it in self.taught_items[category]]
            if clean.lower() not in existing:
                self.taught_items[category].append(clean)

    def _extract_summary(self, content: str) -> str:
        """Extract key examples, vocabulary, or rules from lesson text"""
        if not content:
            return ""

        italics = re.findall(r"_(.*?)_", content)
        important_lines = []
        for line in content.split("\n"):
            line_str = line.strip()
            if any(line_str.startswith(icon) for icon in ["✍️", "✅", "🎯", "💡", "📝", "⭐", "🔥", "📚", "•", "1.", "2.", "3."]):
                cleaned = line_str.replace("_", "").replace("*", "").strip()
                if cleaned and len(cleaned) < 120:
                    important_lines.append(cleaned)

        parts = []
        if italics:
            part_italics = ", ".join([f"'{it.strip()}'" for it in italics[:4]])
            parts.append(f"Examples: {part_italics}")
        if important_lines:
            part_lines = " | ".join(important_lines[:3])
            parts.append(f"Highlights: {part_lines}")

        if parts:
            return " ".join(parts)

        clean_content = content.replace("\n", " ").strip()
        return clean_content[:140]

    def add_lesson_entry(
        self,
        topic: str,
        content: str,
        category: str = "",
        target_items: list[str] = None,
        summary: str = None,
    ):
        """Add rich lesson record and register all taught concepts into long-term memory"""
        normalized = topic.strip()

        # 1. Update overall topics list
        if normalized.lower() not in [t.lower() for t in self.topics]:
            self.topics.append(normalized)

        # 2. Update sliding cooldown window
        self.recent_topics.append(normalized)
        if len(self.recent_topics) > self.cooldown_window:
            self.recent_topics = self.recent_topics[-self.cooldown_window:]

        # 3. Extract and register target items
        items = target_items or self.extract_target_items(content)
        self._register_target_items(items)

        # 4. Generate summary
        extracted_summary = summary or self._extract_summary(content)

        # 5. Append detailed archive entry
        entry = {
            "topic": normalized,
            "category": category,
            "type": "lesson",
            "timestamp": datetime.now().isoformat(),
            "target_items": items,
            "summary": extracted_summary,
            "content_snippet": content[:300] if content else "",
        }
        self.history.append(entry)
        self._save_history()

        print(
            f"[MEMORY] Recorded lesson: \"{normalized}\" | Taught Items: {items} "
            f"(Total Archive: {len(self.history)}, Unique Items: {self.stats['unique_items_taught']})"
        )

    def add_test_entry(self, topic_or_name: str, question: str, answer: str, category: str = ""):
        """Add test record to prevent question duplicate generation"""
        normalized = topic_or_name.strip()
        if normalized.lower() not in [t.lower() for t in self.topics]:
            self.topics.append(normalized)

        entry = {
            "topic": normalized,
            "category": category,
            "type": "test",
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": answer,
        }
        self.tests_history.append(entry)
        self.history.append(entry)
        self._save_history()
        print(f"[MEMORY] Recorded test: \"{question[:40]}...\" (Answer: {answer})")

    def get_lesson_memory_context(self, category: str = "", topic: str = "") -> str:
        """
        Builds a high-priority memory prompt injection containing:
        1. Explicit FORBIDDEN BLACKLIST of recently taught vocabulary, idioms, and rules.
        2. Summaries of recently posted lessons so the model covers fresh angles.
        """
        # Collect recent taught items across all categories for the blacklist
        all_taught = []
        for cat_name, item_list in self.taught_items.items():
            all_taught.extend(item_list[-25:])

        # Reverse so newest items are first, deduplicate
        seen = set()
        blacklist = []
        for it in reversed(all_taught):
            it_lower = it.lower()
            if it_lower not in seen and len(it) > 1:
                seen.add(it_lower)
                blacklist.append(it)
            if len(blacklist) >= self.blacklist_limit:
                break

        blacklist_str = ", ".join(f'"{item}"' for item in blacklist[:self.blacklist_limit])

        # Recent lesson summaries (last N entries)
        recent_lessons = [h for h in self.history if h.get("type") == "lesson"][-self.summary_limit:]
        summary_lines = []
        for item in recent_lessons:
            t = item.get("topic", "General")
            items = item.get("target_items", [])
            items_str = f" [Taught: {', '.join(items)}]" if items else ""
            summ = item.get("summary", "")
            summary_lines.append(f"• \"{t}\"{items_str} — {summ}")

        summaries_block = "\n".join(summary_lines) if summary_lines else "No previous lessons yet."

        context = f"""=== STRICT MEMORY & ANTI-REPETITION CONTEXT ===
1. FORBIDDEN WORDS / IDIOMS / EXPRESSIONS (ALREADY TAUGHT - ABSOLUTELY DO NOT TEACH OR USE THESE):
[{blacklist_str if blacklist_str else "None yet"}]

2. RECENT LESSONS COVERED IN THIS CHANNEL:
{summaries_block}

CRITICAL INSTRUCTION:
You MUST choose completely NEW, FRESH words, idioms, or grammar rules that are NOT in the forbidden list above!
Do NOT repeat any example sentences or concepts taught previously."""

        return context

    def get_test_memory_context(self) -> str:
        """Builds memory context for test generation to avoid duplicate quizzes"""
        recent_tests = self.tests_history[-20:]
        test_lines = []
        for t in recent_tests:
            q = t.get("question", "")
            a = t.get("answer", "")
            test_lines.append(f"• Question: \"{q}\" -> Answer: \"{a}\"")

        # Also get recent words taught
        recent_words = self.taught_items["vocabulary"][-20:] + self.taught_items["phrasal_verbs"][-20:]
        forbidden_test_items = ", ".join(f'"{w}"' for w in recent_words[:30])

        tests_block = "\n".join(test_lines) if test_lines else "No previous tests yet."

        return f"""=== PREVIOUS TESTS MEMORY (DO NOT REPEAT) ===
Already tested questions:
{tests_block}

Do NOT test or repeat the exact questions above. Choose a fresh question testing a different grammar rule, collocation, or preposition."""

    def is_topic_recent(self, topic: str) -> bool:
        """Check if topic is currently in the cooldown window"""
        norm = topic.strip().lower()
        return norm in [t.lower() for t in self.recent_topics]

    def get_used_topics(self) -> list[str]:
        """Get all topics ever used"""
        return self.topics.copy()

    def get_recent_topics(self) -> list[str]:
        """Get list of topics currently in cooldown"""
        return self.recent_topics.copy()

    def reset_cooldown(self):
        """
        Soft reset: clears the sliding topic cooldown buffer so topics can cycle again,
        while strictly preserving all taught vocabulary, idioms, and history registers.
        """
        self.recent_topics = []
        self._save_history()
        print("Topic cooldown buffer has been reset. Long-term memory and taught items preserved!")

    def reset_history(self, full_wipe: bool = False):
        """
        Reset memory. By default, performs a soft cooldown reset to preserve taught items.
        If full_wipe is True, clears all memory.
        """
        if full_wipe:
            self.topics = []
            self.recent_topics = []
            self.history = []
            self.tests_history = []
            for k in self.taught_items:
                self.taught_items[k] = []
            self.stats = {
                "total_lessons": 0,
                "total_tests": 0,
                "unique_items_taught": 0,
            }
            self._save_history()
            print("Full memory wipe executed.")
        else:
            self.reset_cooldown()

    def get_stats(self) -> dict:
        """Return comprehensive memory statistics"""
        return {
            "total_lessons": len([h for h in self.history if h.get("type") == "lesson"]),
            "total_tests": len(self.tests_history),
            "topics_in_cooldown": len(self.recent_topics),
            "total_topics_ever": len(self.topics),
            "cooldown_limit": self.cooldown_window,
            "unique_items_taught": sum(len(items) for items in self.taught_items.values()),
            "vocabulary_count": len(self.taught_items["vocabulary"]),
            "phrasal_verbs_count": len(self.taught_items["phrasal_verbs"]),
            "idioms_count": len(self.taught_items["idioms"]),
            "grammar_rules_count": len(self.taught_items["grammar_rules"]),
            "collocations_count": len(self.taught_items["collocations"]),
            "mistakes_count": len(self.taught_items["mistakes"]),
        }
