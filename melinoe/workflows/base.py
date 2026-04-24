from typing import override
from melinoe.client import ModelConfig
from abc import ABC, abstractmethod


class Step(ABC):
    model_config: ModelConfig

    def __init__(self):
        self.validate_init()

    def validate_init(self) -> None:
        """
        Validate that the Step has a ModelConfig attribute. This is required for any Step to function properly.
        """
        if not hasattr(self, "model_config") or not self.model_config:
            raise ValueError("ModelConfig is required for Step initialization.")

    @abstractmethod
    def validate(self, *args, **kwargs) -> None:
        """
        Validate the input arguments for the step. This method should be overridden by subclasses to implement specific validation logic.
        """
        pass

    @abstractmethod
    def execute(self, *args, **kwargs):
        """
        Execute the step's main logic. This method must be implemented by subclasses to define the specific behavior of the step.
        """
        pass

    def run(self, *args, **kwargs):
        self.validate(*args, **kwargs)
        return self.execute(*args, **kwargs)


class Workflow(ABC):
    steps: list[Step]

    @abstractmethod
    def run(self, *args, **kwargs):
        pass
