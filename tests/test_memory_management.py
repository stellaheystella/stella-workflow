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
logger = logging.getLogger("test_memory_management")

# Global variables to track agent calls
sensor_called = False
processor_called = False
analyzer_called = False

# Global variables to store agent outputs
sensor_output = None
processor_output = None
analyzer_output = None

@pytest_asyncio.fixture
async def test_broker(broker: Any) -> Any:
    """Get the test broker"""
    return broker

@pytest.fixture
def test_topic() -> str:
    """Generate a unique topic for each test"""
    return f"test_memory_topic_{uuid.uuid4().hex}"

@pytest.fixture
def reset_tracking() -> None:
    """Reset the global tracking variables before each test"""
    global sensor_called, processor_called, analyzer_called
    global sensor_output, processor_output, analyzer_output

    sensor_called = False
    processor_called = False
    analyzer_called = False

    sensor_output = None
    processor_output = None
    analyzer_output = None

@pytest_asyncio.fixture
async def setup_workflow(
    test_broker: Any, test_topic: str, reset_tracking: None
) -> Generator[None, None, None]:
    """Set up the workflow with sensor, processor, and analyzer agents"""
    global sensor_called, processor_called, analyzer_called
    global sensor_output, processor_output, analyzer_output

    try:
        # Clear any existing agents
        stella_agent.clear_agents()

        # Define the sensor agent
        @stella_agent(name="sensor", broker=test_broker, topic=test_topic)
        async def sensor_agent() -> dict[str, Any]:
            """Generate sensor data"""
            global sensor_called, sensor_output

            # Generate test data
            sensor_output = {
                "value": 42,
                "timestamp": datetime.now().isoformat()
            }

            # Mark the sensor as called
            sensor_called = True

            # Update state to track this call
            await sensor_agent.update_state(
                messages_processed=1,
                last_processed_time=datetime.now().isoformat(),
                status="running"
            )

            logger.info(f"Sensor agent called, returning: {sensor_output}")
            return sensor_output

        # Define the processor agent
        @stella_agent(name="processor", broker=test_broker, topic=test_topic, depends_on=["sensor"])
        async def processor_agent(message: dict[str, Any]) -> dict[str, Any] | None:
            """Process sensor data"""
            global processor_called, processor_output

            logger.info(f"Processor received message: {message}")

            # Skip messages from self
            if message.get("source") == "processor":
                logger.debug("Processor skipping message from self")
                return None

            # Get message ID from the dependency messages
            message_id = (
                message.get("dependency_messages", {})
                .get("sensor", {})
                .get("id")
            )
            if not message_id:
                logger.debug("No message ID found in dependency messages")
                return None

            # Get current state to check processed messages
            current_state = await processor_agent.get_state()
            processed_messages = current_state.get("processed_messages", [])

            if message_id in processed_messages:
                logger.debug(f"Already processed message {message_id}")
                return None

            # Extract the sensor data
            sensor_data = (
                message.get("dependency_messages", {})
                .get("sensor", {})
                .get("data", {})
            )

            # Process the data
            processor_output = {
                "processed_value": sensor_data.get("value") * 2,
                "original_timestamp": sensor_data.get("timestamp"),
                "processed_timestamp": datetime.now().isoformat()
            }

            # Mark the processor as called
            processor_called = True

            # Update state to track this call and processed message
            processed_messages.append(message_id)
            await processor_agent.update_state(
                messages_processed=len(processed_messages),
                processed_messages=processed_messages,
                last_processed_time=datetime.now().isoformat(),
                status="running"
            )

            logger.info(f"Processor agent called, returning: {processor_output}")
            return processor_output

        # Define the analyzer agent
        @stella_agent(
            name="analyzer",
            broker=test_broker,
            topic=test_topic,
            depends_on=["processor"]
        )
        async def analyzer_agent(message: dict[str, Any]) -> dict[str, Any]:
            """Analyze processed data"""
            global analyzer_called, analyzer_output

            logger.info(f"Analyzer received message: {message}")

            # Extract the processor data
            processor_data = (
                message.get("dependency_messages", {})
                .get("processor", {})
                .get("data", {})
            )

            # Analyze the data
            analyzer_output = {
                "analysis_result": (
                    "normal" if processor_data.get("processed_value") < 100 else "high"
                ),
                "processed_value": processor_data.get("processed_value"),
                "analyzed_timestamp": datetime.now().isoformat()
            }

            # Mark the analyzer as called
            analyzer_called = True

            # Get current state
            current_state = await analyzer_agent.get_state()
            messages_processed = current_state.get("messages_processed", 0) + 1

            # Update state to track this call
            await analyzer_agent.update_state(
                messages_processed=messages_processed,
                last_processed_time=datetime.now().isoformat(),
                status="running"
            )

            logger.info(
                f"Analyzer agent called, returning: {analyzer_output}"
            )
            return analyzer_output

        yield

    finally:
        # Clean up
        await stella_agent.stop_workflow()
        stella_agent.clear_agents()
        # Cancel any pending tasks
        for task in asyncio.all_tasks():
            if not task.done() and task != asyncio.current_task():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

async def test_state_memory_updates(
    setup_workflow: Any, test_broker: Any, test_topic: str
) -> None:
    """Test that agent state memory is properly updated during message flow"""
    logger.info(f"Starting state memory test with topic: {test_topic}")

    try:
        # Start the workflow
        await stella_agent.start_workflow()

        # Wait for the message flow to complete
        for _ in range(10):  # Try for up to 10 seconds
            if sensor_called and processor_called and analyzer_called:
                break
            await asyncio.sleep(1)

        # Verify that all agents were called
        assert sensor_called, "Sensor agent was not called"
        assert processor_called, "Processor agent was not called"
        assert analyzer_called, "Analyzer agent was not called"

        # Get the registered agents
        agents = stella_agent.get_agents()

        # Verify sensor state memory
        sensor_state = await agents["sensor"]["handler"].get_state()
        assert "messages_processed" in sensor_state, "Sensor state missing messages_processed"
        assert (
            sensor_state["messages_processed"] == 1
        ), "Sensor messages_processed count incorrect"
        assert "last_processed_time" in sensor_state, "Sensor state missing last_processed_time"
        assert "status" in sensor_state, "Sensor state missing status"
        assert sensor_state["status"] == "running", "Sensor status incorrect"

        # Verify processor state memory
        processor_state = await agents["processor"]["handler"].get_state()
        assert (
            "messages_processed" in processor_state
        ), "Processor state missing messages_processed"
        assert (
            processor_state["messages_processed"] == 1
        ), "Processor messages_processed count incorrect"
        assert (
            "last_processed_time" in processor_state
        ), "Processor state missing last_processed_time"
        assert "status" in processor_state, "Processor state missing status"
        assert processor_state["status"] == "running", "Processor status incorrect"

        # Verify analyzer state memory
        analyzer_state = await agents["analyzer"]["handler"].get_state()
        assert (
            "messages_processed" in analyzer_state
        ), "Analyzer state missing messages_processed"
        assert (
            analyzer_state["messages_processed"] == 1
        ), "Analyzer messages_processed count incorrect"
        assert (
            "last_processed_time" in analyzer_state
        ), "Analyzer state missing last_processed_time"
        assert "status" in analyzer_state, "Analyzer state missing status"
        assert analyzer_state["status"] == "running", "Analyzer status incorrect"

        # Verify the output of each agent
        assert sensor_output is not None, "Sensor did not generate output"
        assert sensor_output.get("value") == 42, "Sensor output is incorrect"

        assert processor_output is not None, "Processor did not generate output"
        assert (
            processor_output.get("processed_value") == 84
        ), "Processor did not transform the data correctly"

        assert analyzer_output is not None, "Analyzer did not generate output"
        assert (
            analyzer_output.get("analysis_result") == "normal"
        ), "Analyzer did not analyze the data correctly"

    finally:
        # Clean up any pending tasks and connections
        await test_broker.close()
        # Cancel any pending tasks
        for task in asyncio.all_tasks():
            if not task.done() and task != asyncio.current_task():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

async def test_dependency_memory_management(
    setup_workflow: Any, test_broker: Any, test_topic: str
) -> None:
    """Test that dependency memory is properly managed during message flow"""
    logger.info(f"Starting dependency memory test with topic: {test_topic}")

    try:
        # Start the workflow
        await stella_agent.start_workflow()

        # Wait for the message flow to complete
        for _ in range(10):  # Try for up to 10 seconds
            if sensor_called and processor_called and analyzer_called:
                break
            await asyncio.sleep(1)

        # Verify that all agents were called
        assert sensor_called, "Sensor agent was not called"
        assert processor_called, "Processor agent was not called"
        assert analyzer_called, "Analyzer agent was not called"

        # Verify that the processor received the sensor's output in its dependencies
        assert processor_output is not None, "Processor did not generate output"
        assert (
            processor_output.get("original_timestamp") == sensor_output.get("timestamp")
        ), "Processor did not receive sensor's timestamp"

        # Verify that the analyzer received the processor's output in its dependencies
        assert analyzer_output is not None, "Analyzer did not generate output"
        assert (
            analyzer_output.get("processed_value") == processor_output.get("processed_value")
        ), "Analyzer did not receive processor's value"

        # Verify dependency memory structure
        # This would require accessing the broker's memory directly, which might not be possible
        # Instead, we verify the correct data was passed through the message flow

    finally:
        # Clean up any pending tasks and connections
        await test_broker.close()
        # Cancel any pending tasks
        for task in asyncio.all_tasks():
            if not task.done() and task != asyncio.current_task():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
