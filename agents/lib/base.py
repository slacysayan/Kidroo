from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

class AgentInput(BaseModel):
    job_id: str
    video_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)

class AgentOutput(BaseModel):
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

class BaseAgent(ABC, BaseModel):
    name: str

    @abstractmethod
    async def run(self, input: AgentInput) -> AgentOutput:
        pass
