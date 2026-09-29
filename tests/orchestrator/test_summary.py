"""The running summary is the only context that survives message pruning."""
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from research_copilot.orchestrator.nodes import analyze_chat_and_summarize


class RecordingModel:
    def __init__(self, text='Transformers, then their use in translation.'):
        self.prompts = []
        self.text = text

    def with_config(self, **_kwargs):
        return self

    def invoke(self, messages):
        self.prompts.append(messages[0].content)
        return SimpleNamespace(content=self.text)


def test_summary_folds_prior_context_with_the_latest_exchange():
    model = RecordingModel()
    state = {
        'messages': [
            AIMessage(content='Attention replaces recurrence.'),
            HumanMessage(content='How is that used in translation?'),
        ],
        'conversation_summary': 'The user asked about transformers.',
        'originalQuery': 'What are transformers?',
    }
    update = analyze_chat_and_summarize(state, model)
    assert update['conversation_summary'] == 'Transformers, then their use in translation.'
    prompt = model.prompts[0]
    assert 'The user asked about transformers.' in prompt
    assert 'What are transformers?' in prompt
    assert 'Attention replaces recurrence.' in prompt
    assert 'How is that used in translation?' not in prompt


def test_summary_keeps_the_previous_text_when_the_model_fails():
    class Broken(RecordingModel):
        def invoke(self, messages):
            raise RuntimeError('model down')

    state = {
        'messages': [HumanMessage(content='earlier'), AIMessage(content='answer'), HumanMessage(content='next')],
        'conversation_summary': 'Keep me.',
        'originalQuery': 'earlier',
    }
    update = analyze_chat_and_summarize(state, Broken())
    assert update['conversation_summary'] == 'Keep me.'
