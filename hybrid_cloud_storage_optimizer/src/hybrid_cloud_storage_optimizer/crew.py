import os

from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import (
    CrewBase,
    after_kickoff,
    agent,
    before_kickoff,
    crew,
    task,
)

from . import runtime_context
from .models import CustomerContext, StorageAnalysis
from .observability import get_logger, init_langfuse, log_usage, tracing_enabled
from .tools.storage_cost_calculator import StorageCostCalculatorTool

logger = get_logger()

# Single source of truth for the model. Override via the MODEL env var
# (set in .env or CI secrets); falls back to a sensible default.
DEFAULT_MODEL = "groq/llama-3.3-70b-versatile"


def _build_llm() -> LLM:
    """Construct the shared LLM from the MODEL environment variable.

    A low temperature keeps tool-call arguments and numeric reasoning stable —
    important for reliable function calling on Groq/Llama.
    """
    return LLM(model=os.getenv("MODEL", DEFAULT_MODEL), temperature=0.1)


@CrewBase
class HybridCloudStorageOptimizer:
    """Hybrid Cloud Storage Optimizer - NetApp + Hybrid Cloud migration crew"""

    @before_kickoff
    def stash_context(self, inputs):
        """Capture the customer context once so the cost tool can read it
        directly — the LLM never has to serialize it into a tool argument."""
        runtime_context.set_run_context_from_json(
            (inputs or {}).get("customer_context_json", "")
        )
        return inputs

    # Mid-run handoffs follow the same reliability pattern as the customer
    # context: typed task outputs that downstream tools need (workload segments,
    # timeline milestones) are stashed in the run context the moment the task
    # completes, so the cost tool reads them directly and the LLM keeps passing
    # only simple scalar tool arguments (avoids Groq/Llama tool_use_failed).
    @staticmethod
    def _stash_discovery_output(output) -> None:
        pyd = getattr(output, "pydantic", None)
        if pyd is not None:
            runtime_context.merge_milestones(getattr(pyd, "milestones", None))

    @staticmethod
    def _stash_storage_analysis(output) -> None:
        pyd = getattr(output, "pydantic", None)
        segments = getattr(pyd, "segments", None) if pyd is not None else None
        if segments:
            runtime_context.merge_run_context(
                {"segments": [segment.model_dump() for segment in segments]}
            )

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def requirements_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["requirements_analyst"],
            llm=_build_llm(),
            allow_delegation=False,
            verbose=True,
        )

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
    def discover_context(self) -> Task:
        return Task(
            config=self.tasks_config["discover_context"],
            agent=self.requirements_analyst(),
            output_pydantic=CustomerContext,
            callback=self._stash_discovery_output,
        )

    @task
    def analyze_storage(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_storage"],
            agent=self.storage_analyst(),
            output_pydantic=StorageAnalysis,
            callback=self._stash_storage_analysis,
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

    @after_kickoff
    def log_run(self, result):
        """Emit token usage / task summary after each run (observability)."""
        log_usage(result)
        return result

    @crew
    def crew(self) -> Crew:
        """Creates the full Hybrid Cloud Storage Optimizer crew"""
        tracing = tracing_enabled()
        langfuse = init_langfuse()
        logger.info(
            "Starting crew | model=%s | tracing=%s | langfuse=%s",
            os.getenv("MODEL", DEFAULT_MODEL),
            tracing,
            langfuse,
        )
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            tracing=tracing,
        )
