import asyncio
import json
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

async def message_handler(message):
    """Handle received messages"""
    global messages_received
    messages_received += 1
    logger.info(f"Received message #{messages_received}: {message}")
    
    # Access the message data
    data = message.get('data', {})
    source = message.get('source')
    logger.info(f"Message from {source}: {data}")

async def test_with_fake_redis():
    """Test the broker with in-memory fakeredis"""
    logger.info("=== Testing with FakeRedis (in-memory) ===")
    
    # Create broker with fakeredis
    broker = RedisBroker({
        'use_fake_redis': True,
        'poll_interval': 0.5  # Faster polling for testing
    })
    
    # Connect to Redis
    await broker.connect()
    
    # Subscribe to test topic
    test_topic = "test_topic"
    await broker.subscribe(test_topic, message_handler)
    
    # Wait a moment for subscription to be ready
    await asyncio.sleep(1)
    
    # Publish 5 test messages
    logger.info("Publishing test messages...")
    for i in range(1, 6):
        await broker.publish(
            topic=test_topic,
            message={"value": f"test_message_{i}", "count": i},
            source="test_publisher"
        )
        # Small delay between messages
        await asyncio.sleep(0.2)
    
    # Wait for messages to be processed
    logger.info("Waiting for messages to be processed...")
    await asyncio.sleep(3)
    
    # Verify results
    logger.info(f"Total messages received: {messages_received}")
    assert messages_received == 5, f"Expected 5 messages, got {messages_received}"
    logger.info("Test with FakeRedis completed successfully!")

async def test_with_real_redis():
    """Test the broker with real Redis server (if available)"""
    logger.info("=== Testing with Real Redis Server ===")
    global messages_received
    messages_received = 0
    
    # Create broker with real Redis
    broker = RedisBroker({
        'host': 'localhost',
        'port': 6379,
        'poll_interval': 0.5  # Faster polling for testing
    })
    
    try:
        # Connect to Redis
        await broker.connect()
        
        # Subscribe to test topic
        test_topic = "test_topic_real"
        await broker.subscribe(test_topic, message_handler)
        
        # Wait a moment for subscription to be ready
        await asyncio.sleep(1)
        
        # Publish 5 test messages
        logger.info("Publishing test messages...")
        for i in range(1, 6):
            await broker.publish(
                topic=test_topic,
                message={"value": f"test_message_{i}", "count": i},
                source="test_publisher"
            )
            # Small delay between messages
            await asyncio.sleep(0.2)
        
        # Wait for messages to be processed
        logger.info("Waiting for messages to be processed...")
        await asyncio.sleep(3)
        
        # Verify results
        logger.info(f"Total messages received: {messages_received}")
        assert messages_received == 5, f"Expected 5 messages, got {messages_received}"
        logger.info("Test with Real Redis completed successfully!")
    except Exception as e:
        logger.error(f"Error testing with real Redis: {str(e)}")
        logger.info("Skipping real Redis test - server might not be available")

async def main():
    """Run all tests"""
    # Test with fakeredis
    await test_with_fake_redis()
    
    # Test with real Redis if available
    try:
        await test_with_real_redis()
    except Exception as e:
        logger.error(f"Error in real Redis test: {str(e)}")
    
    logger.info("All tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 