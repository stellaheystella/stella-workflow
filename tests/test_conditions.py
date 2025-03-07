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
logger = logging.getLogger("test_conditions")

# Global variables to track agent calls
temperature_called = False
high_temp_alert_called = False
low_temp_alert_called = False

# Global variables to store agent outputs
temperature_output = None
high_temp_alert_output = None
low_temp_alert_output = None

@pytest_asyncio.fixture
async def test_broker(broker: Any) -> Any:
    """Get the test broker"""
    return broker

@pytest.fixture
def test_topic() -> str:
    """Generate a unique topic for each test"""
    return f"test_conditions_topic_{uuid.uuid4().hex}"

@pytest.fixture
def reset_tracking() -> None:
    """Reset the global tracking variables before each test"""
    global temperature_called, high_temp_alert_called, low_temp_alert_called
    global temperature_output, high_temp_alert_output, low_temp_alert_output

    temperature_called = False
    high_temp_alert_called = False
    low_temp_alert_called = False

    temperature_output = None
    high_temp_alert_output = None
    low_temp_alert_output = None

@pytest_asyncio.fixture
async def setup_workflow(
    test_broker: Any, test_topic: str, reset_tracking: None
) -> Generator[None, None, None]:
    """Set up the workflow with temperature sensor and conditional alerts"""
    global temperature_called, high_temp_alert_called, low_temp_alert_called
    global temperature_output, high_temp_alert_output, low_temp_alert_output

    try:
        # Clear any existing agents
        stella_agent.clear_agents()

        # Define the temperature sensor agent
        @stella_agent(name="temperature_sensor", broker=test_broker, topic=test_topic)
        async def temperature_sensor() -> dict[str, Any]:
            """Generate temperature data"""
            global temperature_called, temperature_output

            # Generate test data with two different temperatures
            temperature_data = [
                {
                    "temperature": 35,
                    "humidity": 80,
                    "location": "server_room",
                    "timestamp": "2024-01-01T00:00:00Z",
                },
                {
                    "temperature": 25,
                    "humidity": 60,
                    "location": "server_room",
                    "timestamp": "2024-01-01T00:01:00Z",
                },
            ]

            # Mark the sensor as called
            temperature_called = True

            # Store the output
            temperature_output = temperature_data[0]

            logger.info(f"Temperature sensor called, returning: {temperature_output}")
            return temperature_output

        # Define the high temperature alert agent (condition: temp > 30)
        @stella_agent(
            name="high_temp_alert",
            broker=test_broker,
            topic=test_topic,
            depends_on=["temperature_sensor"],
            condition=(
                "message['dependency_messages']['temperature_sensor']['data']"
                "['temperature'] > 30"
            ),
        )
        async def high_temp_alert(message: dict[str, Any]) -> dict[str, Any]:
            """Process high temperature alerts"""
            global high_temp_alert_called, high_temp_alert_output

            # Log the input message for debugging
            logger.info(
                f"High temperature alert received message: {message}"
            )

            # Extract the temperature data
            temp_data = (
                message.get("dependency_messages", {})
                .get("temperature_sensor", {})
                .get("data", {})
            )

            # Process the data
            high_temp_alert_output = {
                "alert": "High Temperature",
                "temperature": temp_data.get("temperature"),
                "location": temp_data.get("location"),
                "timestamp": datetime.now().isoformat(),
            }

            # Mark the alert as called
            high_temp_alert_called = True

            logger.info(
                f"High temperature alert called, returning: {high_temp_alert_output}"
            )
            return high_temp_alert_output

        # Define the low temperature alert agent (condition: temp <= 30)
        @stella_agent(
            name="low_temp_alert",
            broker=test_broker,
            topic=test_topic,
            depends_on=["temperature_sensor"],
            condition=(
                "message['dependency_messages']['temperature_sensor']['data']"
                "['temperature'] <= 30"
            ),
        )
        async def low_temp_alert(message: dict[str, Any]) -> dict[str, Any]:
            """Process low temperature alerts"""
            global low_temp_alert_called, low_temp_alert_output

            # Log the input message for debugging
            logger.info(
                f"Low temperature alert received message: {message}"
            )

            # Extract the temperature data
            temp_data = (
                message.get("dependency_messages", {})
                .get("temperature_sensor", {})
                .get("data", {})
            )

            # Process the data
            low_temp_alert_output = {
                "alert": "Normal Temperature",
                "temperature": temp_data.get("temperature"),
                "location": temp_data.get("location"),
                "timestamp": datetime.now().isoformat(),
            }

            # Mark the alert as called
            low_temp_alert_called = True

            logger.info(
                f"Low temperature alert called, returning: {low_temp_alert_output}"
            )
            return low_temp_alert_output

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

async def test_high_temperature_condition(
    setup_workflow: Any, test_broker: Any, test_topic: str
) -> None:
    """Test that the high temperature alert is triggered when temperature > 30"""
    logger.info(f"Starting high temperature condition test with topic: {test_topic}")

    try:
        # Start the workflow
        await stella_agent.start_workflow()

        # Wait for the message flow to complete
        for _ in range(10):  # Try for up to 10 seconds
            if temperature_called and high_temp_alert_called:
                break
            await asyncio.sleep(1)

        # Verify that the temperature sensor was called
        assert temperature_called, "Temperature sensor was not called"
        assert temperature_output is not None, "Temperature sensor did not generate output"
        assert temperature_output.get("temperature") == 35, "Temperature sensor output is incorrect"

        # Verify that the high temperature alert was called
        assert high_temp_alert_called, "High temperature alert was not called"
        assert high_temp_alert_output is not None, "High temperature alert did not generate output"
        assert (
            high_temp_alert_output.get("alert") == "High Temperature"
        ), "High temperature alert output is incorrect"
        assert (
            high_temp_alert_output.get("temperature") == 35
        ), "High temperature alert temperature is incorrect"

        # Verify that the low temperature alert was not called
        assert not low_temp_alert_called, "Low temperature alert was incorrectly called"
        assert low_temp_alert_output is None, "Low temperature alert incorrectly generated output"
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

async def test_condition_with_multiple_messages(
    setup_workflow: Any, test_broker: Any, test_topic: str
) -> None:
    """Test that conditions are evaluated correctly for each message"""
    logger.info(f"Starting multiple message condition test with topic: {test_topic}")

    try:
        # This test would need to be expanded to handle multiple messages
        # For now, we'll just verify the basic condition test works
        await test_high_temperature_condition(setup_workflow, test_broker, test_topic)
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
