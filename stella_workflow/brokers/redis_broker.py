import redis.asyncio as aioredis
import fakeredis.aioredis
import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List
from .base import MessageBroker
from ..utils import Colors

logger = logging.getLogger(__name__)

class RedisBroker(MessageBroker):
    def __init__(self, config: Dict):
        self.config = config
        self.client = None
        self._pubsub = None
        self._subscription_tasks = {}
        self._consumer_names = {}
        self._use_fake_redis = config.get('use_fake_redis', False)
        self._poll_interval = config.get('poll_interval', 1.0)  # Default 1 second poll interval

    async def connect(self) -> None:
        """Connect to Redis (real or fake)"""
        logger.info("Connecting to Redis...")
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                if self._use_fake_redis:
                    self.client = fakeredis.aioredis.FakeRedis(decode_responses=True)
                    self._pubsub = self.client.pubsub()
                    logger.info("Using in-memory Redis")
                else:
                    # Use rediss:// for SSL connections
                    protocol = "rediss://" if self.config.get('ssl', False) else "redis://"
                    
                    # Prepare connection kwargs
                    connection_kwargs = {
                        'username': self.config.get('username'),
                        'password': self.config.get('password'),
                        'decode_responses': True,
                        'socket_keepalive': True,
                        'retry_on_timeout': True,
                    }
                    
                    # Add SSL configuration if enabled
                    if self.config.get('ssl', False):
                        connection_kwargs['ssl_cert_reqs'] = self.config.get('ssl_cert_reqs')
                    
                    self.client = await aioredis.Redis.from_url(
                        f"{protocol}{self.config.get('host', 'localhost')}:{self.config.get('port', 6379)}",
                        **connection_kwargs
                    )
                    self._pubsub = self.client.pubsub()
                await self.client.ping()
                logger.info("Successfully connected to Redis")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Connection attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

    async def _ensure_stream(self, topic: str) -> None:
        """Ensure stream exists"""
        stream_key = f"stream:{topic}"
        try:
            # Just try to read from stream, it will be created if doesn't exist
            await self.client.xinfo_stream(stream_key)
        except aioredis.ResponseError:
            # Stream doesn't exist, create it with a dummy message that we'll delete
            dummy_id = await self.client.xadd(stream_key, {'_': '_'})
            await self.client.xdel(stream_key, dummy_id)
        except Exception as e:
            logger.error(f"Error ensuring stream: {str(e)}")
            raise

    async def publish(self, topic: str, message: Dict, source: str = None) -> None:
        """Publish message to Redis Stream and notify subscribers"""
        if not self.client:
            await self.connect()
        
        # Ensure stream exists
        await self._ensure_stream(topic)
        
        # Generate unique message ID
        message_id = str(uuid.uuid4())
        
        # Create stream key and notification channel
        stream_key = f"stream:{topic}"
        notification_channel = f"notifications:{topic}"
        
        # Prepare message data
        # If message is already a dict with source and data fields, use it directly
        if isinstance(message, dict) and 'source' in message and 'data' in message:
            # Use the provided source if not explicitly specified
            if source is None:
                source = message['source']
            # Serialize the data part
            message_data = json.dumps(message['data'])
        else:
            # Normal case - serialize the entire message
            message_data = json.dumps(message)
        
        # Current timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Add message to stream
        await self.client.xadd(
            stream_key,
            {
                'id': message_id,
                'source': source,
                'data': message_data,
                'timestamp': timestamp
            }
        )
        
        # Send notification
        await self.client.publish(notification_channel, "new_message")
        
        logger.debug(f"Published message to {topic}: {{'id': '{message_id}', 'source': '{source}', 'data': '{message_data}', 'timestamp': '{timestamp}'}}")

    async def _subscription_handler(self, topic: str, callback, source_filter: List[str] = None):
        """Handle subscription to Redis Stream with Pub/Sub notifications"""
        if not self.client:
            await self.connect()
        
        # Ensure stream exists
        await self._ensure_stream(topic)
        
        # Create stream key and notification channel
        stream_key = f"stream:{topic}"
        notification_channel = f"notifications:{topic}"
        
        # Create PubSub connection
        pubsub = self.client.pubsub()
        await pubsub.subscribe(notification_channel)
        
        # Start with the earliest ID (get all messages)
        last_id = "0"
        
        logger.debug(f"Created subscription for topic: {topic}")
        logger.debug(f"Listening on stream key: {stream_key}")
        logger.debug(f"Listening on notification channel: {notification_channel}")
        
        # First, read any existing messages in the stream
        try:
            messages = await self.client.xread(
                streams={stream_key: last_id},
                count=10
            )
            
            logger.debug(f"Initial read from stream: {messages}")
            
            if messages:
                for stream_name, message_list in messages:
                    logger.debug(f"Processing initial messages from stream {stream_name}")
                    for message_id, data in message_list:
                        try:
                            logger.debug(f"Processing initial message {message_id}: {data}")
                            
                            # Convert bytes keys to strings if needed
                            processed_data = {}
                            for k, v in data.items():
                                if isinstance(k, bytes):
                                    k = k.decode('utf-8')
                                if isinstance(v, bytes):
                                    v = v.decode('utf-8')
                                processed_data[k] = v
                            
                            # Source filtering
                            if source_filter and processed_data.get('source') not in source_filter:
                                logger.debug(f"Skipping message from source {processed_data.get('source')} (not in filter: {source_filter})")
                                continue
                            
                            # Parse message
                            message = {
                                'id': processed_data.get('id'),
                                'source': processed_data.get('source'),
                                'data': json.loads(processed_data.get('data')),  # Deserialize the JSON data
                                'timestamp': processed_data.get('timestamp')
                            }
                            
                            logger.debug(f"Parsed initial message: {message}")
                            
                            # Process message
                            await callback(message)
                            
                            # Update last seen ID
                            last_id = message_id
                            logger.debug(f"Updated last_id to {last_id}")
                            
                        except Exception as e:
                            logger.error(f"Error processing initial message {message_id}: {str(e)}")
        except Exception as e:
            logger.error(f"Error reading initial messages: {str(e)}")
        
        try:
            while True:
                try:
                    # Wait for notification
                    message = await pubsub.get_message(timeout=1)
                    
                    if message:
                        logger.debug(f"Received notification: {message}")
                    
                    if message and message['type'] == 'message':
                        # Got notification, read from stream
                        logger.debug(f"Reading from stream {stream_key} with last_id {last_id}")
                        messages = await self.client.xread(
                            streams={stream_key: last_id},
                            count=10  # Read multiple messages if available
                        )
                        
                        logger.debug(f"Read messages from stream: {messages}")
                        
                        if messages:  # [[stream_name, [(message_id, data), ...]]]
                            for stream_name, message_list in messages:
                                logger.debug(f"Processing messages from stream {stream_name}")
                                for message_id, data in message_list:
                                    try:
                                        logger.debug(f"Processing message {message_id}: {data}")
                                        
                                        # Convert bytes keys to strings if needed
                                        processed_data = {}
                                        for k, v in data.items():
                                            if isinstance(k, bytes):
                                                k = k.decode('utf-8')
                                            if isinstance(v, bytes):
                                                v = v.decode('utf-8')
                                            processed_data[k] = v
                                        
                                        # Source filtering
                                        if source_filter and processed_data.get('source') not in source_filter:
                                            logger.debug(f"Skipping message from source {processed_data.get('source')} (not in filter: {source_filter})")
                                            continue
                                        
                                        # Parse message
                                        message = {
                                            'id': processed_data.get('id'),
                                            'source': processed_data.get('source'),
                                            'data': json.loads(processed_data.get('data')),  # Deserialize the JSON data
                                            'timestamp': processed_data.get('timestamp')
                                        }
                                        
                                        logger.debug(f"Parsed message: {message}")
                                        
                                        # Process message
                                        await callback(message)
                                        
                                        # Update last seen ID
                                        last_id = message_id
                                        logger.debug(f"Updated last_id to {last_id}")
                                        
                                    except Exception as e:
                                        logger.error(f"Error processing message {message_id}: {str(e)}")
                    
                except asyncio.CancelledError:
                    break
                except asyncio.TimeoutError:
                    # No notification, continue waiting
                    continue
                except Exception as e:
                    logger.error(f"Error in subscription handler: {str(e)}")
                    await asyncio.sleep(1)
                    
        finally:
            try:
                await pubsub.unsubscribe(notification_channel)
            except Exception as e:
                logger.error(f"Error cleaning up subscription: {str(e)}")

    async def subscribe(self, topic: str, callback, source_filter: List[str] = None) -> None:
        """Subscribe to topic using Redis Stream with Pub/Sub notifications"""
        if not self.client:
            await self.connect()
        
        # Create subscription handler task
        task = asyncio.create_task(
            self._subscription_handler(topic, callback, source_filter)
        )
        
        # Store task for cleanup
        self._subscription_tasks[topic] = task
        
        return task

    async def acknowledge(self, message_id: str) -> None:
        """No-op as we're not using consumer groups"""
        pass

    async def get_message(self, topic: str, source_filter: str = None) -> Any:
        """
        [FUTURE USE] Get a single message from a topic using BRPOP.
        
        Unlike subscribe() which continuously listens for messages, this method:
        - Blocks until a single message is available (up to timeout)
        - Removes and returns the message from the queue (destructive read)
        - Is ideal for work queue patterns where each message should be processed once
        - Allows multiple consumers to safely process messages without duplicates
        
        The subscribe() method is better for pub/sub scenarios where:
        - You want to continuously receive all messages
        - Multiple consumers need to receive the same messages
        - Messages don't need to be removed after processing
        """
        if not self.client:
            logger.debug("No Redis connection, connecting...")
            await self.connect()
        
        logger.debug(f"Waiting for message on topic {topic} with source filter: {source_filter}")
        # BRPOP blocks until message available or timeout
        # Returns tuple of (queue_name, message) or None if timeout
        message_data = await self.client.brpop(f"{topic}_queue", timeout=5)
        
        if message_data:
            # message_data[1] contains the actual message (message_data[0] is queue name)
            message = json.loads(message_data[1])
            logger.debug(f"Received message: {message}")
            
            # Apply source filtering if specified
            if source_filter and message['source'] != source_filter:
                logger.debug(f"Skipping message from source {message['source']} (filter: {source_filter})")
                return None
            
            logger.info(f"Successfully retrieved message from {message['source']}")
            return message['data']
        logger.debug("No message received (timeout)")
        return None 

    async def get_memory(self, namespace: str, key: str) -> Any:
        """Get a value from memory using Redis hash sets.
        
        Args:
            namespace (str): The namespace for the memory (e.g. agent name)
            key (str): The key to retrieve
            
        Returns:
            Any: The stored value
            
        Raises:
            KeyError: If the key doesn't exist in memory
            RuntimeError: If not connected to Redis
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        memory_key = f"memory:{namespace}"
        value = await self.client.hget(memory_key, key)
        
        if value is None:
            raise KeyError(f"Key '{key}' not found in namespace '{namespace}'")
            
        return json.loads(value)
        
    async def set_memory(self, namespace: str, key: str, value: Any) -> None:
        """Set a value in memory using Redis hash sets.
        
        Args:
            namespace (str): The namespace for the memory (e.g. agent name)
            key (str): The key to store
            value (Any): The value to store (must be JSON serializable)
            
        Raises:
            RuntimeError: If not connected to Redis
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        memory_key = f"memory:{namespace}"
        await self.client.hset(memory_key, key, json.dumps(value))
        
    async def close(self) -> None:
        """Close the Redis connection and clean up resources."""
        logger.debug("Closing Redis connection...")
        
        # Cancel all subscription tasks
        for topic, task in self._subscription_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error cancelling subscription task for {topic}: {str(e)}")
        
        self._subscription_tasks.clear()
        
        # Close pubsub connection if exists
        if self._pubsub:
            try:
                await self._pubsub.aclose()
            except Exception as e:
                logger.error(f"Error closing pubsub connection: {str(e)}")
        
        # Close Redis client
        if self.client:
            try:
                await self.client.aclose()
            except Exception as e:
                logger.error(f"Error closing Redis client: {str(e)}")
        
        self.client = None
        self._pubsub = None
        logger.debug("Redis connection closed") 