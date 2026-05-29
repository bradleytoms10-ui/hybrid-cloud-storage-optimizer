import os

from crewai import LLM, Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew
from .models import StorageAnalysis
from .tools.storage_cost_calculator import StorageCostCalculatorTool

# Single source of truth for the model. Override via the MODEL env var
# (set in .env or CI secrets); falls back to a sensible default.
DEFAULT_MODEL = "groq/llama-3.3-70b-versatile"


def _build_llm() -> LLM:
    """Construct the shared LLM from the MODEL environment variable."""
    return LLM(model=os.getenv("MODEL", DEFAULT_MODEL))


@CrewBase
class HybridCloudStorageOptimizer:
    """Hybrid Cloud Storage Optimizer - NetApp + Hybrid Cloud migration crew"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def storage_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["storage_analyst"],
            llm=_build_llm(),
            allow_delegation=False,
            verbose=True,
        )

    @agent
    def cloud_cost_estimator(self) -> Agent:
        return Agent(
            config=self.agents_config["cloud_cost_estimator"],
            llm=_build_llm(),
            allow_delegation=False,
            verbose=True,
            tools=[StorageCostCalculatorTool()],
        )

    @agent
    def migration_architect(self) -> Agent:
        return Agent(
            config=self.agents_config["migration_architect"],
            llm=_build_llm(),
            allow_delegation=False,
            verbose=True,
        )

    @task
    def analyze_storage(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_storage"],
            agent=self.storage_analyst(),
            output_pydantic=StorageAnalysis,
        )

    @task
    def estimate_costs(self) -> Task:
        return Task(
            config=self.tasks_config["estimate_costs"],
            agent=self.cloud_cost_estimator(),
        )

    @task
    def generate_plan(self) -> Task:
        return Task(
            config=self.tasks_config["generate_plan"],
            agent=self.migration_architect(),
        )

    @crew
    def crew(self) -> Crew:
        """Creates the full Hybrid Cloud Storage Optimizer crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
