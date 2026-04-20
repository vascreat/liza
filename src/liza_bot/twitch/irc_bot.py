import asyncio
import time

from liza_bot.config import *
from liza_bot.memory.bot_memory import memory_manager

class TwitchIrcBot:
    def __init__(self, bot_memory=None, ollama=None):
        self.reader = None
        self.writer = None
        self.channels = []
        self.video_task = None
        self.audio_task = None
        self.video_stop = asyncio.Event()
        self.audio_stop = asyncio.Event()
        self.last_reply_by_conversation = {}

        self.bot_memory = bot_memory or memory_manager()
        self.ollama = ollama

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
        try:
            import cv2
        except ImportError:
            print('[⚠️] OpenCV не установлен. Установите opencv-python.')
            return
        cap = cv2.VideoCapture(device_index)
        if not cap.isOpened():
            print(f'[⚠️] Не удалось открыть видеоустройство #{device_index}')
            return
        print(f'🎥 Захват видео с устройства #{device_index} запущен')
        while not self.video_stop.is_set():
            ok, frame = await asyncio.to_thread(cap.read)
            if not ok:
                print('[⚠️] Не удалось получить кадр из видеоустройства')
                break
            print(f'[🎥] Кадр: {frame.shape}')
            await asyncio.sleep(0.03)
        await asyncio.to_thread(cap.release)
        print('🎥 Остановка захвата видео')

    async def _capture_audio(self, device_index: int):
        try:
            import sounddevice as sd
        except ImportError:
            print('[⚠️] sounddevice не установлен. Установите sounddevice.')
            return

        def callback(indata, frames, time_info, status):
            if status:
                print(f'[⚠️] Audio status: {status}')
            print(f'[🎙️] Аудио: {indata.shape[0]} сэмплов')
            if self.audio_stop.is_set():
                raise sd.CallbackStop()

        try:
            with sd.InputStream(device=device_index, channels=1, callback=callback):
                print(f'🎙️ Захват аудио с устройства #{device_index} запущен')
                while not self.audio_stop.is_set():
                    await asyncio.sleep(0.2)
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

    def _conversation_key(self, channel: str, user: str) -> str:
        return f'{channel.lower()}:{user.lower()}'

    def _parse_irc_command(self, text: str):
        payload = text
        if payload.startswith('@'):
            payload = payload.split(' ', 1)[1]
        parts = payload.split()
        if not parts:
            return None, None, []
        if parts[0].startswith(':') and len(parts) >= 2:
            return parts[0].lstrip(':'), parts[1], parts[2:]
        return None, parts[0], parts[1:]

    def _format_irc_line(self, text: str) -> str | None:
        if text.startswith('PING'):
            return None

        user, channel, message = self.parse_privmsg(text)
        if user and channel and message is not None:
            return f'[{channel}] {user}: {message}'

        prefix, command, params = self._parse_irc_command(text)
        if command in {'001', '002', '003', '004', '353', '366', '372', '375', '376', 'CAP', 'USERSTATE', 'ROOMSTATE'}:
            return None

        if command in {'JOIN', 'PART'} and prefix and params:
            user = prefix.split('!', 1)[0]
            channel = params[-1].lstrip(':#').lower()
            action = 'joined' if command == 'JOIN' else 'left'
            return f'[{channel}] {user} {action}'

        if command == 'NOTICE' and params:
            channel = params[0].lstrip('#').lower() if params else 'system'
            notice = text.split(' :', 1)[1] if ' :' in text else ' '.join(params[1:])
            return f'[{channel}] notice: {notice}'

        return None

    async def console_loop(self):
        print('Console commands: join <channel>, part <channel>, memory [N], msg <channel> <text>, start_video [device], stop_video, start_audio [device], stop_audio, list, channels, quit')
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
                channel = self.ollama.parse_channel_name(parts[1])
                if channel in self.channels:
                    print(f'Already in {channel}')
                    continue
                self.channels.append(channel)
                self.send_raw(f'JOIN #{channel}')
                print(f'Joined #{channel}')
            elif cmd == 'part' and len(parts) >= 2:
                channel = self.ollama.parse_channel_name(parts[1])
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
                self.bot_memory.show_memory(count)
            elif cmd == 'msg' and len(parts) >= 3:
                target = self.ollama.parse_channel_name(parts[1])
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
            formatted_line = self._format_irc_line(text)
            if formatted_line:
                print(formatted_line)
            if text.startswith('PING'):
                self.send_raw('PONG :tmi.twitch.tv')
                continue
            parsed = self.parse_privmsg(text)
            if parsed[0] is None:
                continue
            user, channel, message = parsed
            if user.lower() == BOT_NICK:
                continue
            if self.ollama is None:
                continue
            if not self.bot_memory.is_bot_mentioned(message):
                continue
            conversation_key = self._conversation_key(channel, user)
            now = time.time()
            last_reply = self.last_reply_by_conversation.get(conversation_key, 0.0)
            if now - last_reply < COOLDOWN:
                continue
            self.last_reply_by_conversation[conversation_key] = now
            self.bot_memory.update_conversation_memory(user)
            print(f'{user}@{channel}: {message}')
            reply = await asyncio.to_thread(self.ollama.ask_ollama, user, message, conversation_key)
            if reply is not None:
                reply = reply[:MAX_LEN]
                await asyncio.sleep(1)
                await self.send_message(reply, channel=channel)

    def parse_privmsg(self, text: str):
        if 'PRIVMSG' not in text:
            return None, None, None
        parts = text.split(' PRIVMSG ', 1)
        if len(parts) != 2:
            return None, None, None
        prefix, rest = parts
        if prefix.startswith('@'):
            prefix = prefix.split(' ', 1)[1]
        if ' :' not in rest:
            return None, None, None
        channel_part, message = rest.split(' :', 1)
        channel = channel_part.strip().lstrip('#').split(' ', 1)[0].lower()
        user = prefix.split('!', 1)[0].lstrip(':')
        return user, channel, message

