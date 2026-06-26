import abc


class VisionSource(abc.ABC):
    """Abstract base for a single layer of scene perception.

    Each source attempts to describe what is currently on screen using a
    different strategy (structured DOM, accessibility tree, or a vision model).
    A source returns a short natural-language description on success, or
    ``None`` when it cannot perceive anything (wrong context, missing
    dependency, runtime error) so the chain can fall through to the next layer.
    """

    @abc.abstractmethod
    def capture(self) -> str | None:
        """Return a one-line scene description, or ``None`` if unavailable."""
        raise NotImplementedError
