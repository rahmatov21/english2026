"""
Telegram English Teaching Bot - Main Bot File
Uses direct HTTP API calls for maximum compatibility
"""

import asyncio
import json
import logging
import sys
import io
import urllib.request
import urllib.error
import uuid
import time
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from config import (
    BOT_TOKEN, CHANNEL_ID, POST_INTERVAL_HOURS,
    TOPICS_DATA, GENERAL_TAGS
)
import random
from ai_client import AIClient
from topic_history import TopicHistory
from post_formatter import PostFormatter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class TelegramAPI:
    """Simple Telegram Bot API wrapper using HTTP requests"""

    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0

    async def _make_request(self, method: str, data: dict = None) -> dict:
        """Make HTTP request to Telegram API"""
        url = f"{self.base_url}/{method}"

        if data:
            payload = json.dumps(data).encode('utf-8')
            request = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        else:
            request = urllib.request.Request(url)

        def do_req():
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    return json.loads(response.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                error_msg = e.read().decode()
                if method == 'answerCallbackQuery' and 'query is too old' in error_msg:
                    return {'ok': False, 'error': 'query too old'}
                if method == 'editMessageReplyMarkup' and ('message is not modified' in error_msg or 'message to edit not found' in error_msg):
                    return {'ok': False, 'error': 'edit skipped'}
                logger.error(f"HTTP Error {e.code}: {error_msg}")
                return {'ok': False, 'error': str(e)}
            except Exception as e:
                logger.error(f"Request error: {e}")
                return {'ok': False, 'error': str(e)}
        
        return await asyncio.to_thread(do_req)

    async def send_message(self, chat_id: str, text: str, parse_mode: str = 'HTML', reply_markup: dict = None, disable_web_page_preview: bool = True) -> dict:
        """Send a message to a chat"""
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': disable_web_page_preview
        }

        if reply_markup:
            data['reply_markup'] = reply_markup

        return await self._make_request('sendMessage', data)

    async def get_updates(self, offset: int = None, limit: int = 100) -> dict:
        """Get updates from Telegram"""
        data = {'limit': limit, 'timeout': 1}
        if offset:
            data['offset'] = offset

        return await self._make_request('getUpdates', data)

    async def answer_callback_query(self, callback_query_id: str, text: str = None, show_alert: bool = False) -> dict:
        """Answer a callback query"""
        data = {'callback_query_id': callback_query_id}
        if text:
            data['text'] = text
        if show_alert:
            data['show_alert'] = True

        return await self._make_request('answerCallbackQuery', data)

    async def edit_message_reply_markup(self, chat_id: str, message_id: int, reply_markup: dict = None) -> dict:
        """Edit the inline keyboard of a message"""
        data = {
            'chat_id': chat_id,
            'message_id': message_id
        }
        if reply_markup is not None:
            data['reply_markup'] = reply_markup
        else:
            data['reply_markup'] = {'inline_keyboard': []}
            
        return await self._make_request('editMessageReplyMarkup', data)

    async def get_chat_member(self, chat_id: str, user_id: int) -> dict:
        """Get information about a member of a chat"""
        data = {
            'chat_id': chat_id,
            'user_id': user_id
        }
        return await self._make_request('getChatMember', data)


    async def send_poll(self, chat_id: str, question: str, options: list, type: str = 'quiz', correct_option_id: int = 0, explanation: str = None, explanation_parse_mode: str = 'HTML') -> dict:
        """Send a native Telegram poll/quiz"""
        data = {
            'chat_id': chat_id,
            'question': question[:300], # max 300 chars
            'options': [opt[:100] for opt in options], # max 100 chars per option
            'type': type,
            'correct_option_id': correct_option_id
        }
        if explanation:
            data['explanation'] = explanation[:200] # max 200 chars
            data['explanation_parse_mode'] = explanation_parse_mode
            
        return await self._make_request('sendPoll', data)

class EnglishBot:
    def __init__(self):
        self.telegram = TelegramAPI(BOT_TOKEN)
        self.channel_id = CHANNEL_ID
        self.ai_client = AIClient()
        self.topic_history = TopicHistory()
        self.formatter = PostFormatter()
        self.scheduler = AsyncIOScheduler()
        self.post_count = 0
        self.test_count = 0
        self.current_test = None
        self.test_message_id = None
        self.testtime_state = {}
        self.waiting_for_model = {}
        self.active_tests = {}
        self.subscriber_cache = {}
        self.running = True

    async def start_scheduler(self):
        """Start the posting scheduler"""
        self.scheduler.add_job(
            self.send_lesson,
            'interval',
            hours=POST_INTERVAL_HOURS,
            id='lesson_job',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("🚀 Scheduler started — lessons every %dh", POST_INTERVAL_HOURS)

    async def send_lesson(self):
        """Generate and send a lesson to the channel"""
        try:
            logger.info("📚 Generating lesson...")

            used_topics = self.topic_history.get_used_topics()
            
            # Find an unused topic
            available_topics = []
            for category, data in TOPICS_DATA.items():
                for topic in data['topics']:
                    if topic.lower().strip() not in [t.lower() for t in used_topics]:
                        available_topics.append({'category': category, 'topic': topic, 'tags': data['tags']})
            
            if not available_topics:
                logger.warning("All topics used! Resetting topic history and starting over.")
                self.topic_history.reset_history()
                for category, data in TOPICS_DATA.items():
                    for topic in data['topics']:
                        available_topics.append({'category': category, 'topic': topic, 'tags': data['tags']})
            
            selected = random.choice(available_topics)
            selected_topic = selected['topic']
            selected_tags = selected['tags']
            
            lesson_data = await self.ai_client.generate_lesson(selected_topic)
            if not lesson_data:
                logger.error("❌ Failed to generate lesson data. Skipping post.")
                return
                
            lesson_data['tags'] = selected_tags
            lesson_data['general_tags'] = GENERAL_TAGS
            
            formatted_post = self.formatter.format_lesson(lesson_data)

            result = await self.telegram.send_message(
                chat_id=self.channel_id,
                text=formatted_post,
                parse_mode='HTML'
            )
            if result.get('ok'):
                self.topic_history.add_topic(lesson_data['topic'])
                self.post_count += 1
                logger.info("✅ Lesson sent: %s (Post #%d)", lesson_data['topic'], self.post_count)
            else:
                logger.error("❌ Failed to send lesson: %s", result)

        except Exception as e:
            logger.error("❌ Error sending lesson: %s", e)

    async def send_test(self, mode: str = 'poll'):
        """Generate and send a test to the channel"""
        try:
            logger.info("🧪 Generating test...")

            used_topics = self.topic_history.get_used_topics()
            test_data = await self.ai_client.generate_test(used_topics)
            if not test_data:
                logger.error("❌ Failed to generate test data. Skipping post.")
                return
                
            self.current_test = test_data

            if mode == 'poll':
                options = [test_data['answer']] + test_data.get('incorrect', [])
                random.shuffle(options)
                correct_idx = options.index(test_data['answer'])
                
                question = test_data.get('question', 'Test Question')
                explanation = test_data.get('explanation', '')
                
                result = await self.telegram.send_poll(
                    chat_id=self.channel_id,
                    question=question,
                    options=options,
                    type='quiz',
                    correct_option_id=correct_idx,
                    explanation=explanation,
                    explanation_parse_mode='HTML'
                )
                if result.get('ok'):
                    self.test_message_id = result['result']['message_id']
                    self.test_count += 1
                    self.topic_history.add_topic(f"Test: {test_data['question'][:30]}")
                    logger.info("✅ Poll Test sent (Test #%d)", self.test_count)
                else:
                    logger.error("❌ Failed to send poll test: %s", result)
            else:
                formatted_post = self.formatter.format_test(test_data)
    
                # Inline keyboard buttons
                options = [test_data['answer']] + test_data.get('incorrect', [])
                random.shuffle(options)
                
                test_id = str(uuid.uuid4())
                correct_idx = options.index(test_data['answer'])
                
                self.active_tests[test_id] = {
                    'options': options,
                    'correct_idx': correct_idx,
                    'votes': {},
                    'counts': {i: 0 for i in range(len(options))},
                    'explanation': test_data.get('explanation', '')
                }
                
                keyboard_buttons = []
                for i, opt in enumerate(options):
                    keyboard_buttons.append({'text': f'{opt}'.strip(), 'callback_data': f'testvote_{test_id}_{i}'})
    
                inline_keyboard = []
                if len(keyboard_buttons) >= 2:
                    inline_keyboard.append([keyboard_buttons[0], keyboard_buttons[1]])
                    if len(keyboard_buttons) > 2:
                        inline_keyboard.append(keyboard_buttons[2:])
                else:
                    inline_keyboard.append(keyboard_buttons)
    
                reply_markup = {
                    'inline_keyboard': inline_keyboard
                }
    
                result = await self.telegram.send_message(
                    chat_id=self.channel_id,
                    text=formatted_post,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                if result.get('ok'):
                    self.test_message_id = result['result']['message_id']
                    self.test_count += 1
                    self.topic_history.add_topic(f"Test: {test_data['question'][:30]}")
                    logger.info("✅ Test sent (Test #%d)", self.test_count)
                else:
                    logger.error("❌ Failed to send test: %s", result)

        except Exception as e:
            logger.error("❌ Error sending test: %s", e)

    async def generate_and_send_batch_tests(self, topic: str, mode: str = 'inline'):
        """Generate and send 10 tests for a given topic"""
        try:
            logger.info(f"🧪 Generating 10 tests for topic: {topic} (Mode: {mode})...")
            
            tests = await self.ai_client.generate_batch_tests(topic)
            if not tests or not isinstance(tests, list):
                logger.error("❌ Failed to generate batch tests data.")
                return
                
            logger.info(f"✅ Generated {len(tests)} tests. Sending to channel...")
            
            for test_data in tests:
                if mode == 'poll':
                    options = [test_data['answer']] + test_data.get('incorrect', [])
                    random.shuffle(options)
                    correct_idx = options.index(test_data['answer'])
                    
                    question = test_data.get('question', 'Test Question')
                    explanation = test_data.get('explanation', '')
                    
                    result = await self.telegram.send_poll(
                        chat_id=self.channel_id,
                        question=question,
                        options=options,
                        type='quiz',
                        correct_option_id=correct_idx,
                        explanation=explanation,
                        explanation_parse_mode='HTML'
                    )
                else:
                    formatted_post = self.formatter.format_test(test_data)
    
                    # Inline keyboard buttons
                    options = [test_data['answer']] + test_data.get('incorrect', [])
                    random.shuffle(options)
                    
                    test_id = str(uuid.uuid4())
                    correct_idx = options.index(test_data['answer'])
                    
                    self.active_tests[test_id] = {
                        'options': options,
                        'correct_idx': correct_idx,
                        'votes': {},
                        'counts': {i: 0 for i in range(len(options))},
                        'explanation': test_data.get('explanation', '')
                    }
                    
                    keyboard_buttons = []
                    for i, opt in enumerate(options):
                        keyboard_buttons.append({'text': f'{opt}'.strip(), 'callback_data': f'testvote_{test_id}_{i}'})
    
                    inline_keyboard = []
                    if len(keyboard_buttons) >= 2:
                        inline_keyboard.append([keyboard_buttons[0], keyboard_buttons[1]])
                        if len(keyboard_buttons) > 2:
                            inline_keyboard.append(keyboard_buttons[2:])
                    else:
                        inline_keyboard.append(keyboard_buttons)
    
                    reply_markup = {
                        'inline_keyboard': inline_keyboard
                    }
    
                    result = await self.telegram.send_message(
                        chat_id=self.channel_id,
                        text=formatted_post,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                
                if result.get('ok'):
                    self.test_count += 1
                else:
                    logger.error("❌ Failed to send batch test: %s", result)
                    
                await asyncio.sleep(5)  # Pause to avoid Telegram rate limits

                # Delay of 6 seconds between sending tests to completely avoid Telegram rate limits (max 20 msgs/min in a chat)
                await asyncio.sleep(6)
                
            logger.info(f"✅ Finished sending {len(tests)} tests to channel.")
            
        except Exception as e:
            logger.error("❌ Error sending batch tests: %s", e)

    async def reveal_test_answer(self):
        """Reveal the answer to the current test"""
        try:
            if not self.current_test:
                logger.info("ℹ️ No test to reveal")
                return

            logger.info("✅ Revealing test answer...")

            formatted_reveal = self.formatter.format_answer_reveal(self.current_test)

            result = await self.telegram.send_message(
                chat_id=self.channel_id,
                text=formatted_reveal,
                parse_mode='HTML'
            )
            if result.get('ok'):
                self.current_test = None
                self.test_message_id = None
                logger.info("🎯 Test answer revealed")
            else:
                logger.error("❌ Failed to reveal answer: %s", result)

        except Exception as e:
            logger.error("❌ Error revealing answer: %s", e)

    async def handle_updates(self):
        """Handle incoming updates (commands, callbacks)"""
        while self.running:
            try:
                updates = await self.telegram.get_updates(offset=self.telegram.offset)

                if updates.get('ok') and updates.get('result'):
                    for update in updates['result']:
                        self.telegram.offset = update['update_id'] + 1

                        if 'callback_query' in update:
                            cb_data = update['callback_query'].get('data', '')
                            logger.info(f"📩 Received callback: {cb_data}")
                            asyncio.create_task(self.handle_callback(update['callback_query']))

                        if 'message' in update:
                            msg_text = update['message'].get('text', '')
                            logger.info(f"📩 Received message: {msg_text}")
                            asyncio.create_task(self.handle_message(update['message']))

                await asyncio.sleep(0.3)

            except Exception as e:
                logger.error("❌ Error handling updates: %s", e)
                await asyncio.sleep(2)

    async def handle_callback(self, callback_query: dict):
        """Handle callback queries (button presses)"""
        try:
            query_id = callback_query['id']
            data = callback_query.get('data', '')

            if data.startswith("testmode_"):
                mode = data.split("_")[1]
                chat_id = callback_query['message']['chat']['id']
                self.testtime_state[chat_id] = {'step': 'topic', 'mode': mode}
                
                # Update the message to remove buttons and confirm
                mode_name = "Inline Buttons" if mode == 'inline' else "Native Quizzes"
                await self.telegram.edit_message_reply_markup(chat_id, callback_query['message']['message_id'], None)
                await self.telegram.answer_callback_query(query_id, f"Selected {mode_name}!")
                await self.telegram.send_message(chat_id, "What topic do you want 10 tests for? 📝", parse_mode='HTML')
            elif data.startswith("singletest_"):
                mode = data.split("_")[1]
                chat_id = callback_query['message']['chat']['id']
                
                # Update the message to remove buttons and confirm
                mode_name = "Inline Buttons" if mode == 'inline' else "Native Quiz"
                await self.telegram.edit_message_reply_markup(chat_id, callback_query['message']['message_id'], None)
                await self.telegram.answer_callback_query(query_id, f"Selected {mode_name}!")
                await self.telegram.send_message(chat_id, f"⏳ Generating a single test in {mode_name} format... 🧪", parse_mode='HTML')
                asyncio.create_task(self.send_test(mode=mode))
            elif data.startswith("changemodel_"):
                model_idx = data.split("_")[1]
                chat_id = callback_query['message']['chat']['id']
                self.waiting_for_model[chat_id] = model_idx
                
                await self.telegram.edit_message_reply_markup(chat_id, callback_query['message']['message_id'], None)
                await self.telegram.answer_callback_query(query_id)
                await self.telegram.send_message(chat_id, f"Please enter the new OpenRouter model name for Model {model_idx} (e.g., <code>anthropic/claude-3-haiku</code>):", parse_mode='HTML')
            elif data.startswith("testvote_"):
                parts = data.split("_")
                if len(parts) == 3:
                    test_id = parts[1]
                    option_idx = int(parts[2])
                    user_id = callback_query['from']['id']

                            
                    test_state = self.active_tests.get(test_id)
                    if not test_state:
                        await self.telegram.answer_callback_query(query_id, "❌ This test is no longer active.")
                        return

                    # Record vote
                    old_vote = test_state['votes'].get(user_id)
                    correct_opt = test_state['options'][test_state['correct_idx']]
                    
                    if old_vote is not None:
                        if old_vote == option_idx:
                            if option_idx == test_state['correct_idx']:
                                await self.telegram.answer_callback_query(query_id, "✅ Correct! Great job! 🎉", show_alert=True)
                            else:
                                explanation = test_state.get('explanation', '')
                                alert_text = f"❌ Incorrect!\n\n✅ True answer: {correct_opt}\n\n💡 {explanation}"
                                if len(alert_text) > 190: alert_text = alert_text[:187] + "..."
                                await self.telegram.answer_callback_query(query_id, alert_text, show_alert=True)
                        else:
                            await self.telegram.answer_callback_query(
                                query_id,
                                "You have already voted! You cannot change your answer. 🚫",
                                show_alert=True
                            )
                        return

                    test_state['votes'][user_id] = option_idx
                    test_state['counts'][option_idx] += 1

                    if option_idx == test_state['correct_idx']:
                        await self.telegram.answer_callback_query(query_id, "✅ Correct! Great job! 🎉", show_alert=True)
                    else:
                        explanation = test_state.get('explanation', '')
                        alert_text = f"❌ Incorrect!\n\n✅ True answer: {correct_opt}\n\n💡 {explanation}"
                        if len(alert_text) > 190: alert_text = alert_text[:187] + "..."
                        await self.telegram.answer_callback_query(query_id, alert_text, show_alert=True)

                    # Rebuild keyboard
                    keyboard_buttons = []
                    for i, opt in enumerate(test_state['options']):
                        count = test_state['counts'][i]
                        text = f"{opt} ({count})" if count > 0 else opt
                        keyboard_buttons.append({'text': text, 'callback_data': f'testvote_{test_id}_{i}'})

                    inline_keyboard = []
                    if len(keyboard_buttons) >= 2:
                        inline_keyboard.append([keyboard_buttons[0], keyboard_buttons[1]])
                        if len(keyboard_buttons) > 2:
                            inline_keyboard.append(keyboard_buttons[2:])
                    else:
                        inline_keyboard.append(keyboard_buttons)

                    reply_markup = {'inline_keyboard': inline_keyboard}

                    message = callback_query.get('message')
                    if message:
                        await self.telegram.edit_message_reply_markup(
                            message['chat']['id'],
                            message['message_id'],
                            reply_markup
                        )
            elif data.startswith("test_answer_"):
                await self.telegram.answer_callback_query(
                    query_id,
                    "✅ Thanks for participating! 🎯 Answer will be revealed soon. ⏳"
                )
        except Exception as e:
            logger.error("❌ Error handling callback: %s", e)

    async def handle_message(self, message: dict):
        """Handle incoming messages"""
        try:
            text = message.get('text', '')
            chat_id = message['chat']['id']

            # Check if we are waiting for a topic from this user
            if chat_id in self.testtime_state and not text.startswith('/'):
                state = self.testtime_state[chat_id]
                if state.get('step') == 'topic':
                    mode = state.get('mode', 'inline')
                    del self.testtime_state[chat_id]
                    await self.telegram.send_message(chat_id, f"⏳ Generating 10 tests about '{text}'. This might take a minute... 🧪", parse_mode='HTML')
                    asyncio.create_task(self.generate_and_send_batch_tests(text, mode=mode))
                    return

            # Check if we are waiting for a model name
            if self.waiting_for_model.get(chat_id) and not text.startswith('/'):
                model_idx = self.waiting_for_model[chat_id]
                self.waiting_for_model[chat_id] = False
                new_model = text.strip()
                if model_idx == '1':
                    self.ai_client.openrouter_model = new_model
                    await self.telegram.send_message(chat_id, f"✅ Primary OpenRouter model successfully changed to: <code>{new_model}</code>", parse_mode='HTML')
                elif model_idx == '2':
                    self.ai_client.openrouter_model_2 = new_model
                    await self.telegram.send_message(chat_id, f"✅ Secondary OpenRouter model successfully changed to: <code>{new_model}</code>", parse_mode='HTML')
                else:
                    self.ai_client.openrouter_model_3 = new_model
                    await self.telegram.send_message(chat_id, f"✅ Tertiary OpenRouter model successfully changed to: <code>{new_model}</code>", parse_mode='HTML')
                return

            if text == '/start':
                welcome = """🌟 <b>Improve Your English</b> 🌟

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

Use /help for commands. 📋"""
                await self.telegram.send_message(chat_id, welcome, parse_mode='HTML')

            elif text == '/help':
                help_text = """📋 <b>Bot Commands</b>

/start — 🌟 Welcome message
/help — 📋 This message
/status — 📊 Bot statistics
/lesson — 📚 Get a lesson now
/test — 🧪 Get a test now
/testtime — 📚 Generate 10 tests for a topic
/model — 🤖 Change AI model
/reset — 🔄 Reset topic history

⏰ <b>Schedule</b>
📚 • Lessons: every 4 hours (6/day)
🧪 • Tests: every 12 hours (2/day)

💡 <b>Tips</b>
💾 • Save posts for later review
👆 • Participate in tests
🔄 • Topics never repeat!"""
                await self.telegram.send_message(chat_id, help_text, parse_mode='HTML')

            elif text == '/status':
                status = f"""📊 <b>Bot Status</b>

📚 Posts sent: <b>{self.post_count}</b>
🧪 Tests sent: <b>{self.test_count}</b>
📝 Topics in history: <b>{self.topic_history.get_history_count()}</b>

⏰ Next posts scheduled automatically.
🟢 Bot is running smoothly!"""
                await self.telegram.send_message(chat_id, status, parse_mode='HTML')

            elif text == '/lesson':
                await self.telegram.send_message(chat_id, "⏳ Generating lesson... 📚", parse_mode='HTML')
                await self.send_lesson()

            elif text == '/test':
                keyboard = {
                    'inline_keyboard': [
                        [
                            {'text': '🔘 Inline Buttons', 'callback_data': 'singletest_inline'},
                            {'text': '📊 Native Quiz', 'callback_data': 'singletest_poll'}
                        ]
                    ]
                }
                await self.telegram.send_message(
                    chat_id, 
                    "How would you like to send this test? ⚙️\n\n🔘 <b>Inline Buttons</b>: Custom buttons with live vote counts.\n📊 <b>Native Quiz</b>: Telegram's built-in poll with offline support.", 
                    parse_mode='HTML',
                    reply_markup=keyboard
                )

            elif text == '/testtime':
                keyboard = {
                    'inline_keyboard': [
                        [
                            {'text': '🔘 Inline Buttons', 'callback_data': 'testmode_inline'},
                            {'text': '📊 Native Quizzes', 'callback_data': 'testmode_poll'}
                        ]
                    ]
                }
                await self.telegram.send_message(
                    chat_id, 
                    "How would you like to send the tests? ⚙️\n\n🔘 <b>Inline Buttons</b>: Custom buttons with live vote counts.\n📊 <b>Native Quizzes</b>: Telegram's built-in polls with offline support and animations.", 
                    parse_mode='HTML',
                    reply_markup=keyboard
                )

            elif text == '/model':
                keyboard = {
                    'inline_keyboard': [
                        [
                            {'text': '🔧 Change Primary Model', 'callback_data': 'changemodel_1'},
                        ],
                        [
                            {'text': '🔧 Change Secondary Model', 'callback_data': 'changemodel_2'}
                        ],
                        [
                            {'text': '🔧 Change Tertiary Model', 'callback_data': 'changemodel_3'}
                        ]
                    ]
                }
                await self.telegram.send_message(
                    chat_id, 
                    f"<b>Current Models:</b>\n"
                    f"1️⃣ Primary: <code>{self.ai_client.openrouter_model}</code>\n"
                    f"2️⃣ Secondary: <code>{self.ai_client.openrouter_model_2}</code>\n"
                    f"3️⃣ Tertiary: <code>{self.ai_client.openrouter_model_3}</code>\n\n"
                    f"Which model would you like to change?", 
                    parse_mode='HTML',
                    reply_markup=keyboard
                )

            elif text == '/reset':
                self.topic_history.reset_history()
                await self.telegram.send_message(chat_id, "🔄 Topic history has been reset! ✅", parse_mode='HTML')

        except Exception as e:
            logger.error("❌ Error handling message: %s", e)


async def main():
    """Main function to run the bot"""
    logger.info("🌟 Starting English Teaching Bot...")

    bot = EnglishBot()

    # Start scheduler
    await bot.start_scheduler()

    # Send first lesson immediately
    await bot.send_lesson()

    # Start handling updates
    logger.info("🟢 Bot is running...")
    await bot.handle_updates()


if __name__ == '__main__':
    asyncio.run(main())