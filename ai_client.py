"""
OpenRouter AI Client for generating English teaching content
Uses direct HTTP requests to avoid library compatibility issues
"""

import asyncio
import json
import urllib.request
import urllib.error
import urllib.error
from config import OPENROUTER_API_KEY, OPENROUTER_API_KEY_2, OPENROUTER_MODEL, OPENROUTER_MODEL_2, OPENROUTER_MODEL_3, OPENROUTER_BASE_URL


class AIClient:
    def __init__(self):
        self.openrouter_api_key = OPENROUTER_API_KEY
        self.openrouter_api_key_2 = OPENROUTER_API_KEY_2
        self.openrouter_model = OPENROUTER_MODEL
        self.openrouter_model_2 = OPENROUTER_MODEL_2
        self.openrouter_model_3 = OPENROUTER_MODEL_3
        self.openrouter_base_url = OPENROUTER_BASE_URL

    async def generate_lesson(self, topic: str) -> dict:
        """Generate an English teaching lesson for a specific topic"""
        prompt = f"""You are an expert English teacher creating content for a Telegram channel called "Improve Your English".

Generate a highly engaging English lesson about the following topic:
"{topic}"

The lesson MUST follow this EXACT visual structure and style:

1. A brief, engaging introduction paragraph (2-3 sentences) explaining the concept with a few relevant emojis.
2. A section with 3 distinct examples or rules. Use emojis at the start of lines (like ✍️, ✅, or 🎯) and end of sentences. Use Markdown italics `_text_` for the example sentences. Format depends on the topic (e.g., numbered list for grammar rules, or bold terms for idioms/vocabulary).
3. A tip, trick, or memory aid paragraph starting with an emoji like 💡 or 🔥.
4. A short concluding motivational sentence with a 🌟 or 🎯.

IMPORTANT: The entire lesson MUST be in 100% English. Do NOT include translations, Chinese characters, or any other languages.
IMPORTANT: Use markdown for formatting: `_text_` for italics (use for all example sentences). 
IMPORTANT: Do NOT include the topic title in your output. Just output the body of the lesson starting directly with the introduction paragraph.

Format your response EXACTLY like this (include the markers):
LESSON: [your lesson body here]"""

        messages = [
            {"role": "system", "content": "You are an expert English teacher creating engaging, bite-sized lessons for social media. The content MUST be entirely in English with NO translations or other languages. Use relevant emojis tastefully to make content visually appealing and structured. Each section should have fitting emojis like 📚 for lessons, ✍️ for examples, 💡 for tips, ⭐ for highlights."},
            {"role": "user", "content": prompt}
        ]

        content = await asyncio.to_thread(self._get_ai_response, messages)
        if not content:
            return None
            
        try:
            parsed = self._parse_lesson(content)
            # Ensure the topic name is preserved
            parsed['topic'] = topic
            return parsed
        except Exception as e:
            print(f"Error parsing lesson: {e}")
            return None

    async def generate_test(self, used_topics: list) -> dict:
        """Generate an interactive test with reactions"""
        topics_str = ", ".join(used_topics) if used_topics else "none"

        prompt = f"""You are an expert English teacher creating interactive tests for a Telegram channel.

Create a fill-in-the-blank English test question. The format should be:
1. A sentence with a blank (represented by ....)
2. The correct answer
3. Two incorrect options that are plausible but wrong
4. A brief explanation of why the correct answer is right

IMPORTANT: Do NOT repeat topics from: {topics_str}
IMPORTANT: The entire test MUST be in 100% English. Do NOT include translations, Chinese characters, or any other languages under any circumstances.
IMPORTANT: Use emojis tastefully throughout your response to make it visually engaging for Telegram users. Use relevant emojis like 🧪 ❓ ✅ 💬 📖 🎯 🧠 and others that fit naturally.

Format your response EXACTLY like this (include the markers):
QUESTION: [sentence with .... for blank]
CORRECT: [correct word/phrase]
INCORRECT 1: [incorrect option 1]
INCORRECT 2: [incorrect option 2]
EXPLANATION: [brief explanation with emojis for visual appeal]

Example:
QUESTION: Do you .... here? 🤔
CORRECT: work
INCORRECT 1: working
INCORRECT 2: works
EXPLANATION: 💡 We use the base form 'work' with 'Do' in present simple questions. Simple but essential!

Make it educational and suitable for intermediate English learners. Use emojis to make it fun!"""

        messages = [
            {"role": "system", "content": "You are an expert English teacher creating interactive tests. The content MUST be entirely in English with NO translations or other languages. Use relevant emojis tastefully to make quizzes visually engaging — 🧪 for tests, ✅ for answers, 💡 for explanations, 🎯 for key points."},
            {"role": "user", "content": prompt}
        ]

        content = await asyncio.to_thread(self._get_ai_response, messages)
        if not content:
            return None

        try:
            return self._parse_test(content)
        except Exception as e:
            print(f"Error parsing test: {e}")
            return None

    async def generate_batch_tests(self, topic: str) -> list[dict]:
        """Generate a batch of 10 tests for a specific topic"""
        prompt = f"""You are an expert English teacher creating interactive tests for a Telegram channel.

Generate exactly 10 fill-in-the-blank English test questions about the following topic:
"{topic}"

IMPORTANT: The entire content MUST be in 100% English. Do NOT include translations, Chinese characters, or any other languages under any circumstances.
IMPORTANT: Output ONLY valid JSON, nothing else. The JSON should be an array of exactly 10 objects.

Format your response EXACTLY as this JSON array:
[
  {{
    "question": "Do you .... here? 🤔",
    "answer": "work",
    "incorrect": ["working", "works"],
    "explanation": "💡 We use the base form 'work' with 'Do' in present simple questions."
  }}
]
(Make sure the array has exactly 10 items)"""

        messages = [
            {"role": "system", "content": "You are an expert English teacher creating interactive tests. The content MUST be entirely in English with NO translations. Output ONLY valid JSON. Do not include markdown code blocks like ```json."},
            {"role": "user", "content": prompt}
        ]

        content = await asyncio.to_thread(self._get_ai_response, messages)
        if not content:
            return None

        try:
            # Clean potential markdown formatting
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            tests = json.loads(content.strip())
            return tests
        except Exception as e:
            print(f"Error parsing batch tests: {e}")
            return None

    def _get_ai_response(self, messages: list) -> str:
        """Try OpenAI first, fallback to OpenRouter"""
        # Try OpenRouter (Primary Key)
        try:
            response = self._make_openrouter_request(messages, fallback_level=1)
            if 'error' not in response:
                choices = response.get('choices', [])
                if choices:
                    content = choices[0].get('message', {}).get('content')
                    if content:
                        print("Successfully generated content using OpenRouter (Primary Key).")
                        return content
            else:
                print(f"API Error from OpenRouter (Primary): {response['error']}")
        except Exception as e:
            print(f"OpenRouter (Primary) failed: {e}. Trying secondary key...")
            
        # Fallback to OpenRouter (Secondary Key)
        try:
            response = self._make_openrouter_request(messages, fallback_level=2)
            if 'error' not in response:
                choices = response.get('choices', [])
                if choices:
                    content = choices[0].get('message', {}).get('content')
                    if content:
                        print("Successfully generated content using OpenRouter (Secondary Key).")
                        return content
            else:
                print(f"API Error from OpenRouter (Secondary): {response['error']}")
        except Exception as e:
            print(f"OpenRouter (Secondary) failed: {e}. Trying tertiary model...")
            
        # Fallback to OpenRouter (Tertiary Model)
        try:
            response = self._make_openrouter_request(messages, fallback_level=3)
            if 'error' not in response:
                choices = response.get('choices', [])
                if choices:
                    content = choices[0].get('message', {}).get('content')
                    if content:
                        print("Successfully generated content using OpenRouter (Tertiary Model).")
                        return content
            else:
                print(f"API Error from OpenRouter (Tertiary): {response['error']}")
        except Exception as e:
            print(f"OpenRouter (Tertiary) failed: {e}.")
            
        print("All AI models and fallback keys failed to generate content.")
        return None

    def _make_openrouter_request(self, messages: list, fallback_level: int = 1) -> dict:
        """Make HTTP request to OpenRouter API"""
        url = f"{self.openrouter_base_url}/chat/completions"

        if fallback_level == 1:
            model_name = self.openrouter_model
            api_key = self.openrouter_api_key
        elif fallback_level == 2:
            model_name = self.openrouter_model_2
            api_key = self.openrouter_api_key_2
        else:
            model_name = self.openrouter_model_3
            api_key = self.openrouter_api_key # Use primary key for 3rd model since no 3rd key was requested
            
        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": 2000,
            "temperature": 0.8
        }
        
        if not api_key or "your-" in api_key:
            raise ValueError(f"API key missing or placeholder for fallback_level {fallback_level}.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(url, data=data, headers=headers)

        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))

    def _parse_lesson(self, content: str) -> dict:
        """Parse the AI response into structured lesson data"""
        lines = content.strip().split('\n')
        topic = ""
        lesson = ""

        for line in lines:
            if line.startswith("TOPIC:"):
                topic = line.replace("TOPIC:", "").strip()
            elif line.startswith("LESSON:"):
                lesson = line.replace("LESSON:", "").strip()
            elif lesson:
                lesson += "\n" + line.strip()

        if not topic:
            topic = "📚 English Lesson"
        if not lesson:
            lesson = content

        return {
            "type": "lesson",
            "topic": topic,
            "content": lesson
        }

    def _parse_test(self, content: str) -> dict:
        """Parse the AI response into structured test data"""
        lines = content.strip().split('\n')
        question = ""
        answer = ""
        incorrect1 = ""
        incorrect2 = ""
        explanation = ""

        for line in lines:
            if line.startswith("QUESTION:"):
                question = line.replace("QUESTION:", "").strip()
            elif line.startswith("CORRECT:"):
                answer = line.replace("CORRECT:", "").strip()
            elif line.startswith("INCORRECT 1:"):
                incorrect1 = line.replace("INCORRECT 1:", "").strip()
            elif line.startswith("INCORRECT 2:"):
                incorrect2 = line.replace("INCORRECT 2:", "").strip()
            elif line.startswith("EXPLANATION:"):
                explanation = line.replace("EXPLANATION:", "").strip()

        if not question:
            question = "Do you .... here? 🤔"
        if not answer:
            answer = "work"
        if not incorrect1:
            incorrect1 = "working"
        if not incorrect2:
            incorrect2 = "works"
        if not explanation:
            explanation = "💡 We use the base form 'work' with 'Do' in present simple questions."

        return {
            "type": "test",
            "question": question,
            "answer": answer,
            "incorrect": [incorrect1, incorrect2],
            "explanation": explanation
        }

    def _get_fallback_lesson(self) -> dict:
        """Fallback lesson if AI fails — emoji-rich"""
        return {
            "type": "lesson",
            "topic": "📚 Daily English Practice",
            "content": (
                "💡 Today's Tip: Practice makes perfect!\n\n"
                "✍️ Try to use new vocabulary in sentences every day.\n\n"
                "📝 Example: Instead of 'good', try 'excellent' ✨, 'wonderful' 🌟, or 'fantastic' 🎉!\n\n"
                "⭐ Tip: Keep a vocabulary notebook 📓 and review it daily. Consistency is key! 🔑"
            )
        }

    def _get_fallback_test(self) -> dict:
        """Fallback test if AI fails — emoji-rich"""
        return {
            "type": "test",
            "question": "Do you .... here? 🤔",
            "answer": "work",
            "explanation": "💡 We use 'work' to ask about someone's job location. A simple but essential question! 🎯"
        }
