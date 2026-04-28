from liza_bot.llm import ollama_connect as oc


class FakeMemory:
    def __init__(self):
        self._history = {'chan:user': ['u1', 'b1']}
        self._last = 'last known answer'
        self.append_calls = []
        self.memory = {}

    def get_history(self, conversation_key=None):
        return self._history.get(conversation_key, [])

    def get_last_response(self, conversation_key=None):
        return self._last

    def append_exchange(self, conversation_key, user, text, answer):
        self.append_calls.append((conversation_key, user, text, answer))


def test_ask_ollama_returns_answer_and_appends_exchange(monkeypatch):
    fake_memory = FakeMemory()

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {'response': '  test answer  '}

    def fake_post(*args, **kwargs):
        return Response()

    monkeypatch.setattr(oc.requests, 'post', fake_post)
    client = oc.ollama_connect(bot_memory=fake_memory)

    answer = client.ask_ollama('alice', 'hello', 'chan:user')

    assert answer == 'test answer'
    assert fake_memory.append_calls == [('chan:user', 'alice', 'hello', '  test answer  ')]


def test_ask_ollama_uses_last_response_on_non_200(monkeypatch):
    fake_memory = FakeMemory()

    class Response:
        status_code = 500

        @staticmethod
        def json():
            return {}

    def fake_post(*args, **kwargs):
        return Response()

    monkeypatch.setattr(oc.requests, 'post', fake_post)
    client = oc.ollama_connect(bot_memory=fake_memory)

    answer = client.ask_ollama('alice', 'hello', 'chan:user')

    assert answer == 'last known answer'
