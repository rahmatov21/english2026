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

# Fix Windows console encoding safely
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'buffer') and not getattr(sys.stdout, '_is_utf8_wrapped', False):
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stdout._is_utf8_wrapped = True
        except Exception:
            pass
    if hasattr(sys.stderr, 'buffer') and not getattr(sys.stderr, '_is_utf8_wrapped', False):
        try:
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
            sys.stderr._is_utf8_wrapped = True
        except Exception:
            pass

from config import (
    BOT_TOKEN, CHANNEL_ID, POST_INTERVAL_HOURS, TEST_INTERVAL_HOURS,
    TOPICS_DATA, GENERAL_TAGS, CATEGORY_ROTATION
)
import random
from ai_client import AIClient
from topic_history import TopicHistory
from post_formatter import PostFormatter
from portfolio_viewer import format_portfolio_message, save_subscriber_chat_id

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class TelegramAPI:
    """Simple Telegram Bot API wrapper using HTTP requests with retries and timeout protection"""

    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0

    async def _make_request(self, method: str, data: dict = None, timeout: int = 35, retries: int = 3) -> dict:
        """Make HTTP request to Telegram API with automatic retries for timeouts/network errors"""
        url = f"{self.base_url}/{method}"

        if data:
            payload = json.dumps(data).encode('utf-8')
            request = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        else:
            request = urllib.request.Request(url)

        def do_req():
            for attempt in range(1, retries + 1):
                try:
                    with urllib.request.urlopen(request, timeout=timeout) as response:
                        return json.loads(response.read().decode('utf-8'))
                except urllib.error.HTTPError as e:
                    error_msg = e.read().decode()
                    if method == 'answerCallbackQuery' and 'query is too old' in error_msg:
                        return {'ok': False, 'error': 'query too old'}
                    if method == 'editMessageReplyMarkup' and ('message is not modified' in error_msg or 'message to edit not found' in error_msg):
                        return {'ok': False, 'error': 'edit skipped'}
                    if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                        wait_sec = attempt * 2
                        logger.warning(f"Telegram HTTP {e.code} on {method}. Retrying in {wait_sec}s (attempt {attempt}/{retries})...")
                        time.sleep(wait_sec)
                        continue
                    logger.error(f"HTTP Error {e.code}: {error_msg}")
                    return {'ok': False, 'error': str(e)}
                except Exception as e:
                    err_str = str(e)
                    if attempt < retries and any(k in err_str.lower() for k in ['timed out', 'timeout', 'reset', 'disconnected', 'temporary']):
                        wait_sec = attempt * 2
                        logger.warning(f"Telegram {method} attempt {attempt} failed ({e}). Retrying in {wait_sec}s...")
                        time.sleep(wait_sec)
                        continue
                    logger.error(f"Request error: {e}")
                    return {'ok': False, 'error': str(e)}
            return {'ok': False, 'error': 'all retries failed'}
        
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

        return await self._make_request('sendMessage', data, timeout=35, retries=3)

    async def get_updates(self, offset: int = None, limit: int = 100) -> dict:
        """Get updates from Telegram"""
        data = {'limit': limit, 'timeout': 1}
        if offset:
            data['offset'] = offset

        return await self._make_request('getUpdates', data, timeout=15, retries=1)

    async def answer_callback_query(self, callback_query_id: str, text: str = None, show_alert: bool = False) -> dict:
        """Answer a callback query"""
        data = {'callback_query_id': callback_query_id}
        if text:
            data['text'] = text
        if show_alert:
            data['show_alert'] = True

        return await self._make_request('answerCallbackQuery', data, timeout=15, retries=2)

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
            
        return await self._make_request('editMessageReplyMarkup', data, timeout=20, retries=2)

    async def edit_message_text(self, chat_id: str, message_id: int, text: str, parse_mode: str = 'HTML', reply_markup: dict = None) -> dict:
        """Edit the text and keyboard of an existing message"""
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': parse_mode
        }
        if reply_markup is not None:
            data['reply_markup'] = reply_markup
        return await self._make_request('editMessageText', data, timeout=25, retries=2)

    async def get_chat_member(self, chat_id: str, user_id: int) -> dict:
        """Get information about a member of a chat"""
        data = {
            'chat_id': chat_id,
            'user_id': user_id
        }
        return await self._make_request('getChatMember', data, timeout=20, retries=2)

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
            
        return await self._make_request('sendPoll', data, timeout=35, retries=3)

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
        self.category_idx = 0
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

        self.scheduler.add_job(
            self.send_test,
            'interval',
            hours=TEST_INTERVAL_HOURS,
            id='test_job',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("🚀 Scheduler started — lessons every %dh, tests every %dh", POST_INTERVAL_HOURS, TEST_INTERVAL_HOURS)

    def _select_next_topic(self) -> dict:
        """
        Intelligently selects the next topic using category rotation and cooldown memory.
        Ensures diverse skills are covered throughout the day and no topic repeats prematurely.
        """
        total_cats = len(CATEGORY_ROTATION)

        # Try up to total_cats to find a category with available (non-cooldown) topics
        for offset in range(total_cats):
            cat_idx = (self.category_idx + offset) % total_cats
            cat_name = CATEGORY_ROTATION[cat_idx]
            cat_data = TOPICS_DATA.get(cat_name)
            if not cat_data:
                continue

            # Filter out topics currently in cooldown
            eligible = [
                t for t in cat_data["topics"]
                if not self.topic_history.is_topic_recent(t)
            ]

            if eligible:
                self.category_idx = cat_idx + 1
                selected_topic = random.choice(eligible)
                return {
                    "category": cat_name,
                    "topic": selected_topic,
                    "tags": cat_data.get("tags", [])
                }

        # If all topics across all categories are in cooldown, trigger soft cooldown reset
        logger.warning("All curriculum topics are currently in cooldown! Refreshing topic cooldown buffer...")
        self.topic_history.reset_cooldown()

        cat_name = CATEGORY_ROTATION[self.category_idx % total_cats]
        self.category_idx += 1
        cat_data = TOPICS_DATA[cat_name]
        selected_topic = random.choice(cat_data["topics"])
        return {
            "category": cat_name,
            "topic": selected_topic,
            "tags": cat_data.get("tags", [])
        }

    async def send_lesson(self):
        """Generate and send a lesson to the channel with deep anti-repetition memory"""
        try:
            logger.info("📚 Selecting next skill and generating lesson...")

            selected = self._select_next_topic()
            selected_category = selected["category"]
            selected_topic = selected["topic"]
            selected_tags = selected["tags"]

            logger.info(f"🎯 Target Skill: [{selected_category}] -> '{selected_topic}'")

            memory_context = self.topic_history.get_lesson_memory_context(
                category=selected_category,
                topic=selected_topic
            )

            lesson_data = await self.ai_client.generate_lesson(
                topic=selected_topic,
                category=selected_category,
                memory_context=memory_context
            )

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
                self.topic_history.add_lesson_entry(
                    topic=lesson_data.get('topic', selected_topic),
                    content=lesson_data.get('content', ''),
                    category=selected_category,
                    target_items=lesson_data.get('target_items')
                )
                self.post_count += 1
                logger.info("✅ Lesson sent & registered in deep memory: %s (Post #%d)", lesson_data.get('topic'), self.post_count)
            else:
                logger.error("❌ Failed to send lesson: %s", result)

        except Exception as e:
            logger.error("❌ Error sending lesson: %s", e)

    async def send_test(self, mode: str = 'poll'):
        """Generate and send an interactive test with anti-repetition memory"""
        try:
            logger.info("🧪 Generating test with memory context...")

            memory_context = self.topic_history.get_test_memory_context()
            test_data = await self.ai_client.generate_test(memory_context=memory_context)
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
                    self.topic_history.add_test_entry("Quiz", test_data.get('question', ''), test_data.get('answer', ''))
                    logger.info("✅ Poll Test sent (Test #%d)", self.test_count)
                else:
                    logger.error("❌ Failed to send poll test: %s", result)
            else:
                formatted_post = self.formatter.format_test(test_data)
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

                reply_markup = {'inline_keyboard': inline_keyboard}

                result = await self.telegram.send_message(
                    chat_id=self.channel_id,
                    text=formatted_post,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                if result.get('ok'):
                    self.test_message_id = result['result']['message_id']
                    self.test_count += 1
                    self.topic_history.add_test_entry("Quiz", test_data.get('question', ''), test_data.get('answer', ''))
                    logger.info("✅ Test sent (Test #%d)", self.test_count)
                else:
                    logger.error("❌ Failed to send test: %s", result)

        except Exception as e:
            logger.error("❌ Error sending test: %s", e)

    async def generate_and_send_batch_tests(self, topic: str, mode: str = 'inline'):
        """Generate and send 10 tests for a given topic"""
        try:
            logger.info(f"🧪 Generating 10 tests for topic: {topic} (Mode: {mode})...")

            memory_context = self.topic_history.get_test_memory_context()
            tests = await self.ai_client.generate_batch_tests(topic, memory_context=memory_context)
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

                    reply_markup = {'inline_keyboard': inline_keyboard}

                    result = await self.telegram.send_message(
                        chat_id=self.channel_id,
                        text=formatted_post,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )

                if result.get('ok'):
                    self.test_count += 1
                    self.topic_history.add_test_entry(topic, test_data.get('question', ''), test_data.get('answer', ''))
                else:
                    logger.error("❌ Failed to send batch test: %s", result)

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

            if data == "refresh_portfolio":
                chat_id = callback_query['message']['chat']['id']
                msg_id = callback_query['message']['message_id']
                save_subscriber_chat_id(chat_id)
                new_text, new_kb = format_portfolio_message()
                await self.telegram.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=new_text,
                    parse_mode='HTML',
                    reply_markup=new_kb
                )
                await self.telegram.answer_callback_query(query_id, "✅ Portfolio updated with live prices!")
                return
            elif data.startswith("testmode_"):
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
/portfolio — 📊 View crypto trading portfolio & P&L
/status — 📈 Bot statistics
/lesson — 📚 Get a lesson now
/test — 🧪 Get a test now
/testtime — 📚 Generate 10 tests for a topic
/model — 🤖 Change AI model
/reset — 🔄 Reset topic history

⏰ <b>Schedule</b>
📚 • Lessons: every 4 hours (6/day)
🧪 • Tests: every 12 hours (2/day)
📊 • Trading: real-time 1h LuxAlgo signals

💡 <b>Tips</b>
💾 • Save posts for later review
👆 • Participate in tests
📊 • Use /portfolio to check real-time crypto positions!"""
                await self.telegram.send_message(chat_id, help_text, parse_mode='HTML')

            elif text in ('/portfolio', '/trade', '/crypto'):
                save_subscriber_chat_id(chat_id)
                msg_text, reply_markup = format_portfolio_message()
                await self.telegram.send_message(
                    chat_id,
                    msg_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )

            elif text == '/status':
                stats = self.topic_history.get_stats()
                next_cat = CATEGORY_ROTATION[self.category_idx % len(CATEGORY_ROTATION)]
                status = f"""📊 <b>Bot & Memory Status</b>

📚 Lessons Posted: <b>{self.post_count}</b>
🧪 Quizzes Posted: <b>{self.test_count}</b>
🧠 Detailed Lesson Records: <b>{stats['total_lessons']}</b>

━━━━━━━━━━━━━━━━━━━━━
🧠 <b>Deep Anti-Repetition Memory:</b>
• 📦 Unique Items Taught: <b>{stats['unique_items_taught']}</b>
  ├ 🔤 Vocabulary Words: <b>{stats['vocabulary_count']}</b>
  ├ 🔗 Phrasal Verbs: <b>{stats['phrasal_verbs_count']}</b>
  ├ 💬 Idioms & Phrases: <b>{stats['idioms_count']}</b>
  ├ 📐 Grammar Rules: <b>{stats['grammar_rules_count']}</b>
  ├ 🤝 Collocations: <b>{stats['collocations_count']}</b>
  └ ⚠️ Confused Pairs: <b>{stats['mistakes_count']}</b>

🔄 <b>Topic Cooldown Buffer:</b>
• ⏳ Active in Cooldown: <b>{stats['topics_in_cooldown']} / {stats['cooldown_limit']}</b>
• 📚 Total Curriculum Topics: <b>120+ across 10 categories</b>
• 🎯 Next Target Skill: <b>{next_cat}</b>

🟢 Bot is running smoothly & scheduled!"""
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
                self.topic_history.reset_cooldown()
                await self.telegram.send_message(
                    chat_id,
                    "🔄 <b>Topic cooldown buffer has been refreshed!</b>\n\nAll 120+ curriculum topics are now eligible for selection, while all previously taught vocabulary words, idioms, and grammar points remain registered in memory to prevent repetition. ✅",
                    parse_mode='HTML'
                )

            elif text == '/resetall':
                self.topic_history.reset_history(full_wipe=True)
                await self.telegram.send_message(chat_id, "⚠️ <b>Full memory wipe completed!</b> All history and taught item registers have been reset.", parse_mode='HTML')

        except Exception as e:
            logger.error("❌ Error handling message: %s", e)


async def main():
    """Main function to run the bot"""
    logger.info("🌟 Starting English Teaching Bot...")

    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        logger.error("❌ BOT_TOKEN is not configured! Please check your .env file.")
        return

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