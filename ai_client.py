"""
OpenRouter AI Client for generating high-impact English teaching content
Features complex anti-repetition memory context injection, structured lesson parsing,
and multi-tier model/key fallback architecture.
"""

import sys
import io
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

import asyncio
import json
import re
import urllib.request
import urllib.error
from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_API_KEY_2,
    OPENROUTER_MODEL,
    OPENROUTER_MODEL_2,
    OPENROUTER_MODEL_3,
    OPENROUTER_BASE_URL,
)


class AIClient:
    def __init__(self):
        self.openrouter_api_key = OPENROUTER_API_KEY
        self.openrouter_api_key_2 = OPENROUTER_API_KEY_2
        self.openrouter_model = OPENROUTER_MODEL
        self.openrouter_model_2 = OPENROUTER_MODEL_2
        self.openrouter_model_3 = OPENROUTER_MODEL_3
        self.openrouter_base_url = OPENROUTER_BASE_URL

        # Dynamic fallback pool of verified active models
        self.fallback_models = [
            self.openrouter_model,
            self.openrouter_model_2,
            self.openrouter_model_3,
            "liquid/lfm-2.5-2.6b:free",
        ]

    async def generate_lesson(self, topic: str, category: str = "", memory_context: str = "") -> dict:
        """
        Generate a high-impact, professional English lesson with anti-repetition memory.
        Enforces a structured teaching format: Hook -> 3 Core Breakdown Items -> Pro Tip -> Micro-Challenge.
        """
        category_hint = f"Category: {category}\n" if category else ""
        memory_block = f"\n{memory_context}\n" if memory_context else ""

        prompt = f"""You are a master English teacher and linguistic expert creating premium educational content for a Telegram channel called "Improve Your English".

{category_hint}Topic to teach:
"{topic}"
{memory_block}
YOUR MISSION:
Deliver a comprehensive, ultra-engaging, bite-sized English lesson about this topic. It must sound natural, modern, and practical—the way native speakers actually talk and write.

STRICT VISUAL STRUCTURE & CONTENT REQUIREMENTS:

1. TOPIC_TITLE: A catchy, polished title with 1-2 relevant emojis (e.g. 🚀 Master Precision Adjectives).
2. TARGET_ITEMS: A comma-separated list of the exact 3 specific words, idioms, or grammar rules taught in this lesson (e.g., ecstatic, petrified, furious).
3. LESSON BODY:
   - 🎯 **The Hook**: 1-2 engaging sentences explaining the real-world context, why this matters, or a common misconception learners make.
   - 📚 **3 Distinct Core Teachings**:
     Present exactly 3 clear items, each structured as follows:
     • **[Target Word / Phrase / Rule]** — Clear, punchy definition or meaning.
       ✍️ Contextual example sentence using Markdown italics `_like this_`.
       ❌ **Don't say:** `_Common learner mistake_`
       ✅ **Instead say:** `_Natural native phrasing_`
   - 💡 **Pro Tip & Memory Hack**: A clever mnemonic, nuance, formality level (Casual vs Formal), or preposition trap starting with 💡 or 🔥.
   - 💬 **Your Turn (Challenge)**: A short fill-in-the-blank or challenge question encouraging learners to practice (e.g. "Complete this sentence in the comments: _..._ 👇").

CRITICAL RULES:
- 100% ENGLISH ONLY: No Russian, Uzbek, Chinese, or other translations under any circumstances.
- FORMATTING: Use Markdown `**bold**` for key terms and `_italics_` for example sentences and dialogues.
- VISUAL ELEGANCE: Use tasteful emojis (🎯, 📚, ✍️, ✅, ❌, 💡, 💬) at the start of sections to create a clean, modern Telegram post layout.
- ANTI-REPETITION: Never repeat words, idioms, or rules from the forbidden list in the memory block.

Format your response EXACTLY like this (do NOT use square brackets in your output):
TOPIC_TITLE: 🚀 Master Precision Adjectives
TARGET_ITEMS: Ecstatic, Petrified, Furious
LESSON:
🎯 **The Hook**: Stop relying on 'very' to express strong emotions!
📚 **3 Distinct Core Teachings**:
• **Ecstatic** — Overwhelmingly happy and joyful.
  ✍️ _She was ecstatic when she received her university acceptance letter._ 🎓
  ❌ **Don't say:** _She was very happy about the letter._
  ✅ **Instead say:** _She was utterly ecstatic!_

• **Petrified** — So frightened that you are unable to move.
  ✍️ _Mark stood petrified as the thunderstorm shook the building._ ⚡
  ❌ **Don't say:** _He was very, very scared._
  ✅ **Instead say:** _He was petrified!_

• **Furious** — Extremely angry and enraged.
  ✍️ _The manager was furious about the missed delivery deadline._ ⏰
  ❌ **Don't say:** _He was very angry with the team._
  ✅ **Instead say:** _He was absolutely furious!_

💡 **Pro Tip & Memory Hack:**
Notice the collocations! We pair these extreme adjectives with 'utterly' or 'absolutely', NEVER with 'very' (e.g. absolutely ecstatic ✅, very ecstatic ❌). 🔥

💬 **Your Turn:**
Which word best describes how you feel right before a big job interview? Write a sentence below! 👇"""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a master English educator creating world-class lessons for Telegram. "
                    "Your content is 100% in English, visually organized with tasteful emojis, "
                    "pedagogically rigorous, and completely free of repetitive clichés. "
                    "Always output the requested TOPIC_TITLE, TARGET_ITEMS, and LESSON markers."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        content = await asyncio.to_thread(self._get_ai_response, messages)
        if not content:
            print("AI generation failed for lesson; using fallback lesson.")
            return self._get_fallback_lesson(topic)

        try:
            parsed = self._parse_lesson(content, fallback_topic=topic, category=category)
            return parsed
        except Exception as e:
            print(f"Error parsing lesson: {e}; using fallback lesson.")
            return self._get_fallback_lesson(topic)

    async def generate_test(self, used_topics: list = None, memory_context: str = "") -> dict:
        """
        Generate an interactive, high-value English test question with smart distractors
        and a detailed pedagogical explanation explaining why the correct answer fits
        and why the wrong options fail.
        """
        memory_block = f"\n{memory_context}\n" if memory_context else ""

        prompt = f"""You are a master English examiner creating an interactive quiz for an English learning channel.
{memory_block}
Create a challenging, practical fill-in-the-blank English test question (B1 to C1 level).
Target areas: dependent prepositions, subtle tense distinctions, collocations, phrasal verbs, or confusing word pairs.

REQUIREMENTS:
1. A realistic sentence with a blank represented by `....` (4 dots).
2. The correct answer.
3. Two plausible distractors (common mistakes that intermediate learners make).
4. An in-depth pedagogical explanation that:
   - Explains why the correct answer is grammatically/contextually right.
   - Explains why each incorrect option is wrong (e.g., wrong preposition, different meaning, or ungrammatical).
5. 100% in English. Emojis included for engaging visual presentation.

Format your response EXACTLY like this:
QUESTION: [Sentence with .... for the blank] 🤔
CORRECT: [correct word/phrase]
INCORRECT 1: [plausible distractor 1]
INCORRECT 2: [plausible distractor 2]
EXPLANATION: [Pedagogical breakdown with 💡, ✅, and ❌ explaining the rule and why the distractors fail]"""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert English quiz creator. Create insightful, intermediate to advanced "
                    "questions that test real conversational or grammatical understanding. 100% English only."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        content = await asyncio.to_thread(self._get_ai_response, messages)
        if not content:
            print("AI generation failed for test; using fallback test.")
            return self._get_fallback_test()

        try:
            return self._parse_test(content)
        except Exception as e:
            print(f"Error parsing test: {e}; using fallback test.")
            return self._get_fallback_test()

    async def generate_batch_tests(self, topic: str, memory_context: str = "") -> list[dict]:
        """Generate a batch of 10 distinct, non-repetitive test questions for a specific topic"""
        memory_block = f"\n{memory_context}\n" if memory_context else ""

        prompt = f"""You are an expert English teacher creating an interactive 10-question quiz test.
Topic: "{topic}"
{memory_block}
Generate exactly 10 fill-in-the-blank English test questions testing different aspects of this topic.
Requirements:
1. 100% English only.
2. Each question has a blank represented by `....`.
3. Exactly one correct answer and two plausible incorrect choices.
4. Detailed, helpful explanation for each question.
5. Output MUST be ONLY a valid JSON array of 10 objects, without markdown code fences.

JSON format:
[
  {{
    "question": "She couldn't help .... when she heard the funny news. 🤔",
    "answer": "laughing",
    "incorrect": ["to laugh", "laugh"],
    "explanation": "💡 The expression 'can't help' is always followed by a gerund (-ing form) when it means unable to stop oneself."
  }}
]"""

        messages = [
            {
                "role": "system",
                "content": "You are an English test generator. Output ONLY a valid JSON array of 10 quiz questions. No intro, no outro, no markdown blocks.",
            },
            {"role": "user", "content": prompt},
        ]

        content = await asyncio.to_thread(self._get_ai_response, messages)
        if not content:
            return None

        try:
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            tests = json.loads(cleaned.strip())
            if isinstance(tests, list) and len(tests) > 0:
                return tests
            return None
        except Exception as e:
            print(f"Error parsing batch tests: {e}")
            return None

    def _get_ai_response(self, messages: list) -> str:
        """
        Execute API request with layered fallback across multiple models and keys:
        1. Iterate through candidate free models in order of quality.
        2. If key 1 fails with 429/auth, immediately try key 2.
        """
        keys = [k for k in [self.openrouter_api_key, self.openrouter_api_key_2] if k and "your-" not in k]
        if not keys:
            print("❌ No valid OpenRouter API keys configured.")
            return None

        # Build list of unique models to try
        models_to_try = []
        for m in self.fallback_models:
            if m and m not in models_to_try:
                models_to_try.append(m)

        for model in models_to_try:
            for key_idx, key in enumerate(keys, 1):
                try:
                    result = self._call_openrouter(messages, model=model, api_key=key)
                    if result:
                        print(f"[AI-SUCCESS] Generated content successfully using [{model}] (Key #{key_idx}).")
                        return result
                except urllib.error.HTTPError as err:
                    err_msg = err.read().decode("utf-8", errors="replace")[:120]
                    print(f"[AI-WARNING] OpenRouter HTTP {err.code} on model [{model}] (Key #{key_idx}): {err_msg}")
                    # If rate limited on this key, try next key immediately
                    continue
                except Exception as e:
                    print(f"[AI-WARNING] OpenRouter call failed on [{model}] (Key #{key_idx}): {e}")
                    continue

        print("[AI-ERROR] All OpenRouter models and fallback keys exhausted.")
        return None

    def _call_openrouter(self, messages: list, model: str, api_key: str) -> str:
        """Direct HTTP POST request to OpenRouter chat completions"""
        url = f"{self.openrouter_base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 2200,
            "temperature": 0.75,
        }

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://telegram.org",
            "X-Title": "English-Teaching-Bot",
        }

        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            choices = res_json.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            return None

    def _parse_lesson(self, content: str, fallback_topic: str = "", category: str = "") -> dict:
        """Parse structured AI response into clean lesson payload"""
        lines = content.strip().split("\n")
        topic_title = ""
        target_items = []
        lesson_body_lines = []
        in_lesson_body = False

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("TOPIC_TITLE:"):
                topic_title = line_str.replace("TOPIC_TITLE:", "").strip()
            elif line_str.startswith("TARGET_ITEMS:"):
                raw_items = line_str.replace("TARGET_ITEMS:", "").strip()
                target_items = [it.strip().strip("'\"") for it in raw_items.split(",") if it.strip()]
            elif line_str.startswith("LESSON:"):
                in_lesson_body = True
                remainder = line_str.replace("LESSON:", "").strip()
                if remainder:
                    lesson_body_lines.append(remainder)
            elif in_lesson_body:
                lesson_body_lines.append(line)

        # Fallback if markers were missed by model
        if not lesson_body_lines:
            lesson_body = content.strip()
        else:
            lesson_body = "\n".join(lesson_body_lines).strip()

        # Clean topic title
        if topic_title:
            topic_title = topic_title.strip("[]'\" ").strip()
            if topic_title.lower() in ("title", "[title]", "catchy title", "topic title"):
                topic_title = ""
        if not topic_title:
            topic_title = f"✨ {fallback_topic or 'English Mastery'}"

        # Clean target items
        clean_target_items = []
        for it in target_items:
            c = it.strip("[]'\" ").strip()
            if c and c.lower() not in ("item1", "item2", "item3", "[item1", "item2]"):
                clean_target_items.append(c)

        # Clean lesson body: drop any accidental model self-talk before the hook
        hook_match = re.search(r"(🎯|📚|•|\*\*The Hook\*\*|\*\*1\.)", lesson_body)
        if hook_match:
            lesson_body = lesson_body[hook_match.start():].strip()

        # If model returned no target items or literal placeholders, auto-extract from lesson body
        if not clean_target_items:
            bold_terms = re.findall(r"\*\*(.+?)\*\*", lesson_body)
            clean_target_items = [
                t.strip(":#-• ") for t in bold_terms
                if len(t.split()) <= 4 and not any(skip in t.lower() for skip in ["hook", "core", "pro tip", "tip", "rule", "turn", "don't say", "instead say", "example"])
            ][:4]

        return {
            "type": "lesson",
            "topic": topic_title,
            "category": category,
            "target_items": clean_target_items,
            "content": lesson_body,
        }

    def _parse_test(self, content: str) -> dict:
        """Parse structured AI response into test question payload"""
        lines = content.strip().split("\n")
        question = ""
        answer = ""
        incorrect1 = ""
        incorrect2 = ""
        explanation = ""

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("QUESTION:"):
                question = line_str.replace("QUESTION:", "").strip()
            elif line_str.startswith("CORRECT:"):
                answer = line_str.replace("CORRECT:", "").strip()
            elif line_str.startswith("INCORRECT 1:"):
                incorrect1 = line_str.replace("INCORRECT 1:", "").strip()
            elif line_str.startswith("INCORRECT 2:"):
                incorrect2 = line_str.replace("INCORRECT 2:", "").strip()
            elif line_str.startswith("EXPLANATION:"):
                explanation = line_str.replace("EXPLANATION:", "").strip()
            elif explanation:
                explanation += "\n" + line_str

        # Clean placeholders
        if not question:
            question = "She couldn't help .... when she heard the hilarious news. 🤔"
        if not answer:
            answer = "laughing"
        if not incorrect1:
            incorrect1 = "to laugh"
        if not incorrect2:
            incorrect2 = "laugh"
        if not explanation:
            explanation = "💡 The phrase 'can't help' is always followed by a gerund (-ing) when it means unable to prevent oneself."

        return {
            "type": "test",
            "question": question,
            "answer": answer,
            "incorrect": [incorrect1, incorrect2],
            "explanation": explanation.strip(),
        }

    def _get_fallback_lesson(self, topic: str = "") -> dict:
        """High-value emergency fallback lesson if all APIs fail"""
        topic_title = topic or "💡 Power Words: Replace 'Very Tired'"
        body = (
            "🎯 Tired of saying 'very tired' in every conversation? Native speakers use rich, "
            "precise adjectives to express their energy levels with style! ✨\n\n"
            "📚 **3 High-Impact Swaps:**\n\n"
            "• **Exhausted** — Completely drained of physical or mental energy.\n"
            "  ✍️ _After running the 10km marathon, Sarah was utterly exhausted._ 🏃‍♀️\n"
            "  ❌ **Don't say:** _I am very, very, very tired from the run._\n"
            "  ✅ **Instead say:** _I'm completely exhausted!_\n\n"
            "• **Drained** — Emotionally or mentally fatigued, often after stress.\n"
            "  ✍️ _A full day of back-to-back client meetings left the team feeling drained._ 💼\n"
            "  💡 Use 'drained' when mental stress saps your energy.\n\n"
            "• **Worn out** — Exhausted from prolonged physical work or daily grind.\n"
            "  ✍️ _He looked worn out after renovating his kitchen all weekend._ 🛠️\n"
            "  💡 Great for casual everyday chats with friends.\n\n"
            "💡 **Pro Tip & Memory Hack:**\n"
            "Think of a battery 🪫: 'Tired' is 30% battery, but 'Exhausted' is 1%! Reserve these words "
            "for when you truly need strong emphasis without using 'very'. 🔥\n\n"
            "💬 **Your Turn:**\n"
            "Which of these words best describes you on Friday evening? Drop it below! 👇"
        )
        return {
            "type": "lesson",
            "topic": f"🌟 {topic_title}",
            "category": "Vocabulary",
            "target_items": ["Exhausted", "Drained", "Worn out"],
            "content": body,
        }

    def _get_fallback_test(self) -> dict:
        """High-value emergency fallback test if all APIs fail"""
        return {
            "type": "test",
            "question": "We are looking forward to .... you at the upcoming summit! 🤔",
            "answer": "meeting",
            "incorrect": ["meet", "met"],
            "explanation": (
                "💡 **Grammar Rule:** In the phrase 'look forward to', the word 'to' is a preposition, "
                "not an infinitive marker! Prepositions must be followed by a noun or a gerund (-ing form). "
                "Therefore, 'meeting' is the only correct answer. 🎯"
            ),
        }
