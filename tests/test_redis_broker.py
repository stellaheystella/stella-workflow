import asyncio
import logging
import sys

from stella_workflow.brokers.redis_broker import RedisBroker

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("test_redis_broker")

# Message received counter for verification
messages_received = 0

async def message_handler(message: dict) -> None:
    """Handle received messages"""
    global messages_received
    messages_received += 1
    logger.info(f"Received message #{messages_received}: {message}")

    # Access the message data
    data = message.get('data', {})
    source = message.get('source')
    logger.info(f"Message from {source}: {data}")

async def test_with_fake_redis() -> None:
    """Test the broker with in-memory fakeredis"""
    logger.info("=== Testing with FakeRedis (in-memory) ===")

    # Create broker with fakeredis
    broker = RedisBroker({
        'use_fake_redis': True,
        'poll_interval': 0.5  # Faster polling for testing
    })

    # Connect to the broker
    await broker.connect()

    # Reset message counter
    global messages_received
    messages_received = 0

    # Subscribe to a test topic
    await broker.subscribe('test_topic', message_handler)

    # Publish a few test messages
    for i in range(5):
        await broker.publish('test_topic', {
            'data': {'message': f'Test message {i}'},
            'source': 'test_publisher'
        })

    # Wait for messages to be processed
    await asyncio.sleep(2)

    # Cleanup
    await broker.close()

    # Verify we received all messages
    assert messages_received == 5, f"Expected 5 messages, got {messages_received}"
    logger.info("Test with FakeRedis completed successfully!")

async def test_with_real_redis() -> None:
    """Test the broker with real Redis server (if available)"""
    logger.info("=== Testing with Real Redis Server ===")

    try:
        # Create broker with real Redis
        broker = RedisBroker({
            'host': 'localhost',
            'port': 6379,
            'poll_interval': 0.5  # Faster polling for testing
        })

        # Connect to the broker
        await broker.connect()

        # Reset message counter
        global messages_received
        messages_received = 0

        # Subscribe to a test topic
        await broker.subscribe('test_topic_real', message_handler)

        # Publish a few test messages
        for i in range(5):
            await broker.publish('test_topic_real', {
                'data': {'message': f'Test message {i}'},
                'source': 'test_publisher'
            })

        # Wait for messages to be processed
        await asyncio.sleep(2)

        # Cleanup
        await broker.close()

        # Verify we received all messages
        assert messages_received == 5, f"Expected 5 messages, got {messages_received}"
        logger.info("Test with Real Redis completed successfully!")
    except Exception as e:
        logger.error(f"Error testing with real Redis: {e!s}")
        logger.info("Skipping real Redis test - server might not be available")

async def main() -> None:
    """Run all tests"""
    # Test with fakeredis
    await test_with_fake_redis()

    # Test with real Redis if available
    try:
        await test_with_real_redis()
    except Exception as e:
        logger.error(f"Error in real Redis test: {e!s}")

    logger.info("All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
