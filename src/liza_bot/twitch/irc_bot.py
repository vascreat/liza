import asyncio
import time

from colorama import Fore, Style

from liza_bot.config import *
from liza_bot.memory.bot_memory import memory_manager
from liza_bot.audio.twitch_speech_to_text import TwitchSpeechRecognizer

class TwitchIrcBot:
    """    
    """
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
        self.twitch_speech_recognizer = None
        self.audio_recognizer_task = None
        
    async def console_loop(self):
        # print('Console commands: join <channel>, leave <channel>, memory [N], msg <channel> <text>, start_video [device], stop_video, start_audio <channe>, stop_audio, list, channels, quit')
        print('Console commands: join <channel>, leave <channel>, start_audio <channe>, stop_audio, list channels, quit')
        
        
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

            match cmd:
                # Joins the specified Twitch channel
                case 'join' if len(parts) >= 2:
                    channel = self.parse_channel_name(parts[1])
                    if channel in self.channels:
                        print(f'Already in {channel}')
                        continue
                    self.channels.append(channel)
                    self.send_raw(f'JOIN #{channel}')
                    print(f'Joined #{channel}')

                # Parts the specified Twitch channel
                case 'leave' if len(parts) >= 2:
                    channel = self.parse_channel_name(parts[1])
                    if channel not in self.channels:
                        print(f'Not in {channel}')
                        continue
                    self.send_raw(f'LEAVE #{channel}')
                    self.channels.remove(channel)
                    print(f'Left #{channel}')

                case 'list' | 'channels':
                    print('Channels:', ', '.join(self.channels) if self.channels else '(none)')

                # case 'memory' | 'history':
                #     count = 10
                #     if len(parts) >= 2 and parts[1].isdigit():
                #         count = int(parts[1])
                #     self.bot_memory.show_memory(count)

                # TODO msg command later to be reviewed ====================================
                # case 'msg' if len(parts) >= 3:
                #     target = self.parse_channel_name(parts[1])
                #     text = parts[2].strip()
                #     if target not in self.channels:
                #         print(f'Not joined to {target}')
                #         continue
                #     await self.send_message(text, channel=target)
                #     print(f'Sent to #{target}: {text}')


                # Starts the audio recognizer task if not already running
                case 'start_audio' if len(parts) >= 2:
                    channel = self.parse_channel_name(parts[1])
                    if self.audio_recognizer_task and not self.audio_recognizer_task.done():
                        print(f'Audio capture already running on {channel}')
                        continue

                    if not self.twitch_speech_recognizer:
                        self.twitch_speech_recognizer = TwitchSpeechRecognizer(channel)

                    elif not self.twitch_speech_recognizer.channel:
                        self.twitch_speech_recognizer.channel = channel

                    async def listen_for_trigger():
                        await self.twitch_speech_recognizer.start()
                        print(f'Audio capture started on #{channel}')
                        while True:
                            text = await self.twitch_speech_recognizer.get_text()
                            if text:
                                print(f'[{channel}] {text}')

                    self.audio_recognizer_task = asyncio.create_task(listen_for_trigger())

                # Stops the audio recognizer task if running
                case 'stop_audio':
                    if self.audio_recognizer_task and not self.audio_recognizer_task.done():
                        if self.twitch_speech_recognizer:
                            self.twitch_speech_recognizer.stop()
                        self.audio_recognizer_task.cancel()
                        try:
                            await self.audio_recognizer_task
                        except asyncio.CancelledError:
                            pass
                        print('Audio capture stopped')
                    else:
                        print('Audio capture is not running')

                case 'quit' | 'exit':
                    print('Stopping bot...')
                    if self.writer:
                        self.writer.close()
                        await self.writer.wait_closed()
                    break

                case _:
                    print('Unknown command. Use: join, part, list, msg, memory, start_video, stop_video, start_audio, stop_audio, channels, quit')
    
    
    def parse_channel_name(self, text: str) -> str:
        return text.strip().lstrip('#').lower()

    async def connect(self):
        """
        Connects to Twitch IRC and performs the initial handshake. After connecting, it starts the console loop in a background task.
        """
        self.reader, self.writer = await asyncio.open_connection('irc.chat.twitch.tv', 6667)
        # Sends the authentication and capability request messages to Twitch IRC
        self.send_raw(f'PASS {TWITCH_TOKEN}')
        self.send_raw(f'NICK {BOT_NICK}')
        self.send_raw('CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership')
        print('✅ Connected to Twitch IRC. Use console command join <channel> to connect to channels.')

    async def send_message(self, message: str, channel: str | None = None):
        if not self.writer:
            return
        if not channel:
            if not self.channels:
                return
            channel = self.channels[0]
        self.send_raw(f'PRIVMSG #{channel} :{message.replace(chr(10), " ")}')

        
    def send_raw(self, message: str):
        if not self.writer:
            return
        self.writer.write((message + '\r\n').encode('utf-8'))

    async def run(self):
        # Waits for the connection to Twitch IRC to be established, then starts the console loop and processes incoming messages in a loop. It handles PING messages, parses PRIVMSG for user messages, checks if the bot is mentioned, and uses the ollama instance to generate replies.
        await self.connect()

        # Starts the console loop in a background task to allow simultaneous processing of incoming messages and console commands
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



    def parse_privmsg(self, text: str):
        """
        Parses a PRIVMSG IRC message and returns the user, channel, and message content.

        Args:
            text (str): The raw IRC message.

        Returns:
            tuple: A tuple containing the user, channel, and message content, or (None, None, None) if parsing fails.
        """
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

