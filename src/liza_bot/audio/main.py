import asyncio
from liza_bot.audio.twitch_speech_to_text import TwitchSpeechRecognizer


async def main():
    channel = input("Enter Twitch channel name: ").strip()
    recognizer = TwitchSpeechRecognizer(channel)

    await recognizer.start()

    try:
        while True:
            text = await recognizer.get_text()
            print(f"[Recognized] {text}")
    except KeyboardInterrupt:
        pass
    finally:
        recognizer.stop()


if __name__ == "__main__":
    asyncio.run(main())