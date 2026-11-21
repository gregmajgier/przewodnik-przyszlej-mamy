import json

import pytest
from pydantic import BaseModel

from app.ai.llm import (
    DemoLLM,
    FakeLLM,
    FoundryLLM,
    LLMError,
    LLMMessage,
    LLMResult,
    ToolCall,
    ToolSpec,
    Usage,
    get_llm,
    register_demo_handler,
    track_usage,
)


class Answer(BaseModel):
    value: int


def user(text: str) -> list[LLMMessage]:
    return [LLMMessage(role="user", content=text)]


async def test_fake_llm_returns_scripted_in_order():
    llm = FakeLLM().script(LLMResult(text="a"), LLMResult(text="b"))
    assert (await llm.chat(user("1"), feature="t")).text == "a"
    assert (await llm.chat(user("2"), feature="t")).text == "b"


async def test_fake_llm_exhausted_script_raises_llmerror():
    llm = FakeLLM()
    with pytest.raises(LLMError):
        await llm.chat(user("1"), feature="t")


async def test_fake_llm_raises_scripted_exception():
    llm = FakeLLM().script(LLMError("boom"))
    with pytest.raises(LLMError):
        await llm.chat(user("1"), feature="t")


async def test_fake_llm_records_calls():
    llm = FakeLLM().script(LLMResult(text="a"))
    tools = [ToolSpec(name="x", description="d", parameters={"type": "object"})]
    await llm.chat(user("hej"), feature="chat", tools=tools)
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call.feature == "chat"
    assert call.messages[0].content == "hej"
    assert call.tools == tools


async def test_structured_parses_json_into_model():
    llm = FakeLLM().script(LLMResult(text=json.dumps({"value": 7})))
    out = await llm.structured(user("?"), Answer, feature="t")
    assert out == Answer(value=7)


async def test_structured_accepts_model_instance_from_script():
    llm = FakeLLM().script(Answer(value=3))
    assert (await llm.structured(user("?"), Answer, feature="t")).value == 3


async def test_structured_retries_once_on_invalid_json_then_succeeds():
    llm = FakeLLM().script(LLMResult(text="nie json"), LLMResult(text='{"value": 1}'))
    assert (await llm.structured(user("?"), Answer, feature="t")).value == 1
    assert len(llm.calls) == 2


async def test_structured_retries_once_on_invalid_json_then_llmerror():
    llm = FakeLLM().script(
        LLMResult(text="nie json"), LLMResult(text='{"value": "x"}'), LLMResult(text='{"value": 1}')
    )
    with pytest.raises(LLMError):
        await llm.structured(user("?"), Answer, feature="t")
    assert len(llm.calls) == 2  # dokładnie jedna ponowna próba


async def test_demo_llm_uses_registered_handler():
    register_demo_handler("demo-feature-a", lambda msgs: LLMResult(text=f"echo:{msgs[-1].content}"))
    out = await DemoLLM().chat(user("hej"), feature="demo-feature-a")
    assert out.text == "echo:hej"


async def test_demo_llm_handler_may_return_model_for_structured():
    register_demo_handler("demo-feature-b", lambda msgs: Answer(value=42))
    assert (await DemoLLM().structured(user("?"), Answer, feature="demo-feature-b")).value == 42


async def test_demo_llm_unknown_feature_returns_polite_fallback():
    out = await DemoLLM().chat(user("?"), feature="no-such-feature")
    assert out.text and "demo" in out.text.lower()
    assert out.tool_calls == []


async def test_demo_llm_structured_unknown_feature_raises_llmerror():
    with pytest.raises(LLMError):
        await DemoLLM().structured(user("?"), Answer, feature="no-such-feature")


def test_get_llm_returns_demo_without_config():
    assert isinstance(get_llm(), DemoLLM)


def test_get_llm_returns_foundry_when_configured(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://example.openai.azure.com")
    monkeypatch.setattr(settings, "azure_openai_api_key", "k")
    assert isinstance(get_llm(), FoundryLLM)


class _Msg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Completion:
    def __init__(self, message, prompt=5, completion=7):
        self.choices = [type("C", (), {"message": message})()]
        self.usage = type("U", (), {"prompt_tokens": prompt, "completion_tokens": completion})()


class _FakeOpenAI:
    """Atrapa AsyncAzureOpenAI: zapamiętuje argumenty, zwraca skryptowane odpowiedzi."""

    def __init__(self, *completions):
        self._completions = list(completions)
        self.kwargs: list[dict] = []
        self.chat = type("Chat", (), {"completions": self})()

    async def create(self, **kwargs):
        self.kwargs.append(kwargs)
        return self._completions.pop(0)


async def test_foundry_chat_maps_messages_tools_and_usage():
    call = type(
        "TC",
        (),
        {"id": "c1", "function": type("F", (), {"name": "profil", "arguments": '{"a": 1}'})()},
    )()
    client = _FakeOpenAI(_Completion(_Msg(None, [call])))
    llm = FoundryLLM(client=client, deployment="dep")
    tools = [ToolSpec(name="profil", description="d", parameters={"type": "object", "properties": {}})]
    res = await llm.chat(
        [
            LLMMessage(role="system", content="s"),
            LLMMessage(role="assistant", tool_calls=[ToolCall(id="c0", name="x", arguments={})]),
            LLMMessage(role="tool", content="{}", tool_call_id="c0"),
        ],
        feature="chat",
        tools=tools,
    )
    assert res.tool_calls == [ToolCall(id="c1", name="profil", arguments={"a": 1})]
    assert res.usage == Usage(prompt_tokens=5, completion_tokens=7)
    sent = client.kwargs[0]
    assert sent["model"] == "dep"
    assert sent["tools"][0]["function"]["name"] == "profil"
    assert sent["messages"][1]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert sent["messages"][2]["tool_call_id"] == "c0"


async def test_foundry_structured_uses_json_schema_and_parses():
    client = _FakeOpenAI(_Completion(_Msg('{"value": 9}')))
    out = await FoundryLLM(client=client, deployment="dep").structured(user("?"), Answer, feature="t")
    assert out.value == 9
    assert client.kwargs[0]["response_format"]["type"] == "json_schema"


async def test_foundry_bad_tool_arguments_json_becomes_llmerror():
    call = type("TC", (), {"id": "c1", "function": type("F", (), {"name": "x", "arguments": "{nie json"})()})()
    client = _FakeOpenAI(_Completion(_Msg(None, [call])))
    with pytest.raises(LLMError):
        await FoundryLLM(client=client, deployment="d").chat(user("x"), feature="t")


async def test_foundry_wraps_sdk_errors_in_llmerror_without_leaking_content():
    class Boom(_FakeOpenAI):
        async def create(self, **kwargs):
            raise RuntimeError("sekretna treść promptu")

    with pytest.raises(LLMError) as e:
        await FoundryLLM(client=Boom(), deployment="d").chat(user("x"), feature="t")
    assert "sekretna" not in str(e.value)


async def test_usage_tracker_collects_usage_from_chat_and_structured():
    llm = FakeLLM().script(
        LLMResult(text="a", usage=Usage(prompt_tokens=10, completion_tokens=5)),
        LLMResult(text='{"value": 1}', usage=Usage(prompt_tokens=3, completion_tokens=2)),
    )
    with track_usage() as total:
        await llm.chat(user("1"), feature="t")
        await llm.structured(user("2"), Answer, feature="t")
    assert total.prompt_tokens == 13 and total.completion_tokens == 7


async def test_foundry_sends_reasoning_effort_for_reasoning_models(monkeypatch):
    """gpt-5.x (np. gpt-5.4-nano) — wysiłek rozumowania z konfiguracji; puste = parametr pominięty (gpt-4.1-nano)."""
    from app.config import settings

    monkeypatch.setattr(settings, "azure_openai_reasoning_effort", "low")
    client = _FakeOpenAI(_Completion(_Msg("ok", None)))
    await FoundryLLM(client=client, deployment="gpt-5.4-nano").chat([LLMMessage(role="user", content="?")], feature="chat")
    assert client.kwargs[0]["reasoning_effort"] == "low"

    monkeypatch.setattr(settings, "azure_openai_reasoning_effort", "")
    client = _FakeOpenAI(_Completion(_Msg("ok", None)))
    await FoundryLLM(client=client, deployment="gpt-4.1-nano").chat([LLMMessage(role="user", content="?")], feature="chat")
    assert "reasoning_effort" not in client.kwargs[0]
