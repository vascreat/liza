from pathlib import Path

from liza_bot.memory import bot_memory


def test_append_exchange_updates_global_and_scoped_history(tmp_path, monkeypatch):
    test_memory_file = tmp_path / 'memory.json'
    monkeypatch.setattr(bot_memory, 'MEMORY_FILE', test_memory_file)

    manager = bot_memory.memory_manager()
    manager.append_exchange('chan:user', 'alice', 'hello', 'hi')

    assert manager.history[-2:] == ['alice: hello', 'Bot: hi']
    assert manager.get_history('chan:user')[-2:] == ['alice: hello', 'Bot: hi']


def test_save_memory_truncates_histories(tmp_path, monkeypatch):
    test_memory_file = tmp_path / 'memory.json'
    monkeypatch.setattr(bot_memory, 'MEMORY_FILE', test_memory_file)
    monkeypatch.setattr(bot_memory, 'MAX_HISTORY_SIZE', 4)

    manager = bot_memory.memory_manager()
    memory = {
        'history': ['u1', 'b1', 'u2', 'b2', 'u3', 'b3'],
        'last_user': 'alice',
        'interlocutors': ['alice'],
        'switches': [],
        'conversation_histories': {
            'chan:user': ['u1', 'b1', 'u2', 'b2', 'u3', 'b3'],
        },
    }

    manager.save_memory(memory)

    assert manager.history == ['u2', 'b2', 'u3', 'b3']
    assert manager.conversation_histories['chan:user'] == ['u2', 'b2', 'u3', 'b3']
