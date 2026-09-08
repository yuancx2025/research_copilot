from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
import pytest
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.tools.base import SourceType


class FakeModel:
    def __init__(self, responses):
        self.responses = iter(responses)
    def bind_tools(self, tools):
        return self
    async def ainvoke(self, messages):
        return next(self.responses)


class Agent(BaseAgent):
    def get_system_prompt(self):
        return 'Research.'
    def parse_citation(self, *args):
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize('batch', [True, False])
async def test_individual_calls_limited_and_every_call_gets_result(batch):
    invoked = []
    async def count(value: int):
        invoked.append(value)
        return str(value)
    tool = StructuredTool.from_function(coroutine=count, name='count', description='Count')
    calls = [dict(name='count', args={'value':i}, id=str(i), type='tool_call') for i in range(13 if batch else 10)]
    responses = ([AIMessage(content='', tool_calls=calls)] if batch else
                 [AIMessage(content='', tool_calls=[call]) for call in calls])
    model = FakeModel(responses + [AIMessage(content='Finished from available evidence.')])
    graph = Agent(SourceType.WEB, model, [tool]).create_agent_subgraph()
    result = await graph.ainvoke({'messages':[HumanMessage(content='Research')], 'tool_calls_used':0},
                                {'configurable':{'thread_id':'budget'}, 'recursion_limit':50})
    assert invoked == list(range(10))
    results = [m for m in result['messages'] if isinstance(m, ToolMessage)]
    assert {m.tool_call_id for m in results} == {c['id'] for c in calls}
    assert sum(m.status == 'error' for m in results) == (3 if batch else 0)
    assert result['tool_calls_used'] == 10

