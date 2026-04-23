


import subprocess
import sys
import asyncio
import speech_recognition as sr
import streamlink
from colorama import Fore, Back, Style


class TwitchSpeechRecognizer:
    """
    A class to capture and transcribe Twitch stream audio in real-time using streamlink, ffmpeg and Google's speech recognition API.
    
    """
    def __init__(self, channel):
        self.channel = channel
        self.recognizer = sr.Recognizer()
        self.sample_rate = 16000
        self.sample_width = 2  # 16-bit PCM
        self.chunk_duration = 5  # seconds
        self.chunk_size = self.sample_rate * self.sample_width * self.chunk_duration
        self.ffmpeg_cmd = None
        self.ffmpeg_proc = None
        self._stop_event = asyncio.Event()
        self._task = None
        self.text_queue: asyncio.Queue[str] = asyncio.Queue()

    async def start(self):
        """
        Async function to start the recognizer as an async background task.
        """
        self._stop_event.clear()
        stream_url = self.get_stream_url()
        if not stream_url:
            print("[Speech] No stream URL found.")
            return
        self.start_ffmpeg(stream_url)
        self._task = asyncio.create_task(self._run_pipeline())

    async def _run_pipeline(self):

        """
        Async function to read audio data from ffmpeg in chunks, process it with the speech recognizer, and print the transcribed text.
        """
        print(Fore.RED + "Listening for speech..." + Style.RESET_ALL)
        try:
            while not self._stop_event.is_set():
                # Read chunk in a thread to avoid blocking event loop
                pcm_data = await asyncio.to_thread(self.ffmpeg_proc.stdout.read, self.chunk_size)
                if not pcm_data or len(pcm_data) < self.chunk_size:
                    break
                await asyncio.to_thread(self.process_chunk, pcm_data)
        finally:
            self.ffmpeg_proc.terminate()
            print("[Speech] Stopped.")
            
    def get_stream_url(self):
        """
        gets the audio-only stream URL for the specified Twitch channel using streamlink.
        """
        streams = streamlink.streams(f"https://www.twitch.tv/{self.channel}")
        if "audio_only" not in streams:
            print("No audio_only stream available.")
            return None
        return streams["audio_only"].url

    def start_ffmpeg(self, stream_url):

        """
        Starts the ffmpeg process to capture audio from the given stream URL chunk and convert it to WAV format at 16 kHz.
        """
        self.ffmpeg_cmd = [
            "ffmpeg",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", stream_url,
            "-f", "wav",
            "-acodec", "pcm_s16le",
            "-ac", "1",
            "-ar", "16000",
            "-"
        ]
        self.ffmpeg_proc = subprocess.Popen(
            self.ffmpeg_cmd,
            # stdout: pipe the output so we can read it in Python
            stdout=subprocess.PIPE,

            # stderr: suppress ffmpeg logs
            stderr=subprocess.DEVNULL
        )


    def stop(self):
        """
        Stop the ffmpeg process and signal the recognizer to stop
        """
        if self._task and not self._task.done():
            self._stop_event.set()

    async def get_text(self) -> str:
        """
        Wait for and return the next recognized text from the queue.
        """
        return await self.text_queue.get()


    def process_chunk(self, pcm_data):
        """
        Process a chunk of PCM audio data and print the recognized text.
        """
        audio = sr.AudioData(pcm_data, self.sample_rate, self.sample_width)
        try:
            text = self.recognizer.recognize_google(audio, language="ru-RU")
            print(Fore.RED+f"[Speech] {text}"+Style.RESET_ALL)
            asyncio.get_event_loop().call_soon_threadsafe(self.text_queue.put_nowait, text)
        except sr.UnknownValueError:
            print("[Speech] (Unrecognized)")
        except KeyboardInterrupt:
            print("Exiting...")
            raise
        except Exception as e:
            print(f"[Error] {e}")


#   Example usage in an async bot:
# recognizer = TwitchSpeechRecognizer("channel_name")
# await recognizer.start()
# ...
# recognizer.stop()  # To stop listening


# def main():
#     channel = "xittaa"  # Replace with the desired Twitch channel
#     print(Fore.RED + f"Connecting to Twitch channel: {channel}" + Style.RESET_ALL)
#     recognizer = TwitchSpeechRecognizer(channel)
#     stream_url = recognizer.get_stream_url()
#     if not stream_url:
#         return
#     print(Fore.RED + f"Stream URL: {stream_url}" + Style.RESET_ALL)
#     recognizer.start_ffmpeg(stream_url)
#     recognizer.pipeline_chunks()

# if __name__ == "__main__":
#     main()
