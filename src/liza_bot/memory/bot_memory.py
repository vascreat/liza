import json
import time

from liza_bot.config import *

class memory_manager:
    """
    Manages bot memory
    """
    
    def __init__(self):
        self.memory = self.load_memory()
        self.history = self.memory.get('history', [])
        self.conversation_histories = self.memory.get('conversation_histories', {})

        
        print(f'✅ History loaded ({len(self.history)} messages)')
        print(f'📝 Last conversation: {self.memory.get("last_user") or "(none)"}')
        print(f'🔇 Silent errors: {SILENT_ERRORS}')
        print(f'🔗 Ollama URL: {OLLAMA_URL}')

    def load_memory(self):
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return {
                        'history': data.get('history', []),
                        'last_user': data.get('last_user'),
                        'interlocutors': data.get('interlocutors', []),
                        'switches': data.get('switches', []),
                        'conversation_histories': {
                            key: value for key, value in data.get('conversation_histories', {}).items()
                            if isinstance(value, list)
                        },
                    }
                if isinstance(data, list):
                    return {
                        'history': data,
                        'last_user': None,
                        'interlocutors': [],
                        'switches': [],
                        'conversation_histories': {},
                    }
            except Exception as exc:
                print(f'[⚠️] Error loading memory: {exc}')
        return {'history': [], 'last_user': None, 'interlocutors': [], 'switches': [], 'conversation_histories': {}}


    def save_memory(self,mem):
        try:
            mem_to_save = dict(mem)
            mem_to_save['history'] = mem_to_save.get('history', [])[-MAX_HISTORY_SIZE:]
            conversation_histories = {}
            for key, history in mem_to_save.get('conversation_histories', {}).items():
                if isinstance(history, list):
                    conversation_histories[key] = history[-MAX_HISTORY_SIZE:]
            mem_to_save['conversation_histories'] = conversation_histories
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(mem_to_save, f, ensure_ascii=False, indent=2)
            self.memory = mem_to_save
            self.history = self.memory['history']
            self.conversation_histories = self.memory['conversation_histories']
        except Exception as exc:
            print(f'[⚠️] Error saving memory: {exc}')


    def update_conversation_memory(self,user):
        prev_user = self.memory.get('last_user')
        if user not in self.memory.setdefault('interlocutors', []):
            self.memory['interlocutors'].append(user)
        if prev_user and prev_user != user:
            self.memory.setdefault('switches', []).append({
                'from': prev_user,
                'to': user,
                'when': int(time.time()),
            })
        self.memory['last_user'] = user
        self.save_memory(self.memory)


    def get_history(self, conversation_key=None):
        if not conversation_key:
            return self.history
        return self.memory.setdefault('conversation_histories', {}).setdefault(conversation_key, [])


    def append_exchange(self, conversation_key, user, text, answer):
        user_line = f'{user}: {text}'
        bot_line = f'Bot: {answer}'
        self.history.append(user_line)
        self.history.append(bot_line)
        scoped_history = self.get_history(conversation_key)
        scoped_history.append(user_line)
        scoped_history.append(bot_line)
        self.memory['history'] = self.history
        self.memory['conversation_histories'] = self.conversation_histories
        self.save_memory(self.memory)


    def show_memory(self, count=10):
        if not self.history:
            print('📝 Memory is empty')
            return

        print(f'📝 Last interlocutor: {self.memory.get("last_user") or "none"}')
        if self.memory.get('interlocutors'):
            print(f'📝 Nicknames in memory: {", ".join(self.memory.get("interlocutors", []))}')
        if self.memory.get('switches'):
            print('📝 Switches between interlocutors:')
            for sw in self.memory['switches'][-5:]:
                when = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(sw['when']))
                print(f'  {when}: {sw["from"]} -> {sw["to"]}')

        recent = self.history[-count * 2:]
        print(f'\n📝 === LAST {len(recent) // 2} REQUESTS ===')
        for i in range(0, len(recent), 2):
            if i + 1 < len(recent):
                print(f'{recent[i]}\n{recent[i+1]}\n')


    def get_last_response(self, conversation_key=None):
        history = self.get_history(conversation_key)
        if len(history) >= 2:
            return history[-1]
        if conversation_key and len(self.history) >= 2:
            return self.history[-1]
        return None


    def is_bot_mentioned(self,message: str) -> bool:
        lower = message.lower().strip()
        if f'@{BOT_NICK}' in lower or '@лиза' in lower or '@лизанька' in lower:
            return True
        if lower.startswith(BOT_NICK) or lower.startswith('лиза') or lower.startswith('лизанька'):
            return True
        return False