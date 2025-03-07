"""Test configuration and fixtures."""
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from stella_workflow.brokers.base import BrokerFactory
from stella_workflow.workflow import stella_agent

# Load environment variables from .env file
load_dotenv()


def get_redis_config() -> dict[str, Any]:
    """Get Redis configuration from environment variables."""
    ssl_cert_reqs = os.getenv("REDIS_SSL_CERT_REQS", "none").lower()
    ssl_cert_map = {
        "none": None,
        "optional": "optional",
        "required": "required",
    }

    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "username": os.getenv("REDIS_USERNAME"),
        "password": os.getenv("REDIS_PASSWORD"),
        "decode_responses": True,
        "ssl": os.getenv("REDIS_SSL", "false").lower() == "true",
        "ssl_cert_reqs": ssl_cert_map.get(ssl_cert_reqs, None),
    }


# Get Redis configuration from environment
REDIS_CONFIG = get_redis_config()


@pytest.fixture(autouse=True)
def configure_logging() -> None:
    """Configure logging levels for tests."""
    # Store original levels
    original_levels = {
        "stella_workflow": logging.getLogger("stella_workflow").level,
        "asyncio": logging.getLogger("asyncio").level,
    }

    # Set debug logging for troubleshooting
    logging.getLogger("stella_workflow").setLevel(logging.DEBUG)
    logging.getLogger("asyncio").setLevel(logging.DEBUG)

    yield

    # Restore original levels
    for logger_name, level in original_levels.items():
        logging.getLogger(logger_name).setLevel(level)


@pytest.fixture
def openai_api_key() -> str:
    """Get OpenAI API key from environment variable."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        pytest.skip("OPENAI_API_KEY environment variable not set or is default value")
    return api_key


@pytest_asyncio.fixture
async def broker() -> AsyncGenerator[Any, None]:
    """Fixture to provide a Redis broker for tests."""
    broker = BrokerFactory.create_broker("redis", REDIS_CONFIG)
    try:
        await broker.connect()  # Ensure broker is connected
        yield broker
    except Exception as e:
        print(f"Warning: Error while connecting broker: {e}")
        try:
            await broker.close()
        except Exception as e:
            print(f"Warning: Error while closing broker after connection failure: {e}")
        raise
    finally:
        try:
            await broker.close()
        except Exception as e:
            print(f"Warning: Error while closing broker: {e}")


@pytest.fixture
def test_topic() -> str:
    """Fixture to provide a unique topic name for tests."""
    return "test_topic"


@pytest_asyncio.fixture(autouse=True)
async def clear_redis_memory(broker: Any) -> AsyncGenerator[None, None]:
    """Clear Redis memory before and after each test."""
    try:
        if broker and broker.client:
            # Clear all keys matching memory:*
            keys = await broker.client.keys("memory:*")
            if keys:
                await broker.client.delete(*keys)
    except Exception as e:
        print(f"Warning: Error while clearing Redis memory: {e}")

    yield

    try:
        if broker and broker.client:
            # Clear all keys matching memory:*
            keys = await broker.client.keys("memory:*")
            if keys:
                await broker.client.delete(*keys)
    except Exception as e:
        print(f"Warning: Error while clearing Redis memory: {e}")


@pytest_asyncio.fixture(autouse=True)
async def clear_agents() -> AsyncGenerator[None, None]:
    """Clear registered agents before and after each test."""
    stella_agent.clear_agents()
    yield

    # Also clear after test for good measure
    if stella_agent._broker:
        try:
            await stella_agent._broker.close()
        except Exception as e:
            print(f"Warning: Error while closing broker: {e}")
    stella_agent.clear_agents()
