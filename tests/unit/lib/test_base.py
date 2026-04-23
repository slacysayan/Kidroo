import pytest
from pydantic import ValidationError
from agents.lib.base import BaseAgent, AgentInput, AgentOutput

class MockAgent(BaseAgent):
    name: str = "mock_agent"

    async def run(self, input: AgentInput) -> AgentOutput:
        return AgentOutput(success=True, data={"received": input.job_id})

@pytest.mark.asyncio
async def test_base_agent_implementation():
    agent = MockAgent(name="test_mock")
    input_data = AgentInput(job_id="test_job")
    output = await agent.run(input_data)

    assert agent.name == "test_mock"
    assert output.success is True
    assert output.data["received"] == "test_job"

def test_agent_input_validation():
    with pytest.raises(ValidationError):
        # job_id is required
        AgentInput()
