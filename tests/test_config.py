import os
from pathlib import Path

from liza_bot import config


def test_load_env_populates_missing_keys(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text(
        'A=1\n'
        'B = "hello"\n'
        '# comment\n'
        'INVALID_LINE\n',
        encoding='utf-8',
    )

    monkeypatch.delenv('A', raising=False)
    monkeypatch.delenv('B', raising=False)

    config.load_env(env_file)

    assert os.environ['A'] == '1'
    assert os.environ['B'] == 'hello'


def test_load_env_does_not_override_existing_value(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text('BOT_NICK=liza\n', encoding='utf-8')

    monkeypatch.setenv('BOT_NICK', 'already_set')
    config.load_env(env_file)

    assert os.environ['BOT_NICK'] == 'already_set'
