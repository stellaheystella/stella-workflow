"""Base classes and factory for message brokers."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional


class MessageBroker(ABC):
    @abstractmethod
    async def publish(self, topic: str, message: Any, source: Optional[str] = None) -> None:
        pass

    @abstractmethod
    async def subscribe(
        self,
        topic: str,
        callback: Callable[[dict[str, Any]], Any],
        source_filter: Optional[str] = None
    ) -> None:
        pass

    @abstractmethod
    async def acknowledge(self, message_id: str) -> None:
        pass

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @abstractmethod
    async def get_message(
        self,
        topic: str,
        source_filter: Optional[str] = None
    ) -> Any:
        pass

    @abstractmethod
    async def get_memory(self, namespace: str, key: str) -> Any:
        """Get a value from memory.

        Args:
            namespace (str): The namespace for the memory (e.g. agent name)
            key (str): The key to retrieve

        Returns:
            Any: The stored value

        Raises:
            KeyError: If the key doesn't exist in memory
        """
        pass

    @abstractmethod
    async def set_memory(self, namespace: str, key: str, value: Any) -> None:
        """Set a value in memory.

        Args:
            namespace (str): The namespace for the memory (e.g. agent name)
            key (str): The key to store
            value (Any): The value to store (must be JSON serializable)
        """
        pass

class BrokerFactory:
    """Factory class for creating message broker instances.

    This class provides a factory method to create different types of message brokers
    (Redis, Kafka, RabbitMQ etc.) based on the specified broker type. It abstracts away
    the broker-specific initialization details behind a common interface.
    """

    @staticmethod
    def create_broker(broker_type: str, config: dict) -> MessageBroker:
        """Create and return a message broker instance of the specified type.

        Args:
            broker_type (str): The type of broker to create ('redis', 'kafka', 'rabbitmq')
            config (dict): Configuration dictionary for the broker connection

        Returns:
            MessageBroker: An instance of the specified message broker

        Raises:
            ValueError: If the specified broker type is not supported
        """
        # Import broker implementations dynamically
        if broker_type.lower() == 'redis':
            from . import RedisBroker
            return RedisBroker(config)
        else:
            raise ValueError(f"Unsupported broker type: {broker_type}")
