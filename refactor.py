import sys
import re
import json

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Make TelegramAPI methods async
content = content.replace('def _make_request(self', 'async def _make_request(self')
content = content.replace('def send_message(self', 'async def send_message(self')
content = content.replace('def get_updates(self', 'async def get_updates(self')
content = content.replace('def answer_callback_query(self', 'async def answer_callback_query(self')
content = content.replace('def edit_message_reply_markup(self', 'async def edit_message_reply_markup(self')
content = content.replace('def get_chat_member(self', 'async def get_chat_member(self')
content = content.replace('def send_poll(self', 'async def send_poll(self')

# Await inner calls
content = content.replace('return self._make_request', 'return await self._make_request')

# Await TelegramAPI calls throughout bot.py
content = content.replace('self.telegram.send_message(', 'await self.telegram.send_message(')
content = content.replace('self.telegram.send_poll(', 'await self.telegram.send_poll(')
content = content.replace('self.telegram.get_updates(', 'await self.telegram.get_updates(')
content = content.replace('self.telegram.answer_callback_query(', 'await self.telegram.answer_callback_query(')
content = content.replace('self.telegram.edit_message_reply_markup(', 'await self.telegram.edit_message_reply_markup(')
content = content.replace('self.telegram.get_chat_member(', 'await self.telegram.get_chat_member(')

# Fix _make_request to use asyncio.to_thread
pattern = re.compile(r'async def _make_request\(self, method: str, data: dict = None\) -\> dict:.*?try:.*?return \{\'ok\': False, \'error\': str\(e\)\}', re.DOTALL)
match = pattern.search(content)

if match:
    old_body = match.group(0)
    new_body = r'''async def _make_request(self, method: str, data: dict = None) -> dict:
        """Make HTTP request to Telegram API"""
        url = f"{self.base_url}/{method}"

        if data:
            payload = json.dumps(data).encode('utf-8')
            request = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        else:
            request = urllib.request.Request(url)

        def do_req():
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                error_msg = e.read().decode()
                if method == 'answerCallbackQuery' and 'query is too old' in error_msg:
                    return {'ok': False, 'error': 'query too old'}
                logger.error(f"HTTP Error {e.code}: {error_msg}")
                return {'ok': False, 'error': str(e)}
            except Exception as e:
                logger.error(f"Request error: {e}")
                return {'ok': False, 'error': str(e)}
        
        return await asyncio.to_thread(do_req)'''
    content = content.replace(old_body, new_body)
else:
    print('regex failed')
    sys.exit(1)

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Success')
