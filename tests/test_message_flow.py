import asyncio
import logging
from collections.abc import Generator
from typing import Any

import pytest
import pytest_asyncio

from stella_workflow.workflow import stella_agent

# Configure logging
logger = logging.getLogger("test_message_flow")

# Global variables to track message flow
producer_called = False
processor_called = False
consumer_called = False
producer_output = None
processor_output = None
consumer_output = None

@pytest_asyncio.fixture
async def test_broker(broker: Any) -> Any:
    """Use the broker fixture from conftest.py"""
    return broker

@pytest.fixture
def reset_tracking() -> Generator[None, None, None]:
    """Reset the global tracking variables before each test"""
    global producer_called, processor_called, consumer_called
    global producer_output, processor_output, consumer_output

    producer_called = False
    processor_called = False
    consumer_called = False
    producer_output = None
    processor_output = None
    consumer_output = None

    yield

    # Log final state for debugging
    logger.info(f"Final state - Producer called: {producer_called}, output: {producer_output}")
    logger.info(f"Final state - Processor called: {processor_called}, output: {processor_output}")
    logger.info(f"Final state - Consumer called: {consumer_called}, output: {consumer_output}")

@pytest_asyncio.fixture
async def setup_workflow(
    test_broker: Any, test_topic: str, reset_tracking: Any
) -> Generator[None, None, None]:
    """Set up a simple workflow with producer -> processor -> consumer"""
    # Clear any existing agents
    stella_agent.clear_agents()

    # Set the broker for all agents
    stella_agent._broker = test_broker

    # Define the producer agent (entry point)
    @stella_agent(name="producer", broker=test_broker, topic=test_topic)
    async def producer_agent() -> dict[str, str]:
        global producer_called, producer_output
        producer_called = True

        # Create a simple output message following the expected format
        output = {
            "value": "raw_data",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        producer_output = output
        logger.info(f"Producer agent called, returning: {output}")
        return output

    # Define the processor agent (depends on producer)
    @stella_agent(name="processor", broker=test_broker, topic=test_topic, depends_on=["producer"])
    async def processor_agent(message: dict[str, Any]) -> dict[str, Any]:
        """Process data from the producer"""
        global processor_called, processor_output

        # Log the input message for debugging
        logger.info(f"Processor received message: {message}")

        # Extract the producer data from the message
        producer_data = message.get("dependency_messages", {}).get("producer", {}).get("data", {})
        logger.info(f"Extracted producer data: {producer_data}")

        if not producer_data:
            logger.error("Missing required dependencies: producer data not found in message")
            return {"error": "Missing required dependencies"}

        # Process the data (convert to uppercase)
        value = producer_data.get("value", "").upper()

        # Create the output
        processor_output = {
            "value": value,
            "original_timestamp": producer_data.get("timestamp"),
            "processed_timestamp": "2024-01-01T00:01:00Z"
        }

        # Mark the processor as called
        processor_called = True

        logger.info(f"Processor agent called, returning: {processor_output}")
        return processor_output  # Return just the data, not wrapped with source

    # Define the consumer agent (depends on processor)
    @stella_agent(name="consumer", broker=test_broker, topic=test_topic, depends_on=["processor"])
    async def consumer_agent(message: dict[str, Any]) -> dict[str, Any]:
        """Consume data from the processor"""
        global consumer_called, consumer_output

        # Log the input message for debugging
        logger.info(f"Consumer received message: {message}")

        # Extract the processor data from the message
        processor_data = message.get("dependency_messages", {}).get("processor", {}).get("data", {})
        logger.info(f"Extracted processor data: {processor_data}")

        if not processor_data:
            logger.error("Missing required dependencies: processor data not found in message")
            return {"error": "Missing required dependencies"}

        # Process the data (add a status field)
        consumer_output = {
            "value": processor_data.get("value"),
            "original_timestamp": processor_data.get("original_timestamp"),
            "processed_timestamp": processor_data.get("processed_timestamp"),
            "status": "completed"
        }

        # Mark the consumer as called
        consumer_called = True

        logger.info(f"Consumer agent called, returning: {consumer_output}")
        return consumer_output

    yield

    # Clean up
    await stella_agent.stop_workflow()
    stella_agent.clear_agents()

async def test_simple_message_flow(
    setup_workflow: Any, test_broker: Any, test_topic: str
) -> None:
    """Test a simple message flow: producer -> processor -> consumer"""
    logger.info(f"Starting simple message flow test with topic: {test_topic}")

    # Start the workflow - this will trigger the producer automatically
    await stella_agent.start_workflow()

    # Wait for the message flow to complete
    # This is necessary because the messages are processed asynchronously
    for _ in range(10):  # Try for up to 10 seconds
        if producer_called and processor_called and consumer_called:
            break
        await asyncio.sleep(1)

    # Verify that all agents were called
    assert producer_called, "Producer agent was not called"
    assert processor_called, "Processor agent was not called"
    assert consumer_called, "Consumer agent was not called"

    # Verify the output of each agent
    assert producer_output is not None, "Producer did not generate output"
    assert producer_output.get("value") == "raw_data", "Producer output is incorrect"

    assert processor_output is not None, "Processor did not generate output"
    assert (
        processor_output.get("value") == "RAW_DATA"
    ), "Processor did not transform the data correctly"

    assert consumer_output is not None, "Consumer did not generate output"
    assert consumer_output.get("status") == "completed", "Consumer did not add status field"
    assert consumer_output.get("value") == "RAW_DATA", "Consumer output has incorrect value"

async def test_dependency_resolution(
    setup_workflow: Any, test_broker: Any, test_topic: str
) -> None:
    """Test that dependencies are properly resolved in the message flow"""
    logger.info(f"Starting dependency resolution test with topic: {test_topic}")

    # Start the workflow - this will trigger the producer automatically
    await stella_agent.start_workflow()

    # Wait for the message flow to complete
    for _ in range(10):  # Try for up to 10 seconds
        if producer_called and processor_called and consumer_called:
            break
        await asyncio.sleep(1)

    # Verify that the processor received the producer's output in its dependencies
    assert processor_output is not None, "Processor did not generate output"
    assert processor_output.get("original_timestamp") == producer_output.get("timestamp"), \
        "Processor did not receive producer's timestamp"

    # Verify that the consumer received the processor's output in its dependencies
    assert consumer_output is not None, "Consumer did not generate output"
    assert consumer_output.get("value") == processor_output.get("value"), \
        "Consumer did not receive processor's value"
    assert (
        consumer_output.get("processed_timestamp") == processor_output.get("processed_timestamp")
    ), "Consumer did not receive processor's timestamp"
