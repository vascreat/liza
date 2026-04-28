import asyncio
import importlib
import sys
import types


fake_audio_module = types.ModuleType('liza_bot.audio.twitch_speech_to_text')


class FakeSpeechRecognizer:
    def __init__(self, channel=None):
        self.channel = channel


fake_audio_module.TwitchSpeechRecognizer = FakeSpeechRecognizer
sys.modules['liza_bot.audio.twitch_speech_to_text'] = fake_audio_module

TwitchIrcBot = importlib.import_module('liza_bot.twitch.irc_bot').TwitchIrcBot


def test_parse_channel_name_normalizes_input():
    bot = TwitchIrcBot()
    assert bot.parse_channel_name('  #TeStChannel ') == 'testchannel'


def test_parse_privmsg_extracts_user_channel_and_message():
    bot = TwitchIrcBot()
    text = ':alice!alice@alice.tmi.twitch.tv PRIVMSG #mychan :hello world'

    user, channel, message = bot.parse_privmsg(text)

    assert user == 'alice'
    assert channel == 'mychan'
    assert message == 'hello world'


def test_format_irc_line_for_chat_message():
    bot = TwitchIrcBot()
    text = ':alice!alice@alice.tmi.twitch.tv PRIVMSG #mychan :hello world'

    assert bot._format_irc_line(text) == '[mychan] alice: hello world'


def test_send_message_uses_first_joined_channel_when_not_provided():
    sent = []

    class DummyWriter:
        def write(self, payload):
            sent.append(payload.decode('utf-8'))

    bot = TwitchIrcBot()
    bot.writer = DummyWriter()
    bot.channels = ['mychan']

    asyncio.run(bot.send_message('line1\nline2'))

    assert sent[-1] == 'PRIVMSG #mychan :line1 line2\r\n'
