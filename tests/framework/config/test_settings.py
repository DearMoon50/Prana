from framework.config.settings import FrameworkSettings


def test_defaults(monkeypatch):
    # prana.config.load_dotenv() pulls the developer's local .env into
    # os.environ process-wide, so clear the vars this test asserts defaults
    # for (and ignore the .env file itself) to test true code defaults.
    for var in ("LLM_PROVIDERS_RAW", "AGENT_MAX_STEPS"):
        monkeypatch.delenv(var, raising=False)
    s = FrameworkSettings(_env_file=None)
    assert s.llm_providers == ["openrouter", "ollama"]
    assert s.agent_max_steps == 5


def test_llm_providers_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_RAW", "gemini,ollama")
    s = FrameworkSettings(_env_file=None)
    assert s.llm_providers == ["gemini", "ollama"]
