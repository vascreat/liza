#!/usr/bin/env bash
set -euo pipefail

FORCE_RECREATE_VENV=0
for arg in "$@"; do
    case "$arg" in
        --force-recreate-venv) FORCE_RECREATE_VENV=1 ;;
    esac
done

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPTS_DIR")"
VENV_PATH="$PROJECT_ROOT/.venv"
REQUIREMENTS_PATH="$PROJECT_ROOT/requirements.txt"
ENV_EXAMPLE_PATH="$PROJECT_ROOT/config/env.example"
ENV_PATH="$PROJECT_ROOT/.env"
PYPROJECT_PATH="$PROJECT_ROOT/pyproject.toml"

step() {
    echo "[setup] $1"
}

get_python_command() {
    for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" &>/dev/null; then
            echo "$candidate"
            return 0
        fi
    done
    echo "Python 3 was not found. Install Python 3.10+ and try again." >&2
    exit 1
}

if [[ "$FORCE_RECREATE_VENV" -eq 1 && -d "$VENV_PATH" ]]; then
    step "Removing existing virtual environment"
    rm -rf "$VENV_PATH"
fi

if [[ ! -d "$VENV_PATH" ]]; then
    PYTHON_CMD="$(get_python_command)"
    step "Creating virtual environment with $PYTHON_CMD"
    "$PYTHON_CMD" -m venv "$VENV_PATH"
else
    step "Using existing virtual environment"
fi

PYTHON_EXE="$VENV_PATH/bin/python"
if [[ ! -x "$PYTHON_EXE" ]]; then
    echo "Virtual environment Python executable was not found." >&2
    exit 1
fi

step "Upgrading pip"
"$PYTHON_EXE" -m pip install --upgrade pip

step "Installing Python dependencies"
"$PYTHON_EXE" -m pip install -r "$REQUIREMENTS_PATH"

if [[ -f "$PYPROJECT_PATH" ]]; then
    step "Installing project in editable mode"
    "$PYTHON_EXE" -m pip install -e "$PROJECT_ROOT"
fi

if [[ ! -f "$ENV_PATH" ]]; then
    if [[ -f "$ENV_EXAMPLE_PATH" ]]; then
        step "Creating .env from env.example"
        cp "$ENV_EXAMPLE_PATH" "$ENV_PATH"
    else
        step "Skipping .env creation because env.example was not found"
    fi
else
    step ".env already exists; leaving it unchanged"
fi

step "Setup complete"
echo ""
echo "Next steps:"
echo "1. Edit $ENV_PATH and fill in your Twitch credentials if needed."
echo "2. Make sure Ollama is installed and your model already exists."
echo "3. Run the bot with: $PYTHON_EXE -m liza_bot.main"
