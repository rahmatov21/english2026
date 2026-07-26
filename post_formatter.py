"""
Post Formatter - Formats lessons and tests for Telegram
Uses HTML parsing mode with emoji-rich, premium styling
"""

import html
import re


class PostFormatter:
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML special characters"""
        return html.escape(text)

    @staticmethod
    def markdown_to_html(text: str) -> str:
        """Convert basic markdown to Telegram HTML"""
        # Bold: **text**
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
        # Bold: __text__
        text = re.sub(r'__(.+?)__', r'<b>\1</b>', text, flags=re.DOTALL)
        # Italic: *text* (must not start with space to avoid bullet points)
        text = re.sub(r'(?<!\*)\*([^\*\s][^\*]*?)\*(?!\*)', r'<i>\1</i>', text, flags=re.DOTALL)
        # Italic: _text_
        text = re.sub(r'(?<!_)_([^\_\s][^\_]*?)_(?!_)', r'<i>\1</i>', text, flags=re.DOTALL)
        return text

    @staticmethod
    def _clean_hashtag(text: str) -> str:
        """Create a clean hashtag: no emojis, no special chars, camelCase"""
        # Remove all non-alphanumeric characters except spaces
        cleaned = re.sub(r'[^\w\s]', '', text)
        # Remove emojis that might have slipped through
        cleaned = re.sub(r'[^\x00-\x7F]+', '', cleaned)
        # Split into words and capitalize each
        words = cleaned.strip().split()
        if not words:
            return "English"
        # CamelCase
        return words[0].capitalize() + ''.join(w.capitalize() for w in words[1:])

    @staticmethod
    def format_lesson(lesson_data: dict) -> str:
        """Format a lesson post for Telegram with emoji-rich, premium styling"""
        topic = lesson_data.get('topic', '📚 English Lesson')
        content = lesson_data.get('content', '')
        specific_tags = lesson_data.get('tags', [])
        general_tags = lesson_data.get('general_tags', ['#LearnEnglish', '#EnglishLesson'])

        topic = PostFormatter.escape_html(topic)
        content = PostFormatter.escape_html(content)
        
        topic = PostFormatter.markdown_to_html(topic)
        content = PostFormatter.markdown_to_html(content)
        
        if not specific_tags:
            specific_tags = ["#" + PostFormatter._clean_hashtag(topic)]
            
        formatted = f"""✨ <b>{topic}</b> ✨


{content}

___________________________________
💡 <i>Save this post so you don't forget it!</i>
⏰ <i>Stay tuned!</i>

✅ <b>Follow us:</b>
|<a href="https://t.me/+QxanmBn5JImTJfQe">Telegram</a> | <a href="https://instagram.com/englishnativetv?igshid=ZDdkNTZiNTM=">Instagram</a> | <a href="https://m.youtube.com/@englishnativetv/videos">YouTube</a>"""

        return formatted

    @staticmethod
    def format_test(test_data: dict) -> str:
        """Format a test post for Telegram with emoji-rich styling"""
        question = test_data.get('question', 'Do you .... here? 🤔')
        answer = test_data.get('answer', 'work')
        explanation = test_data.get('explanation', '')

        question = PostFormatter.escape_html(question)
        answer = PostFormatter.escape_html(answer)
        explanation = PostFormatter.escape_html(explanation)

        question = PostFormatter.markdown_to_html(question)
        answer = PostFormatter.markdown_to_html(answer)
        explanation = PostFormatter.markdown_to_html(explanation)

        formatted = f"""🧪 <b>English Test Time!</b>

❓ {question}

━━━━━━━━━━━━━━━━━━━━━━━
👇 <b>Choose your answer using the buttons below.</b>

✅Follow us:

|<a href="https://t.me/+QxanmBn5JImTJfQe">Telegram</a> | <a href="https://instagram.com/englishnativetv?igshid=ZDdkNTZiNTM=">Instagram</a> | <a href="https://m.youtube.com/@englishnativetv/videos">YouTube</a>"""

        return formatted

    @staticmethod
    def format_answer_reveal(test_data: dict) -> str:
        """Format the answer reveal message with emoji-rich styling"""
        question = test_data.get('question', '')
        answer = test_data.get('answer', '')
        explanation = test_data.get('explanation', '')

        question = PostFormatter.escape_html(question)
        answer = PostFormatter.escape_html(answer)
        explanation = PostFormatter.escape_html(explanation)

        question = PostFormatter.markdown_to_html(question)
        answer = PostFormatter.markdown_to_html(answer)
        explanation = PostFormatter.markdown_to_html(explanation)

        # Replace the blank with the answer
        answered_question = question.replace('....', f'<b>{answer}</b>')
        answered_question = answered_question.replace('___', f'<b>{answer}</b>')
        answered_question = answered_question.replace('...', f'<b>{answer}</b>')

        formatted = f"""✅ <b>Answer Revealed!</b>

📝 {answered_question}

💡 <b>Explanation:</b>
{explanation}

━━━━━━━━━━━━━━━━━━━━━━━
🤔 <i>How did you do? Keep practicing daily! 📚</i>

✅Follow us:

|<a href="https://t.me/+QxanmBn5JImTJfQe">Telegram</a> | <a href="https://instagram.com/englishnativetv?igshid=ZDdkNTZiNTM=">Instagram</a> | <a href="https://m.youtube.com/@englishnativetv/videos">YouTube</a>"""

        return formatted

    @staticmethod
    def format_welcome() -> str:
        """Format welcome message — clean, emoji-rich"""
        return """🌟 <b>Improve Your English</b> 🌟

🤖 Your AI English teacher bot is now active!

📋 <b>What you get:</b>
📚 • 6 lessons daily — every 4 hours
🧪 • 2 tests daily — every 12 hours
🔄 • Unique topics — no repeats!

🚀 <b>How to use:</b>
📖 • Read the lessons
👆 • Tap test buttons to answer
✅ • Check back for answer reveals

🎯 Let's improve your English together!

✅Follow us:

|<a href="https://t.me/+QxanmBn5JImTJfQe">Telegram</a> | <a href="https://instagram.com/englishnativetv?igshid=ZDdkNTZiNTM=">Instagram</a> | <a href="https://m.youtube.com/@englishnativetv/videos">YouTube</a>"""
