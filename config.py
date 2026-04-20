import os
from pathlib import Path


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

MEMORY_FILE = BASE_DIR / 'bot_memory.json'
MAX_HISTORY_SIZE = 50

# Loads the Twitch bot token from the environment variable TWITCH_TOKEN. If not set, uses an empty string. Removes any leading/trailing spaces.
TWITCH_TOKEN = os.getenv('TWITCH_TOKEN', '').strip()

# Loads the bot’s nickname from BOT_NICK, defaults to 'liza' if not set. Strips spaces and converts to lowercase.
BOT_NICK = os.getenv('BOT_NICK', 'liza').strip().lower()

# Loads the model name for Ollama from MODEL, defaults to 'liza:latest'.
MODEL = os.getenv('MODEL', 'liza:latest')

# Loads the Ollama API URL from OLLAMA_URL, defaults to the local server endpoint.
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434/api/generate')

# Loads SILENT_ERRORS, converts to lowercase, and checks if it’s a truthy value ('1', 'true', or 'yes').
SILENT_ERRORS = os.getenv('SILENT_ERRORS', 'false').lower() in ('1', 'true', 'yes')

# Loads the cooldown time (in seconds) between bot replies from COOLDOWN, defaults to 2 seconds, and converts to float.
COOLDOWN = float(os.getenv('COOLDOWN', '2'))

# Loads the maximum reply length from MAX_LEN, defaults to 500, and converts to integer.
MAX_LEN = int(os.getenv('MAX_LEN', '500'))