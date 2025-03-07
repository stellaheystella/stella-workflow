# Event Aggregation System

This example demonstrates a production-ready event aggregation system using Stella Workflow Core. It showcases how to set up a workflow with multiple independent producers feeding into a single consumer.

## Overview

The system consists of:

1. **Multiple Independent Event Producers**:
   - **Metrics Producer**: Collects system metrics (CPU, memory, disk usage, etc.)
   - **Logs Producer**: Collects application log events
   - **Alerts Producer**: Generates system and application alerts

2. **Event Aggregator**: Combines data from all producers into a single aggregated event

3. **Notification System**: Processes the aggregated events and sends notifications when needed

## Use Cases

This pattern is useful for:
- Monitoring systems that collect data from multiple sources
- Event-driven architectures that need to combine events from different systems
- Data pipelines that aggregate information from multiple sources
- Real-time dashboards that display data from various systems

## Prerequisites

- Python 3.8 or higher
- Redis server (local or remote)
- Stella Workflow Core library

## Configuration

The example uses environment variables for configuration. You can set these in a `.env` file in the same directory:

```
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_USERNAME=your_username  # Optional
REDIS_PASSWORD=your_password  # Optional
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none

# Logging Configuration
LOG_LEVEL=INFO

# Workflow Configuration
AGGREGATION_TIMEOUT=30  # seconds
```

## Running the Example

To run the event aggregation system:

```bash
cd examples/multiple_producers
python event_aggregation.py
```

## Output

The example will:

1. Create a unique topic for the workflow
2. Set up the five agents (metrics producer, logs producer, alerts producer, event aggregator, notification agent)
3. Run the workflow
4. If notifications are generated, write them to a file named `notifications_YYYYMMDD_HHMMSS.json`
5. Log the workflow statistics
6. Clean up resources

### Example Output

When running the example, you'll see logs similar to:

```
2025-03-05 02:42:38,000 - event_aggregation - INFO - Setting up event aggregation workflow with topic: event_aggregation_1a6bc76c
2025-03-05 02:42:40,927 - event_aggregation - INFO - Metrics producer: Collecting system metrics
2025-03-05 02:42:40,886 - event_aggregation - INFO - Logs producer: Collecting application logs
2025-03-05 02:42:40,885 - event_aggregation - INFO - Alerts producer: Checking for alerts
2025-03-05 02:42:41,535 - event_aggregation - INFO - Alerts producer: Generated 2 alerts
2025-03-05 02:42:41,536 - event_aggregation - INFO - Logs producer: Collected 1 log events
2025-03-05 02:42:41,602 - event_aggregation - INFO - Metrics producer: Collected system metrics with CPU usage 17.67%
2025-03-05 02:42:43,046 - event_aggregation - INFO - Event aggregator: Aggregating events from all producers
2025-03-05 02:42:43,694 - event_aggregation - INFO - Event aggregator: Aggregated events with 1 logs and 2 alerts
2025-03-05 02:42:44,995 - event_aggregation - INFO - Notification agent: Processing aggregated events
2025-03-05 02:42:44,996 - event_aggregation - INFO - Notification agent: Sending 2 notifications
2025-03-05 02:42:44,999 - event_aggregation - INFO - Notification agent: Saved notifications to notifications_20250305_024244.json
2025-03-05 02:42:45,959 - event_aggregation - INFO - Event aggregation workflow completed successfully
```

If notifications are generated, they will be saved to a JSON file with content similar to:

```json
[
  {
    "type": "system",
    "severity": "high",
    "message": "High memory usage detected: 55.46%",
    "timestamp": "2025-03-05T02:42:44.996080"
  },
  {
    "type": "alert",
    "severity": "critical",
    "message": "Alert: Network latency high",
    "timestamp": "2025-03-05T02:42:44.996094"
  }
]
```

## Logs

The example logs to both the console and a file named `event_aggregation.log`. You can check this file for detailed information about the workflow execution.

## Extending the Example

You can extend this example for your own use cases:

- **Metrics Producer**: Modify to collect real system metrics using libraries like `psutil`
- **Logs Producer**: Connect to actual log sources like log files, syslog, or logging services
- **Alerts Producer**: Integrate with real monitoring systems or alert services
- **Event Aggregator**: Customize the aggregation logic based on your specific needs
- **Notification Agent**: Connect to actual notification channels like email, SMS, Slack, etc.

## Key Features Demonstrated

This example demonstrates several key features of Stella Workflow Core:

1. **Multiple Independent Producers**: Shows how to set up multiple entry point agents that run independently
2. **Dependency Management**: The event aggregator depends on all producers, ensuring it receives data from each
3. **Message Filtering**: Each agent filters messages to only process those from relevant sources
4. **State Management**: Each agent maintains its own state to track progress and statistics
5. **Timeout Handling**: The workflow includes a configurable timeout to prevent infinite waiting
6. **Error Handling**: Comprehensive error handling with try/except blocks and logging
7. **Resource Cleanup**: Properly closing connections in finally blocks

## Production Considerations

When adapting this example for production use, consider:

1. **Scaling**: For high-volume event processing, you might need to scale horizontally
2. **Persistence**: Consider persisting state to a database for recovery after restarts
3. **Monitoring**: Add monitoring for the workflow itself
4. **Security**: Secure Redis connections and any external APIs
5. **Rate Limiting**: Add rate limiting for notification delivery
6. **Retry Logic**: Add retry logic for failed operations 