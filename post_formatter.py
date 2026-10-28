"""
Post Formatter - Premium Telegram Message Styler
Produces visually engaging, beautifully formatted HTML posts with dividers,
proper markdown-to-HTML conversion, and clean hashtags.
"""

import html
import re


class PostFormatter:
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML special characters for Telegram without escaping quotes/apostrophes"""
        if not text:
            return ""
        return html.escape(text, quote=False)

    @staticmethod
    def markdown_to_html(text: str) -> str:
        """Convert standard markdown syntax into Telegram HTML tags"""
        if not text:
            return ""

        # Code blocks: ```code```
        text = re.sub(r'```(.*?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)

        # Inline code: `code`
        text = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', text)

        # Bold: **text** or __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
        text = re.sub(r'__(.+?)__', r'<b>\1</b>', text, flags=re.DOTALL)

        # Italic: _text_ (ensure not surrounded by alphanumeric characters)
        text = re.sub(r'(?<!\w)_([^\_\n]+?)_(?!\w)', r'<i>\1</i>', text)

        # Single asterisk italic: *text* (must not conflict with bullet points)
        text = re.sub(r'(?<!\*)\*([^\*\s\n][^\*\n]*?)\*(?!\*)', r'<i>\1</i>', text)

        return text

    @staticmethod
    def _clean_hashtag(text: str) -> str:
        """Create a clean, camelCase hashtag without emojis or punctuation"""
        cleaned = re.sub(r'[^\w\s]', '', text)
        cleaned = re.sub(r'[^\x00-\x7F]+', '', cleaned)
        words = cleaned.strip().split()
        if not words:
            return "LearnEnglish"
        return words[0].capitalize() + ''.join(w.capitalize() for w in words[1:])

    @staticmethod
    def format_lesson(lesson_data: dict) -> str:
        """Format an educational lesson with premium visual hierarchy and hashtags"""
        topic = lesson_data.get('topic', '📚 English Lesson')
        content = lesson_data.get('content', '')
        specific_tags = lesson_data.get('tags', [])
        general_tags = lesson_data.get('general_tags', ['#LearnEnglish', '#EnglishTips'])

        # Prepare hashtags
        all_tags = []
        if specific_tags:
            all_tags.extend(specific_tags[:3])
        else:
            all_tags.append("#" + PostFormatter._clean_hashtag(topic))

        if general_tags:
            for gt in general_tags[:3]:
                if gt not in all_tags:
                    all_tags.append(gt)

        hashtags_str = " ".join(all_tags)

        # Convert markdown styling
        topic_escaped = PostFormatter.escape_html(topic)
        topic_formatted = PostFormatter.markdown_to_html(topic_escaped)

        content_escaped = PostFormatter.escape_html(content)
        content_formatted = PostFormatter.markdown_to_html(content_escaped)

        formatted = f"""🌟 <b>{topic_formatted}</b> 🌟
━━━━━━━━━━━━━━━━━━━━━

{content_formatted}

━━━━━━━━━━━━━━━━━━━━━
💡 <i>Save this post so you don't lose it!</i>
⏰ <i>New bite-sized lessons every 4 hours!</i>

🏷️ {hashtags_str}

✅ <b>Follow us:</b>
|<a href="https://t.me/+QxanmBn5JImTJfQe">Telegram</a> | <a href="https://instagram.com/englishnativetv?igshid=ZDdkNTZiNTM=">Instagram</a> | <a href="https://m.youtube.com/@englishnativetv/videos">YouTube</a>"""

        return formatted

    @staticmethod
    def format_test(test_data: dict) -> str:
        """Format an interactive quiz question for Telegram"""
        question = test_data.get('question', 'Do you .... here? 🤔')
        category = test_data.get('category', 'English Quiz')

        question_escaped = PostFormatter.escape_html(question)
        question_formatted = PostFormatter.markdown_to_html(question_escaped)

        formatted = f"""🧪 <b>English Quiz Time!</b> 🎯
━━━━━━━━━━━━━━━━━━━━━

❓ {question_formatted}

━━━━━━━━━━━━━━━━━━━━━
👇 <b>Tap your answer below:</b>

🏷️ #EnglishQuiz #TestYourEnglish #LearnEnglish

✅ <b>Follow us:</b>
|<a href="https://t.me/+QxanmBn5JImTJfQe">Telegram</a> | <a href="https://instagram.com/englishnativetv?igshid=ZDdkNTZiNTM=">Instagram</a> | <a href="https://m.youtube.com/@englishnativetv/videos">YouTube</a>"""

        return formatted

    @staticmethod
    def format_answer_reveal(test_data: dict) -> str:
        """Format the answer reveal and explanation message"""
        question = test_data.get('question', '')
        answer = test_data.get('answer', '')
        explanation = test_data.get('explanation', '')

        question_escaped = PostFormatter.escape_html(question)
        answer_escaped = PostFormatter.escape_html(answer)
        explanation_escaped = PostFormatter.escape_html(explanation)

        explanation_formatted = PostFormatter.markdown_to_html(explanation_escaped)

        # Replace blank markers with the bold answer
        answered_question = question_escaped
        for blank in ['....', '___', '...']:
            if blank in answered_question:
                answered_question = answered_question.replace(blank, f'<b><u>{answer_escaped}</u></b>')
                break

        formatted = f"""✅ <b>Answer Revealed!</b> 🎉
━━━━━━━━━━━━━━━━━━━━━

📝 {answered_question}

💡 <b>Explanation:</b>
{explanation_formatted}

━━━━━━━━━━━━━━━━━━━━━
🤔 <i>Did you get it right? Keep practicing daily! 📚</i>

🏷️ #QuizAnswer #EnglishGrammar #DailyEnglish

✅ <b>Follow us:</b>
|<a href="https://t.me/+QxanmBn5JImTJfQe">Telegram</a> | <a href="https://instagram.com/englishnativetv?igshid=ZDdkNTZiNTM=">Instagram</a> | <a href="https://m.youtube.com/@englishnativetv/videos">YouTube</a>"""

        return formatted

    @staticmethod
    def format_welcome() -> str:
        """Format welcome message for new users"""
        return """🌟 <b>Welcome to Improve Your English!</b> 🌟

🤖 Your automated AI English teacher is online and ready!

📋 <b>What you get:</b>
📚 • 6 high-impact lessons daily (every 4 hours)
🧪 • 2 interactive quizzes daily (every 12 hours)
🧠 • Advanced memory tracking — zero repeating topics or words!
🎯 • Practical vocabulary, phrasal verbs, idioms & grammar

🚀 <b>Commands you can use:</b>
/lesson — Generate an instant lesson
/test — Generate an instant quiz
/status — View detailed memory & posting statistics
/portfolio — View live crypto trading positions & P&L

✅ <b>Follow us:</b>
|<a href="https://t.me/+QxanmBn5JImTJfQe">Telegram</a> | <a href="https://instagram.com/englishnativetv?igshid=ZDdkNTZiNTM=">Instagram</a> | <a href="https://m.youtube.com/@englishnativetv/videos">YouTube</a>"""
