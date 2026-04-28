import asyncio
from liza_bot.llm.ollama_connect import ollama_connect
from liza_bot.memory.bot_memory import memory_manager
from liza_bot.twitch.irc_bot import TwitchIrcBot
from liza_bot.audio.twitch_speech_to_text import TwitchSpeechRecognizer

class BotController:
    def __init__(self):
        # Instances an instance of the memory_manager class
        self.memory_manager = memory_manager()

        # Instances an instance of the ollama_connect class
        self.ollama = ollama_connect(bot_memory=self.memory_manager)

        # Instances an instance of the TwitchIrcBot class
        self.twitch_bot = TwitchIrcBot(bot_memory=self.memory_manager, ollama=self.ollama)

        
        self.twitch_bot.ollama = self.ollama
        self.ollama.twitchBot = self.twitch_bot

    async def run(self):
        await self.twitch_bot.run()

def run():
    controller = BotController()
    try:
        asyncio.run(controller.run())
    except KeyboardInterrupt:
        print('Stopped by user')
