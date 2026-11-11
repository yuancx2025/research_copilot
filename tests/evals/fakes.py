"""A minimal real chat model, so LangChain callbacks and caching behave as in production."""
from typing import Any, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda


class FakeChat(BaseChatModel):
    """Answers with ``reply`` and reports fixed token usage."""

    reply: str = "ok"
    input_tokens: int = 10
    output_tokens: int = 3
    fail: bool = False
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake-chat"

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager=None, **kwargs: Any) -> ChatResult:
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider unavailable")
        message = AIMessage(content=self.reply, usage_metadata={
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens})
        return ChatResult(generations=[ChatGeneration(message=message)])

    def with_structured_output(self, schema, **kwargs):
        return self | RunnableLambda(lambda message: schema.model_validate_json(message.content))

