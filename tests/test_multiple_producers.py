import asyncio
import logging
import uuid
from collections.abc import Generator
from datetime import datetime
from typing import Any

import pytest
import pytest_asyncio

from stella_workflow import stella_agent

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_multiple_producers")

# Global variables to track agent calls
counter_called = False
namer_called = False
consumer_called = False

# Global variables to store agent outputs
counter_output = None
namer_output = None
consumer_output = None

@pytest_asyncio.fixture
async def test_broker(broker: Any) -> Any:
    """Get the test broker"""
    return broker

@pytest.fixture
def test_topic() -> str:
    """Generate a unique topic for each test"""
    return f"test_multiple_producers_topic_{uuid.uuid4().hex}"

@pytest.fixture
def reset_tracking() -> None:
    """Reset the global tracking variables before each test"""
    global counter_called, namer_called, consumer_called
    global counter_output, namer_output, consumer_output

    counter_called = False
    namer_called = False
    consumer_called = False

    counter_output = None
    namer_output = None
    consumer_output = None

@pytest_asyncio.fixture
async def setup_workflow(
    test_broker: Any, test_topic: str, reset_tracking: None
) -> Generator[None, None, None]:
    """Set up the workflow with counter, namer, and consumer agents"""
    global counter_called, namer_called, consumer_called
    global counter_output, namer_output, consumer_output

    # Clear any existing agents
    stella_agent.clear_agents()

    # Define the counter agent
    @stella_agent(name="counter", broker=test_broker, topic=test_topic)
    async def counter_agent() -> dict[str, Any]:
        """Generate counter data"""
        global counter_called, counter_output

        # Generate test data
        counter_output = {
            "count": 42,
            "timestamp": datetime.now().isoformat()
        }

        # Mark the counter as called
        counter_called = True

        logger.info(f"Counter agent called, returning: {counter_output}")
        return counter_output

    # Define the namer agent
    @stella_agent(name="namer", broker=test_broker, topic=test_topic)
    async def namer_agent() -> dict[str, str]:
        """Generate name data"""
        global namer_called, namer_output

        # Generate test data
        namer_output = {
            "name": "test",
            "timestamp": datetime.now().isoformat()
        }

        # Mark the namer as called
        namer_called = True

        logger.info(f"Namer agent called, returning: {namer_output}")
        return namer_output

    # Define the consumer agent
    @stella_agent(
        name="consumer",
        broker=test_broker,
        topic=test_topic,
        depends_on=["counter", "namer"]
    )
    async def consumer_agent(message: dict[str, Any]) -> dict[str, str]:
        """Consume data from multiple producers"""
        global consumer_called, consumer_output

        logger.info(f"Consumer received message: {message}")

        # Extract the producer data
        counter_data = message.get("dependency_messages", {}).get("counter", {}).get("data", {})
        namer_data = message.get("dependency_messages", {}).get("namer", {}).get("data", {})

        # Process the data
        consumer_output = {
            "result": f"{namer_data.get('name')}_{counter_data.get('count')}",
            "counter_timestamp": counter_data.get("timestamp"),
            "namer_timestamp": namer_data.get("timestamp"),
            "processed_timestamp": datetime.now().isoformat()
        }

        # Mark the consumer as called
        consumer_called = True

        logger.info(f"Consumer agent called, returning: {consumer_output}")
        return consumer_output

    yield

async def test_multiple_producers_flow(
    setup_workflow: Any, test_broker: Any, test_topic: str
) -> None:
    """Test that multiple producers can feed into a single consumer"""
    logger.info(f"Starting multiple producers test with topic: {test_topic}")

    # Start the workflow
    await stella_agent.start_workflow()

    # Wait for the message flow to complete
    for _ in range(10):  # Try for up to 10 seconds
        if counter_called and namer_called and consumer_called:
            break
        await asyncio.sleep(1)

    # Verify that all producers were called
    assert counter_called, "Counter agent was not called"
    assert namer_called, "Namer agent was not called"

    # Verify the output of each producer
    assert counter_output is not None, "Counter did not generate output"
    assert counter_output.get("count") == 42, "Counter output is incorrect"

    assert namer_output is not None, "Namer did not generate output"
    assert namer_output.get("name") == "test", "Namer output is incorrect"

    # Verify that the consumer was called
    assert consumer_called, "Consumer agent was not called"
    assert consumer_output is not None, "Consumer did not generate output"

    # Verify that the consumer received data from both producers
    assert consumer_output.get("result") == "test_42", "Consumer did not combine data correctly"
    assert (
        consumer_output.get("counter_timestamp") == counter_output.get("timestamp")
    ), "Consumer did not receive counter timestamp"
    assert (
        consumer_output.get("namer_timestamp") == namer_output.get("timestamp")
    ), "Consumer did not receive namer timestamp"
