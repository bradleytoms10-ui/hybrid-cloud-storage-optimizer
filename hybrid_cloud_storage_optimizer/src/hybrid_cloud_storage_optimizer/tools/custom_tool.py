"""Template for adding new CrewAI tools to this project.

This is a reference scaffold — it is intentionally NOT registered on any agent.
The production tool used by the crew is ``StorageCostCalculatorTool`` in
``storage_cost_calculator.py``. Copy this pattern to add a new capability
(e.g. a Terraform-plan generator or a live cloud-pricing fetcher), then wire it
onto an agent in ``crew.py`` via ``tools=[...]``.
"""

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ExampleToolInput(BaseModel):
    """Input schema. Field descriptions are shown to the agent."""

    argument: str = Field(..., description="What this argument represents.")


class ExampleTool(BaseTool):
    name: str = "example_tool"
    description: str = (
        "Describe precisely what the tool does and when to use it — the agent "
        "relies on this text to decide whether and how to call the tool."
    )
    args_schema: Type[BaseModel] = ExampleToolInput

    def _run(self, argument: str) -> str:
        raise NotImplementedError("Replace with a real implementation before use.")
