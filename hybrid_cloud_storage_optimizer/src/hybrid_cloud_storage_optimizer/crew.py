from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew


@CrewBase
class HybridCloudStorageOptimizer:
    """Hybrid Cloud Storage Optimizer - NetApp + Hybrid Cloud migration crew"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def storage_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["storage_analyst"],
            allow_delegation=False,
            verbose=True,
        )

    @agent
    def cloud_cost_estimator(self) -> Agent:
        return Agent(
            config=self.agents_config["cloud_cost_estimator"],
            allow_delegation=False,
            verbose=True,
        )

    @agent
    def migration_architect(self) -> Agent:
        return Agent(
            config=self.agents_config["migration_architect"],
            allow_delegation=False,
            verbose=True,
        )

    @task
    def analyze_storage(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_storage"],
            agent=self.storage_analyst(),
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