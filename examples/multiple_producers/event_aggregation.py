#!/usr/bin/env python

"""
Event Aggregation System - Production Example

This example demonstrates a production-ready event aggregation system using Stella Workflow Core.
The system consists of:
1. Multiple independent event producers (metrics, logs, alerts)
2. A central event aggregator that combines data from all producers
3. A notification system that processes the aggregated events

This pattern is useful for:
- Monitoring systems that collect data from multiple sources
- Event-driven architectures that need to combine events from different systems
- Data pipelines that aggregate information from multiple sources

Usage:
    python event_aggregation.py

Environment Variables:
    REDIS_HOST: Redis host (default: localhost)
    REDIS_PORT: Redis port (default: 6379)
    REDIS_USERNAME: Redis username (optional)
    REDIS_PASSWORD: Redis password (optional)
    REDIS_SSL: Whether to use SSL (default: false)
    LOG_LEVEL: Logging level (default: INFO)
    AGGREGATION_TIMEOUT: Timeout in seconds (default: 30)
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
import random
from dotenv import load_dotenv

# Add parent directory to path to import stella_workflow
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stella_workflow.workflow import stella_agent

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("event_aggregation.log")
    ]
)
logger = logging.getLogger("event_aggregation")

# Global variables
workflow_topic = f"event_aggregation_{uuid.uuid4().hex[:8]}"
workflow_complete = False

def get_redis_config():
    """Get Redis configuration from environment variables."""
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", 6379)),
        "username": os.getenv("REDIS_USERNAME", ""),
        "password": os.getenv("REDIS_PASSWORD", ""),
        "ssl": os.getenv("REDIS_SSL", "false").lower() == "true",
        "ssl_cert_reqs": os.getenv("REDIS_SSL_CERT_REQS", "none"),
    }

async def setup_workflow():
    """Set up the event aggregation workflow."""
    from stella_workflow.brokers import BrokerFactory
    
    # Create Redis broker
    redis_config = get_redis_config()
    broker = BrokerFactory.create_broker('redis', redis_config)
    await broker.connect()
    
    logger.info(f"Setting up event aggregation workflow with topic: {workflow_topic}")
    
    # 1. Metrics Producer Agent
    @stella_agent(name="metrics_producer", broker=broker, topic=workflow_topic)
    async def metrics_producer():
        """Produce system metrics data."""
        logger.info("Metrics producer: Collecting system metrics")
        
        # In a real-world scenario, this would collect actual system metrics
        # For this example, we'll simulate metrics data
        metrics = {
            "cpu_usage": random.uniform(0, 100),
            "memory_usage": random.uniform(0, 100),
            "disk_usage": random.uniform(0, 100),
            "network_traffic": random.uniform(0, 1000),
            "active_connections": random.randint(1, 100),
            "collection_time": datetime.now().isoformat()
        }
        
        # Update state to track metrics collection
        metrics_collected = await metrics_producer.get_state_value("metrics_collected", 0)
        await metrics_producer.update_state(
            metrics_collected=metrics_collected + 1,
            last_collection_time=datetime.now().isoformat()
        )
        
        logger.info(f"Metrics producer: Collected system metrics with CPU usage {metrics['cpu_usage']:.2f}%")
        return metrics
    
    # 2. Logs Producer Agent
    @stella_agent(name="logs_producer", broker=broker, topic=workflow_topic)
    async def logs_producer():
        """Produce application log events."""
        logger.info("Logs producer: Collecting application logs")
        
        # In a real-world scenario, this would collect actual application logs
        # For this example, we'll simulate log data
        log_levels = ["INFO", "WARNING", "ERROR", "DEBUG"]
        services = ["api", "database", "auth", "frontend", "backend"]
        
        logs = {
            "events": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "level": random.choice(log_levels),
                    "service": random.choice(services),
                    "message": f"Sample log message {uuid.uuid4().hex[:8]}"
                }
                for _ in range(random.randint(1, 5))  # Generate 1-5 log events
            ],
            "collection_time": datetime.now().isoformat()
        }
        
        # Update state to track logs collection
        logs_collected = await logs_producer.get_state_value("logs_collected", 0)
        await logs_producer.update_state(
            logs_collected=logs_collected + len(logs["events"]),
            last_collection_time=datetime.now().isoformat()
        )
        
        logger.info(f"Logs producer: Collected {len(logs['events'])} log events")
        return logs
    
    # 3. Alerts Producer Agent
    @stella_agent(name="alerts_producer", broker=broker, topic=workflow_topic)
    async def alerts_producer():
        """Produce system and application alerts."""
        logger.info("Alerts producer: Checking for alerts")
        
        # In a real-world scenario, this would check for actual system alerts
        # For this example, we'll simulate alert data
        alert_types = ["system", "application", "security", "performance"]
        alert_severities = ["low", "medium", "high", "critical"]
        
        # Randomly decide if we have alerts (70% chance of no alerts)
        has_alerts = random.random() > 0.3
        
        alerts = {
            "alerts": [],
            "collection_time": datetime.now().isoformat()
        }
        
        if has_alerts:
            num_alerts = random.randint(1, 3)  # Generate 1-3 alerts
            alerts["alerts"] = [
                {
                    "id": f"alert-{uuid.uuid4().hex[:8]}",
                    "type": random.choice(alert_types),
                    "severity": random.choice(alert_severities),
                    "message": f"Alert: {random.choice(['High CPU usage', 'Memory leak detected', 'Disk space low', 'Network latency high'])}",
                    "timestamp": datetime.now().isoformat()
                }
                for _ in range(num_alerts)
            ]
        
        # Update state to track alerts collection
        alerts_collected = await alerts_producer.get_state_value("alerts_collected", 0)
        await alerts_producer.update_state(
            alerts_collected=alerts_collected + len(alerts["alerts"]),
            last_collection_time=datetime.now().isoformat()
        )
        
        if alerts["alerts"]:
            logger.info(f"Alerts producer: Generated {len(alerts['alerts'])} alerts")
        else:
            logger.info("Alerts producer: No alerts generated")
            
        return alerts
    
    # 4. Event Aggregator Agent
    @stella_agent(name="event_aggregator", broker=broker, topic=workflow_topic, 
                 depends_on=["metrics_producer", "logs_producer", "alerts_producer"])
    async def event_aggregator(message):
        """Aggregate events from all producers."""
        logger.info("Event aggregator: Aggregating events from all producers")
        
        # Skip if message is not from one of our dependencies
        source = message.get("source")
        if source not in ["metrics_producer", "logs_producer", "alerts_producer"]:
            logger.debug(f"Event aggregator: Skipping message from {source} (not from our dependencies)")
            return None
        
        # Extract data from all producers
        dependency_messages = message.get("dependency_messages", {})
        
        metrics_data = dependency_messages.get("metrics_producer", {}).get("data", {})
        logs_data = dependency_messages.get("logs_producer", {}).get("data", {})
        alerts_data = dependency_messages.get("alerts_producer", {}).get("data", {})
        
        # Check if we have data from all producers
        if not all([metrics_data, logs_data, alerts_data]):
            logger.debug("Event aggregator: Missing data from some producers, waiting for more messages")
            return None
        
        # Aggregate the events
        aggregated_events = {
            "metrics": metrics_data,
            "logs": logs_data,
            "alerts": alerts_data,
            "aggregation_time": datetime.now().isoformat(),
            "summary": {
                "cpu_usage": metrics_data.get("cpu_usage", 0),
                "memory_usage": metrics_data.get("memory_usage", 0),
                "log_count": len(logs_data.get("events", [])),
                "alert_count": len(alerts_data.get("alerts", [])),
                "has_critical_alerts": any(alert.get("severity") == "critical" 
                                          for alert in alerts_data.get("alerts", []))
            }
        }
        
        # Update state to track aggregation
        events_aggregated = await event_aggregator.get_state_value("events_aggregated", 0)
        await event_aggregator.update_state(
            events_aggregated=events_aggregated + 1,
            last_aggregation_time=datetime.now().isoformat()
        )
        
        logger.info(f"Event aggregator: Aggregated events with {len(logs_data.get('events', []))} logs and {len(alerts_data.get('alerts', []))} alerts")
        return aggregated_events
    
    # 5. Notification Agent
    @stella_agent(name="notification_agent", broker=broker, topic=workflow_topic, 
                 depends_on=["event_aggregator"])
    async def notification_agent(message):
        """Process aggregated events and send notifications if needed."""
        logger.info("Notification agent: Processing aggregated events")
        
        # Skip if message is not from event_aggregator
        source = message.get("source")
        if source != "event_aggregator":
            logger.debug(f"Notification agent: Skipping message from {source} (not from event_aggregator)")
            return None
        
        # Extract the aggregated events
        aggregated_events = message.get("dependency_messages", {}).get("event_aggregator", {}).get("data", {})
        
        if not aggregated_events:
            logger.warning("Notification agent: No aggregated events found in message")
            return None
        
        # Process the aggregated events
        summary = aggregated_events.get("summary", {})
        alerts = aggregated_events.get("alerts", {}).get("alerts", [])
        
        # Determine if notifications are needed
        notifications = []
        
        # Check CPU usage threshold
        if summary.get("cpu_usage", 0) > 50:
            notifications.append({
                "type": "system",
                "severity": "high",
                "message": f"High CPU usage detected: {summary.get('cpu_usage', 0):.2f}%",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check memory usage threshold
        if summary.get("memory_usage", 0) > 50:
            notifications.append({
                "type": "system",
                "severity": "high",
                "message": f"High memory usage detected: {summary.get('memory_usage', 0):.2f}%",
                "timestamp": datetime.now().isoformat()
            })
        
        # Add notifications for critical alerts
        for alert in alerts:
            if alert.get("severity") in ["high", "critical"]:
                notifications.append({
                    "type": "alert",
                    "severity": alert.get("severity"),
                    "message": alert.get("message"),
                    "timestamp": datetime.now().isoformat()
                })
        
        # In a real-world scenario, this would send actual notifications
        # For this example, we'll just log them and save to a file
        if notifications:
            logger.info(f"Notification agent: Sending {len(notifications)} notifications")
            
            # Save notifications to file
            notification_file = f"notifications_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(notification_file, "w") as f:
                json.dump(notifications, f, indent=2)
                
            logger.info(f"Notification agent: Saved notifications to {notification_file}")
        else:
            logger.info("Notification agent: No notifications needed")
        
        # Create the result
        result = {
            "notifications": notifications,
            "notification_count": len(notifications),
            "processed_time": datetime.now().isoformat()
        }
        
        # Update state to track notifications
        notifications_sent = await notification_agent.get_state_value("notifications_sent", 0)
        last_notification_time = datetime.now().isoformat() if notifications else None
        await notification_agent.update_state(
            notifications_sent=notifications_sent + len(notifications),
            last_notification_time=last_notification_time
        )
        
        # Signal that the workflow is complete
        global workflow_complete
        workflow_complete = True
        
        return result
    
    return broker

async def run_workflow():
    """Run the event aggregation workflow."""
    global workflow_complete
    
    # Set up the workflow
    broker = await setup_workflow()
    
    try:
        # Start the workflow
        logger.info("Starting event aggregation workflow")
        await stella_agent.start_workflow()
        
        # Wait for the workflow to complete
        timeout = int(os.getenv("AGGREGATION_TIMEOUT", 30))  # seconds
        for _ in range(timeout):
            if workflow_complete:
                break
            await asyncio.sleep(1)
        
        if workflow_complete:
            logger.info("Event aggregation workflow completed successfully")
            
            # Get the registered agents
            agents = stella_agent.get_agents()
            
            # Print workflow statistics
            logger.info("Workflow Statistics:")
            
            metrics_state = await agents["metrics_producer"]["handler"].get_state()
            logger.info(f"Metrics Producer: {metrics_state.get('metrics_collected', 0)} metrics collected")
            
            logs_state = await agents["logs_producer"]["handler"].get_state()
            logger.info(f"Logs Producer: {logs_state.get('logs_collected', 0)} logs collected")
            
            alerts_state = await agents["alerts_producer"]["handler"].get_state()
            logger.info(f"Alerts Producer: {alerts_state.get('alerts_collected', 0)} alerts collected")
            
            aggregator_state = await agents["event_aggregator"]["handler"].get_state()
            logger.info(f"Event Aggregator: {aggregator_state.get('events_aggregated', 0)} events aggregated")
            
            notification_state = await agents["notification_agent"]["handler"].get_state()
            logger.info(f"Notification Agent: {notification_state.get('notifications_sent', 0)} notifications sent")
        else:
            logger.error(f"Event aggregation workflow did not complete within {timeout} seconds")
    
    except Exception as e:
        logger.exception(f"Error running workflow: {str(e)}")
    
    finally:
        # Stop the workflow
        await stella_agent.stop_workflow()
        
        # Close the broker connection
        if broker:
            await broker.close()

def main():
    """Main entry point for the event aggregation system."""
    try:
        asyncio.run(run_workflow())
    except KeyboardInterrupt:
        logger.info("Workflow execution interrupted by user")
    except Exception as e:
        logger.exception(f"Unhandled exception: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 