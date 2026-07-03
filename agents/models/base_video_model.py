from abc import ABC, abstractmethod


class BaseVideoModel(ABC):

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def generate_clip(self, prompt: str, duration: int = 10,
                      output_path: str | None = None) -> str | None:
        ...

    @abstractmethod
    def name(self) -> str:
        ...
