from app.llm import factory

def test_chat_model_built_from_setting(monkeypatch):
    captured = {}
    monkeypatch.setattr(factory, "init_chat_model",
                        lambda m, **k: captured.setdefault("model", m) or "MODEL")
    factory.get_chat_model()
    assert captured["model"] == factory.settings.model
