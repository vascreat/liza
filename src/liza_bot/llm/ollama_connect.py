import requests

from liza_bot.config import *
from liza_bot.memory.bot_memory import memory_manager

class ollama_connect:

    def __init__(self, bot_memory=None, twitch_bot=None):
        self.botMemory = bot_memory or memory_manager()
        self.memory = self.botMemory.memory
        self.twitchBot = twitch_bot

    def ask_ollama(self, user: str, text: str, conversation_key=None) -> str | None:
        history = self.botMemory.get_history(conversation_key)
        context = '\n'.join(history[-6:])
        prompt = f"""
    Ты весёлый Twitch чат-бот по имени лиза. Отвечай очень коротко, с юмором и только на русском языке.
    Если задают вопрос на другом языке, всё равно отвечай по-русски.

    Контекст:
    {context}

    {user}: {text}
    Бот:
    """
        try:
            r = requests.post(
                OLLAMA_URL,
                json={'model': MODEL, 'prompt': prompt, 'stream': False},
                timeout=20,
            )
            if r.status_code != 200:
                print(f'[⚠️ ОШИБКА] Ollama вернул {r.status_code}')
                if last_resp := self.botMemory.get_last_response(conversation_key):
                    return last_resp
                if SILENT_ERRORS:
                    return None
                return 'Ошибка ИИ 😢'
            data = r.json()
            answer = data.get('response')
            if not answer:
                print('[⚠️ ОШИБКА] Ollama вернул пустой ответ')
                if last_resp := self.botMemory.get_last_response(conversation_key):
                    return last_resp
                if SILENT_ERRORS:
                    return None
                return 'Ошибка ИИ 😢'
            self.botMemory.append_exchange(conversation_key, user, text, answer)
            return answer.strip()
        except requests.RequestException as exc:
            print(f'[⚠️ ОШИБКА] Ollama недоступен: {exc}')
            if last_resp := self.botMemory.get_last_response(conversation_key):
                return last_resp
            if SILENT_ERRORS:
                return None
            return 'Ошибка ИИ 😢'
        except Exception as exc:
            print(f'[⚠️ ОШИБКА] Ошибка парсинга: {exc}')
            if last_resp := self.botMemory.get_last_response(conversation_key):
                return last_resp
            if SILENT_ERRORS:
                return None
            return 'Ошибка ИИ 😢'

    def parse_channel_name(self, text: str) -> str:
        return text.strip().lstrip('#').lower()