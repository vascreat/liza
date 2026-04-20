<<<<<<< HEAD
import asyncio
import base64
import json
import os
import re
import time
from pathlib import Path

import requests


# ================== Настройки ==================
BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / '.env'


def load_env(path: Path):
    if not path.exists():
        return
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value


load_env(ENV_FILE)

TWITCH_TOKEN = os.getenv('TWITCH_TOKEN', '').strip()
BOT_NICK = os.getenv('BOT_NICK', 'liza').strip().lower()
MODEL = os.getenv('MODEL', 'liza:latest')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
SILENT_ERRORS = os.getenv('SILENT_ERRORS', 'false').lower() in ('1', 'true', 'yes')
COOLDOWN = float(os.getenv('COOLDOWN', '2'))
MAX_LEN = int(os.getenv('MAX_LEN', '500'))


if not TWITCH_TOKEN:
    raise SystemExit('Missing required env var: TWITCH_TOKEN')
if not TWITCH_TOKEN.startswith('oauth:'):
    raise SystemExit('TWITCH_TOKEN must start with oauth:')


# ================== Память ==================
MEMORY_FILE = BASE_DIR / 'bot_memory.json'
MAX_HISTORY_SIZE = 50


def load_memory():
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
                }
            if isinstance(data, list):
                return {
                    'history': data,
                    'last_user': None,
                    'interlocutors': [],
                    'switches': [],
                }
        except Exception as exc:
            print(f'[⚠️] Ошибка при загрузке памяти: {exc}')
    return {'history': [], 'last_user': None, 'interlocutors': [], 'switches': []}


def save_memory(mem):
    try:
        mem_to_save = dict(mem)
        mem_to_save['history'] = mem_to_save.get('history', [])[-MAX_HISTORY_SIZE:]
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(mem_to_save, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f'[⚠️] Ошибка при сохранении памяти: {exc}')


def update_conversation_memory(user):
    prev_user = memory.get('last_user')
    if user not in memory.setdefault('interlocutors', []):
        memory['interlocutors'].append(user)
    if prev_user and prev_user != user:
        memory.setdefault('switches', []).append({
            'from': prev_user,
            'to': user,
            'when': int(time.time()),
        })
    memory['last_user'] = user
    save_memory(memory)


def show_memory(count=10):
    if not history:
        print('📝 Память пуста')
        return

    print(f'📝 Последний собеседник: {memory.get("last_user") or "нет"}')
    if memory.get('interlocutors'):
        print(f'📝 Ники в памяти: {", ".join(memory.get("interlocutors", []))}')
    if memory.get('switches'):
        print('📝 Переключения между собеседниками:')
        for sw in memory['switches'][-5:]:
            when = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(sw['when']))
            print(f'  {when}: {sw["from"]} -> {sw["to"]}')

    recent = history[-count * 2:]
    print(f'\n📝 === ПОСЛЕДНИЕ {len(recent) // 2} ЗАПРОСОВ ===')
    for i in range(0, len(recent), 2):
        if i + 1 < len(recent):
            print(f'{recent[i]}\n{recent[i+1]}\n')


def get_last_response():
    if len(history) >= 2:
        return history[-1]
    return None


def is_bot_mentioned(message: str) -> bool:
    lower = message.lower().strip()
    if f'@{BOT_NICK}' in lower or '@лиза' in lower or '@лизанька' in lower:
        return True
    if lower.startswith(BOT_NICK) or lower.startswith('лиза') or lower.startswith('лизанька'):
        return True
    return False


# ================== Логика ==================
memory = load_memory()
history = memory.get('history', [])
last_reply = 0
print(f'✅ История загружена ({len(history)} сообщений)')
print(f'📝 Последний собеседник: {memory.get("last_user") or "(none)"}')
print(f'🔇 Тихий режим: {SILENT_ERRORS}')
print(f'🔗 Ollama URL: {OLLAMA_URL}')
print(f'📸 Режим видео: Vision (анализ изображений)')


def ask_ollama_vision(image_frame, prompt_text: str = "Опиши, что ты видишь на этом изображении. Ответь коротко на русском.") -> str | None:
    """Отправляет кадр как изображение в Ollama для анализа (vision mode).
    
    Ожидает image_frame в RGB формате.
    """
    try:
        import cv2
    except ImportError:
        print('[⚠️] OpenCV не установлен')
        return None
    
    try:
        # imencode работает ТОЛЬКО с BGR форматом для JPG
        # Конвертируем RGB -> BGR перед кодированием
        frame_bgr = cv2.cvtColor(image_frame, cv2.COLOR_RGB2BGR)
        _, buffer = cv2.imencode('.jpg', frame_bgr)
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        
        r = requests.post(
            f'{OLLAMA_URL}/api/generate',
            json={
                'model': MODEL,
                'prompt': prompt_text,
                'images': [image_base64],
                'stream': False,
            },
            timeout=30,
        )
        
        if r.status_code != 200:
            print(f'[⚠️ ОШИБКА] Ollama вернул {r.status_code}')
            return None
        
        data = r.json()
        answer = data.get('response', '').strip()
        if not answer:
            print('[⚠️ ОШИБКА] Ollama вернул пустой ответ')
            return None
        return answer
    except requests.RequestException as exc:
        print(f'[⚠️ ОШИБКА] Ollama недоступен: {exc}')
        return None
    except Exception as exc:
        print(f'[⚠️ ОШИБКА] Ошибка отправки изображения: {exc}')
        return None


def ask_ollama(user: str, text: str) -> str | None:
    global history
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
            if last_resp := get_last_response():
                return last_resp
            if SILENT_ERRORS:
                return None
            return 'Ошибка ИИ 😢'
        data = r.json()
        answer = data.get('response')
        if not answer:
            print('[⚠️ ОШИБКА] Ollama вернул пустой ответ')
            if last_resp := get_last_response():
                return last_resp
            if SILENT_ERRORS:
                return None
            return 'Ошибка ИИ 😢'
        history.append(f'{user}: {text}')
        history.append(f'Бот: {answer}')
        memory['history'] = history
        save_memory(memory)
        return answer.strip()
    except requests.RequestException as exc:
        print(f'[⚠️ ОШИБКА] Ollama недоступен: {exc}')
        if last_resp := get_last_response():
            return last_resp
        if SILENT_ERRORS:
            return None
        return 'Ошибка ИИ 😢'
    except Exception as exc:
        print(f'[⚠️ ОШИБКА] Ошибка парсинга: {exc}')
        if last_resp := get_last_response():
            return last_resp
        if SILENT_ERRORS:
            return None
        return 'Ошибка ИИ 😢'


def parse_channel_name(text: str) -> str:
    return text.strip().lstrip('#').lower()


class TwitchIrcBot:
    def __init__(self):
        self.reader = None
        self.writer = None
        self.channels = []
        self.video_task = None
        self.audio_task = None
        self.video_stop = asyncio.Event()
        self.audio_stop = asyncio.Event()
        self.screenshot_enabled = False
        self.screenshot_dir = BASE_DIR / 'screenshots'
        self.screenshot_dir.mkdir(exist_ok=True)

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection('irc.chat.twitch.tv', 6667)
        self.send_raw(f'PASS {TWITCH_TOKEN}')
        self.send_raw(f'NICK {BOT_NICK}')
        self.send_raw('CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership')
        print('✅ Connected to Twitch IRC. Use console command join <channel> to connect to channels.')

    def send_raw(self, message: str):
        if not self.writer:
            return
        self.writer.write((message + '\r\n').encode('utf-8'))

    async def send_message(self, message: str, channel: str | None = None):
        if not self.writer:
            return
        if not channel:
            if not self.channels:
                return
            channel = self.channels[0]
        self.send_raw(f'PRIVMSG #{channel} :{message.replace(chr(10), " ")}')

    async def _capture_video(self, device_index: int):
        """Захватывает весь экран и анализирует его через Ollama."""
        try:
            import mss
            import numpy as np
            import cv2
        except ImportError:
            print('[⚠️] Требуются пакеты: mss, numpy, opencv-python')
            print('Установите: pip install mss numpy opencv-python')
            return

        print(f'🖥️ Захват экрана запущен')
        if self.screenshot_enabled:
            print(f'📸 Скриншоты сохраняются в: {self.screenshot_dir}')

        frame_count = 0
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Первый монитор
                print(f'🖥️ Размер экрана: {monitor["width"]}x{monitor["height"]}')
                
                while not self.video_stop.is_set():
                    # Захватываем экран (mss возвращает RGBA)
                    screenshot = sct.grab(monitor)
                    frame_rgba = np.array(screenshot)
                    # Конвертируем RGBA -> RGB (убираем альфа, сохраняем натуральные цвета)
                    frame_rgb = cv2.cvtColor(frame_rgba, cv2.COLOR_RGBA2RGB)
                    
                    frame_count += 1
                    
                    # Сохраняем скриншот если включено
                    if self.screenshot_enabled and frame_count % 5 == 0:
                        try:
                            timestamp = int(time.time() * 1000) % 1000000
                            filename = self.screenshot_dir / f'frame_{frame_count}_{timestamp}.jpg'
                            # imwrite ожидает BGR, конвертируем из RGB
                            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                            await asyncio.to_thread(cv2.imwrite, str(filename), frame_bgr)
                        except Exception as e:
                            print(f'[⚠️] Ошибка сохранения скриншота: {e}')
                    
                    # Отправляем RGB кадр в Ollama каждые 10 кадров
                    if frame_count % 10 == 0:
                        print(f'[🖥️] Анализ кадра #{frame_count}...')
                        response = await asyncio.to_thread(ask_ollama_vision, frame_rgb, "Кратко опиши что происходит на экране. Только на русском.")
                        if response:
                            print(f'[👁️ Ollama]: {response}')
                        else:
                            print('[🖥️] Ollama не ответил')
                    
                    if frame_count % 30 == 0:
                        print(f'[🖥️] Обработано {frame_count} кадров')
                    
                    await asyncio.sleep(0.1)  # Минимальная задержка для снижения нагрузки
        
        except Exception as e:
            print(f'[⚠️] Ошибка захвата экрана: {e}')
        
        print(f'🖥️ Остановка захвата экрана (всего кадров: {frame_count})')

    async def _capture_audio(self, device_index: int):
        try:
            import sounddevice as sd
            import numpy as np
            import speech_recognition as sr
            import io
            import wave
        except ImportError:
            print('[⚠️] Требуемые пакеты не установлены. Установите: pip install sounddevice numpy SpeechRecognition')
            return

        CHUNK_SIZE = 4096
        SAMPLE_RATE = 16000
        samples_collected = 0
        recognizer = sr.Recognizer()
        audio_frames = []

        def callback(indata, frames, time_info, status):
            nonlocal samples_collected
            if status:
                print(f'[⚠️] Audio status: {status}')
            audio_frames.append(indata.copy())
            samples_collected += len(indata)
            if self.audio_stop.is_set():
                raise sd.CallbackStop()

        async def recognize_from_frames():
            nonlocal audio_frames, samples_collected
            if len(audio_frames) == 0:
                return None
            
            try:
                audio_data = np.concatenate(audio_frames, axis=0)
                normalized = (audio_data * 32767).astype('int16')
                wav_data = io.BytesIO()
                
                with wave.open(wav_data, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(SAMPLE_RATE)
                    wav_file.writeframes(normalized.tobytes())
                
                wav_data.seek(0)
                audio = sr.AudioData(wav_data.read(), SAMPLE_RATE, 2)
                
                text = await asyncio.to_thread(recognizer.recognize_google, audio, language='ru-RU')
                return text
            except sr.UnknownValueError:
                return None
            except sr.RequestError as e:
                print(f'[⚠️] Ошибка распознавания: {e}')
                return None
            except Exception as e:
                print(f'[⚠️] Ошибка обработки аудио: {e}')
                return None

        try:
            with sd.InputStream(device=device_index, channels=1, samplerate=SAMPLE_RATE, callback=callback, blocksize=CHUNK_SIZE) as stream:
                print(f'🎙️ Захват аудио с устройства #{device_index} (sample rate: {SAMPLE_RATE} Hz) запущен')
                chunk_count = 0
                while not self.audio_stop.is_set():
                    await asyncio.sleep(0.2)
                    chunk_count += 1
                    
                    if chunk_count % 25 == 0:
                        if len(audio_frames) > 0:
                            text = await recognize_from_frames()
                            if text:
                                print(f'[📝] Распознано: {text}')
                            else:
                                print(f'[🎙️] Захвачено звука, но не распознано')
                            audio_frames.clear()
                            samples_collected = 0
        except Exception as exc:
            print(f'[⚠️] Ошибка захвата аудио: {exc}')
        print('🎙️ Остановка захвата аудио')

    def _parse_device_index(self, text: str | None, default: int = 0) -> int:
        if not text:
            return default
        try:
            return int(text)
        except ValueError:
            return default

    def list_available_devices(self):
        print('\n📺 === ВИДЕОУСТРОЙСТВА ===')
        try:
            import cv2
            for i in range(10):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    print(f'  Камера #{i}: доступна')
                    cap.release()
                else:
                    cap.release()
        except ImportError:
            print('  [⚠️] OpenCV не установлен')
        except Exception as exc:
            print(f'  [⚠️] Ошибка: {exc}')

        print('\n🎙️ === АУДИОУСТРОЙСТВА ===')
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    print(f'  Микрофон #{i}: {device["name"]} ({device["max_input_channels"]} каналов)')
        except ImportError:
            print('  [⚠️] sounddevice не установлен')
        except Exception as exc:
            print(f'  [⚠️] Ошибка: {exc}')
        print()

    async def console_loop(self):
        print('Console commands: join <channel>, part <channel>, memory [N], msg <channel> <text>, start_video, stop_video, start_audio [device], stop_audio, screenshot_on/off, clear_screenshots, devices, list, channels, quit')
        loop = asyncio.get_running_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, input, '> ')
            except (EOFError, KeyboardInterrupt):
                print('Console input closed')
                break
            if not line:
                continue
            parts = line.strip().split(' ', 2)
            cmd = parts[0].lower()
            if cmd == 'devices':
                self.list_available_devices()
            elif cmd == 'join' and len(parts) >= 2:
                channel = parse_channel_name(parts[1])
                if channel in self.channels:
                    print(f'Already in {channel}')
                    continue
                self.channels.append(channel)
                self.send_raw(f'JOIN #{channel}')
                print(f'Joined #{channel}')
            elif cmd == 'part' and len(parts) >= 2:
                channel = parse_channel_name(parts[1])
                if channel not in self.channels:
                    print(f'Not in {channel}')
                    continue
                self.send_raw(f'PART #{channel}')
                self.channels.remove(channel)
                print(f'Parted #{channel}')
            elif cmd in ('list', 'channels'):
                print('Channels:', ', '.join(self.channels) if self.channels else '(none)')
            elif cmd in ('memory', 'history'):
                count = 10
                if len(parts) >= 2 and parts[1].isdigit():
                    count = int(parts[1])
                show_memory(count)
            elif cmd == 'msg' and len(parts) >= 3:
                target = parse_channel_name(parts[1])
                text = parts[2].strip()
                if target not in self.channels:
                    print(f'Not joined to {target}')
                    continue
                await self.send_message(text, channel=target)
                print(f'Sent to #{target}: {text}')
            elif cmd == 'start_video':
                device_index = self._parse_device_index(parts[1] if len(parts) >= 2 else None)
                if self.video_task and not self.video_task.done():
                    print('Video capture already running')
                    continue
                self.video_stop.clear()
                self.video_task = asyncio.create_task(self._capture_video(device_index))
            elif cmd == 'stop_video':
                if self.video_task and not self.video_task.done():
                    self.video_stop.set()
                    await self.video_task
                else:
                    print('Video capture is not running')
            elif cmd == 'start_audio':
                device_index = self._parse_device_index(parts[1] if len(parts) >= 2 else None)
                if self.audio_task and not self.audio_task.done():
                    print('Audio capture already running')
                    continue
                self.audio_stop.clear()
                self.audio_task = asyncio.create_task(self._capture_audio(device_index))
            elif cmd == 'stop_audio':
                if self.audio_task and not self.audio_task.done():
                    self.audio_stop.set()
                    await self.audio_task
                else:
                    print('Audio capture is not running')
            elif cmd == 'screenshot_on':
                self.screenshot_enabled = True
                print(f'📸 Сохранение скриншотов включено: {self.screenshot_dir}')
            elif cmd == 'screenshot_off':
                self.screenshot_enabled = False
                print('📸 Сохранение скриншотов отключено')
            elif cmd == 'clear_screenshots':
                try:
                    import shutil
                    if self.screenshot_dir.exists():
                        shutil.rmtree(self.screenshot_dir)
                        self.screenshot_dir.mkdir(exist_ok=True)
                        print('📸 Папка скриншотов очищена')
                    else:
                        print('📸 Папка скриншотов не существует')
                except Exception as e:
                    print(f'[⚠️] Ошибка при очистке: {e}')
            elif cmd in ('quit', 'exit'):
                print('Stopping bot...')
                if self.writer:
                    self.writer.close()
                    await self.writer.wait_closed()
                break
            else:
                print('Unknown command. Use: join, part, list, msg, memory, start_video, stop_video, start_audio, stop_audio, screenshot_on, screenshot_off, clear_screenshots, devices, channels, quit')

    async def run(self):
        await self.connect()
        asyncio.create_task(self.console_loop())
        while True:
            line = await self.reader.readline()
            if not line:
                print('Connection closed by server')
                break
            text = line.decode('utf-8', errors='ignore').strip()
            if not text:
                continue
            print('<<', text)
            if text.startswith('PING'):
                self.send_raw('PONG :tmi.twitch.tv')
                continue
            parsed = self.parse_privmsg(text)
            if parsed is None:
                continue
            user, channel, message = parsed
            if user.lower() == BOT_NICK:
                continue
            if not is_bot_mentioned(message):
                continue
            global last_reply
            now = time.time()
            if now - last_reply < COOLDOWN:
                continue
            last_reply = now
            update_conversation_memory(user)
            print(f'{user}@{channel}: {message}')
            reply = ask_ollama(user, message)
            if reply is not None:
                reply = reply[:MAX_LEN]
                await asyncio.sleep(1)
                await self.send_message(reply, channel=channel)

    def parse_privmsg(self, text: str):
        if 'PRIVMSG' not in text:
            return None
        parts = text.split(' PRIVMSG ', 1)
        if len(parts) != 2:
            return None
        prefix, rest = parts
        if prefix.startswith('@'):
            prefix = prefix.split(' ', 1)[1]
        if ' :' not in rest:
            return None
        channel_part, message = rest.split(' :', 1)
        channel = channel_part.strip().lstrip('#').split(' ', 1)[0].lower()
        user = prefix.split('!', 1)[0].lstrip(':')
        return user, channel, message


if __name__ == '__main__':
    print('🤖 Запуск бота Лиза...')
    bot = TwitchIrcBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print('Stopped by user')
=======
import asyncio
import json
import os
import re
import time
from pathlib import Path
import requests

from liza_bot.config import *

# Global variable to track last reply time
last_reply = 0


# ================== Настройки ==================
BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / '.env'


def load_env(path: Path):
    if not path.exists():
        return
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value


load_env(ENV_FILE)

TWITCH_TOKEN = os.getenv('TWITCH_TOKEN', '').strip()
BOT_NICK = os.getenv('BOT_NICK', 'liza').strip().lower()
MODEL = os.getenv('MODEL', 'liza:latest')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434/api/generate')
SILENT_ERRORS = os.getenv('SILENT_ERRORS', 'false').lower() in ('1', 'true', 'yes')
COOLDOWN = float(os.getenv('COOLDOWN', '2'))
MAX_LEN = int(os.getenv('MAX_LEN', '500'))


if not TWITCH_TOKEN:
    raise SystemExit('Missing required env var: TWITCH_TOKEN')
if not TWITCH_TOKEN.startswith('oauth:'):
    raise SystemExit('TWITCH_TOKEN must start with oauth:')


# # ================== Память ==================
MEMORY_FILE = BASE_DIR / 'bot_memory.json'
MAX_HISTORY_SIZE = 50


def load_memory():
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
                }
            if isinstance(data, list):
                return {
                    'history': data,
                    'last_user': None,
                    'interlocutors': [],
                    'switches': [],
                }
        except Exception as exc:
            print(f'[⚠️] Ошибка при загрузке памяти: {exc}')
    return {'history': [], 'last_user': None, 'interlocutors': [], 'switches': []}


def save_memory(mem):
    try:
        mem_to_save = dict(mem)
        mem_to_save['history'] = mem_to_save.get('history', [])[-MAX_HISTORY_SIZE:]
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(mem_to_save, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f'[⚠️] Ошибка при сохранении памяти: {exc}')


def update_conversation_memory(user):
    prev_user = memory.get('last_user')
    if user not in memory.setdefault('interlocutors', []):
        memory['interlocutors'].append(user)
    if prev_user and prev_user != user:
        memory.setdefault('switches', []).append({
            'from': prev_user,
            'to': user,
            'when': int(time.time()),
        })
    memory['last_user'] = user
    save_memory(memory)


def show_memory(count=10):
    if not history:
        print('📝 Память пуста')
        return

    print(f'📝 Последний собеседник: {memory.get("last_user") or "нет"}')
    if memory.get('interlocutors'):
        print(f'📝 Ники в памяти: {", ".join(memory.get("interlocutors", []))}')
    if memory.get('switches'):
        print('📝 Переключения между собеседниками:')
        for sw in memory['switches'][-5:]:
            when = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(sw['when']))
            print(f'  {when}: {sw["from"]} -> {sw["to"]}')

    recent = history[-count * 2:]
    print(f'\n📝 === ПОСЛЕДНИЕ {len(recent) // 2} ЗАПРОСОВ ===')
    for i in range(0, len(recent), 2):
        if i + 1 < len(recent):
            print(f'{recent[i]}\n{recent[i+1]}\n')


def get_last_response():
    if len(history) >= 2:
        return history[-1]
    return None


def is_bot_mentioned(message: str) -> bool:
    lower = message.lower().strip()
    if f'@{BOT_NICK}' in lower or '@лиза' in lower or '@лизанька' in lower:
        return True
    if lower.startswith(BOT_NICK) or lower.startswith('лиза') or lower.startswith('лизанька'):
        return True
    return False


# ================== Логика ==================
memory = load_memory()
history = memory.get('history', [])
print(f'✅ История загружена ({len(history)} сообщений)')
print(f'📝 Последний собеседник: {memory.get("last_user") or "(none)"}')
print(f'🔇 Тихий режим: {SILENT_ERRORS}')
print(f'🔗 Ollama URL: {OLLAMA_URL}')


def ask_ollama(user: str, text: str) -> str | None:
    global history
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
            if last_resp := get_last_response():
                return last_resp
            if SILENT_ERRORS:
                return None
            return 'Ошибка ИИ 😢'
        data = r.json()
        answer = data.get('response')
        if not answer:
            print('[⚠️ ОШИБКА] Ollama вернул пустой ответ')
            if last_resp := get_last_response():
                return last_resp
            if SILENT_ERRORS:
                return None
            return 'Ошибка ИИ 😢'
        history.append(f'{user}: {text}')
        history.append(f'Бот: {answer}')
        memory['history'] = history
        save_memory(memory)
        return answer.strip()
    except requests.RequestException as exc:
        print(f'[⚠️ ОШИБКА] Ollama недоступен: {exc}')
        if last_resp := get_last_response():
            return last_resp
        if SILENT_ERRORS:
            return None
        return 'Ошибка ИИ 😢'
    except Exception as exc:
        print(f'[⚠️ ОШИБКА] Ошибка парсинга: {exc}')
        if last_resp := get_last_response():
            return last_resp
        if SILENT_ERRORS:
            return None
        return 'Ошибка ИИ 😢'


def parse_channel_name(text: str) -> str:
    return text.strip().lstrip('#').lower()


class TwitchIrcBot:
    def __init__(self):
        self.reader = None
        self.writer = None
        self.channels = []
        self.video_task = None
        self.audio_task = None
        self.video_stop = asyncio.Event()
        self.audio_stop = asyncio.Event()

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection('irc.chat.twitch.tv', 6667)
        self.send_raw(f'PASS {TWITCH_TOKEN}')
        self.send_raw(f'NICK {BOT_NICK}')
        self.send_raw('CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership')
        print('✅ Connected to Twitch IRC. Use console command join <channel> to connect to channels.')

    def send_raw(self, message: str):
        if not self.writer:
            return
        self.writer.write((message + '\r\n').encode('utf-8'))

    async def send_message(self, message: str, channel: str | None = None):
        if not self.writer:
            return
        if not channel:
            if not self.channels:
                return
            channel = self.channels[0]
        self.send_raw(f'PRIVMSG #{channel} :{message.replace(chr(10), " ")}')

    # async def _capture_video(self, device_index: int):
    #     try:
    #         import cv2
    #     except ImportError:
    #         print('[⚠️] OpenCV не установлен. Установите opencv-python.')
    #         return
    #     cap = cv2.VideoCapture(device_index)
    #     if not cap.isOpened():
    #         print(f'[⚠️] Не удалось открыть видеоустройство #{device_index}')
    #         return
    #     print(f'🎥 Захват видео с устройства #{device_index} запущен')
    #     while not self.video_stop.is_set():
    #         ok, frame = await asyncio.to_thread(cap.read)
    #         if not ok:
    #             print('[⚠️] Не удалось получить кадр из видеоустройства')
    #             break
    #         print(f'[🎥] Кадр: {frame.shape}')
    #         await asyncio.sleep(0.03)
    #     await asyncio.to_thread(cap.release)
    #     print('🎥 Остановка захвата видео')

    # async def _capture_audio(self, device_index: int):
    #     try:
    #         import sounddevice as sd
    #     except ImportError:
    #         print('[⚠️] sounddevice не установлен. Установите sounddevice.')
    #         return

    #     def callback(indata, frames, time_info, status):
    #         if status:
    #             print(f'[⚠️] Audio status: {status}')
    #         print(f'[🎙️] Аудио: {indata.shape[0]} сэмплов')
    #         if self.audio_stop.is_set():
    #             raise sd.CallbackStop()

    #     try:
    #         with sd.InputStream(device=device_index, channels=1, callback=callback):
    #             print(f'🎙️ Захват аудио с устройства #{device_index} запущен')
    #             while not self.audio_stop.is_set():
    #                 await asyncio.sleep(0.2)
    #     except Exception as exc:
    #         print(f'[⚠️] Ошибка захвата аудио: {exc}')
    #     print('🎙️ Остановка захвата аудио')

    def _parse_device_index(self, text: str | None, default: int = 0) -> int:
        if not text:
            return default
        try:
            return int(text)
        except ValueError:
            return default

    async def console_loop(self):
        # print('Console commands: join <channel>, part <channel>, memory [N], msg <channel> <text>, start_video [device], stop_video, start_audio [device], stop_audio, list, channels, quit')
        print('Console commands: join <channel>, part <channel>, memory [N], msg <channel> <text>, list, channels, quit')
        
        loop = asyncio.get_running_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, input, '> ')
            except (EOFError, KeyboardInterrupt):
                print('Console input closed')
                break
            if not line:
                continue
            parts = line.strip().split(' ', 2)
            cmd = parts[0].lower()
            if cmd == 'join' and len(parts) >= 2:
                channel = parse_channel_name(parts[1])
                if channel in self.channels:
                    print(f'Already in {channel}')
                    continue
                self.channels.append(channel)
                self.send_raw(f'JOIN #{channel}')
                print(f'Joined #{channel}')
            elif cmd == 'part' and len(parts) >= 2:
                channel = parse_channel_name(parts[1])
                if channel not in self.channels:
                    print(f'Not in {channel}')
                    continue
                self.send_raw(f'PART #{channel}')
                self.channels.remove(channel)
                print(f'Parted #{channel}')
            elif cmd in ('list', 'channels'):
                print('Channels:', ', '.join(self.channels) if self.channels else '(none)')
            elif cmd in ('memory', 'history'):
                count = 10
                if len(parts) >= 2 and parts[1].isdigit():
                    count = int(parts[1])
                show_memory(count)
            elif cmd == 'msg' and len(parts) >= 3:
                target = parse_channel_name(parts[1])
                text = parts[2].strip()
                if target not in self.channels:
                    print(f'Not joined to {target}')
                    continue
                await self.send_message(text, channel=target)
                print(f'Sent to #{target}: {text}')

            # elif cmd == 'start_video':
            #     device_index = self._parse_device_index(parts[1] if len(parts) >= 2 else None)
            #     if self.video_task and not self.video_task.done():
            #         print('Video capture already running')
            #         continue
            #     self.video_stop.clear()
            #     self.video_task = asyncio.create_task(self._capture_video(device_index))

            # elif cmd == 'stop_video':
            #     if self.video_task and not self.video_task.done():
            #         self.video_stop.set()
            #         await self.video_task
            #     else:
            #         print('Video capture is not running')

            # elif cmd == 'start_audio':
            #     device_index = self._parse_device_index(parts[1] if len(parts) >= 2 else None)
            #     if self.audio_task and not self.audio_task.done():
            #         print('Audio capture already running')
            #         continue
            #     self.audio_stop.clear()
            #     self.audio_task = asyncio.create_task(self._capture_audio(device_index))

            # elif cmd == 'stop_audio':
            #     if self.audio_task and not self.audio_task.done():
            #         self.audio_stop.set()
            #         await self.audio_task
            #     else:
            #         print('Audio capture is not running')

            elif cmd in ('quit', 'exit'):
                print('Stopping bot...')
                if self.writer:
                    self.writer.close()
                    await self.writer.wait_closed()
                break
            else:
                print('Unknown command. Use: join, part, list, msg, memory, start_video, stop_video, start_audio, stop_audio, channels, quit')

    async def run(self):
        await self.connect()
        asyncio.create_task(self.console_loop())
        while True:
            line = await self.reader.readline()
            if not line:
                print('Connection closed by server')
                break
            text = line.decode('utf-8', errors='ignore').strip()
            if not text:
                continue
            print('<<', text)
            if text.startswith('PING'):
                self.send_raw('PONG :tmi.twitch.tv')
                continue
            parsed = self.parse_privmsg(text)
            if parsed is None:
                continue
            user, channel, message = parsed
            if user.lower() == BOT_NICK:
                continue
            if not is_bot_mentioned(message):
                continue
            global last_reply
            now = time.time()
            if now - last_reply < COOLDOWN:
                continue
            last_reply = now
            update_conversation_memory(user)
            print(f'{user}@{channel}: {message}')
            reply = ask_ollama(user, message)
            if reply is not None:
                reply = reply[:MAX_LEN]
                await asyncio.sleep(1)
                await self.send_message(reply, channel=channel)

    def parse_privmsg(self, text: str):
        if 'PRIVMSG' not in text:
            return None
        parts = text.split(' PRIVMSG ', 1)
        if len(parts) != 2:
            return None
        prefix, rest = parts
        if prefix.startswith('@'):
            prefix = prefix.split(' ', 1)[1]
        if ' :' not in rest:
            return None
        channel_part, message = rest.split(' :', 1)
        channel = channel_part.strip().lstrip('#').split(' ', 1)[0].lower()
        user = prefix.split('!', 1)[0].lstrip(':')
        return user, channel, message


if __name__ == '__main__':
    print('🤖 Запуск бота Лиза...')
    bot = TwitchIrcBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print('Stopped by user')
>>>>>>> dab93a4 (Add Twitch bot controller and multi-user chat handling)
