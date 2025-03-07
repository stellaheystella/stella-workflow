#!/usr/bin/env python3
"""
State and Memory Management Example for Stella Workflow

This example demonstrates a production-ready data processing pipeline that effectively
uses state and memory management in Stella Workflow. The pipeline consists of:

1. Data Collector: Simulates collecting data from multiple sources
2. Data Processor: Processes and transforms the collected data
3. Data Analyzer: Analyzes the processed data and generates insights
4. Alert Manager: Monitors the analysis results and generates alerts when needed

Each agent maintains its state and uses memory to track processing history and metrics.

Usage:
    python state_memory_pipeline.py

Environment Variables:
    REDIS_HOST: Redis host (default: localhost)
    REDIS_PORT: Redis port (default: 6379)
    REDIS_USERNAME: Redis username (optional)
    REDIS_PASSWORD: Redis password (optional)
    REDIS_SSL: Whether to use SSL (default: false)
    LOG_LEVEL: Logging level (default: INFO)
    MAX_ITERATIONS: Number of iterations to run (default: 5)
    USE_FAKE_REDIS: Use fake Redis for testing (default: false)
"""

import asyncio
import logging
import uuid
import json
import random
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Import Stella Workflow components
from stella_workflow.workflow import stella_agent
from stella_workflow.brokers import RedisBroker

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("state_memory_pipeline.log")
    ]
)
logger = logging.getLogger("state_memory_pipeline")

# Global variables to track execution
execution_complete = asyncio.Event()
max_iterations = int(os.getenv("MAX_ITERATIONS", "5"))
current_iteration = 0
output_filename = None

# Simulated data sources
DATA_SOURCES = {
    "temperature_sensor": {
        "min": float(os.getenv("TEMPERATURE_MIN", "15.0")),
        "max": float(os.getenv("TEMPERATURE_MAX", "35.0")),
        "unit": "celsius",
        "anomaly_threshold": float(os.getenv("TEMPERATURE_THRESHOLD", "30.0"))
    },
    "humidity_sensor": {
        "min": float(os.getenv("HUMIDITY_MIN", "30.0")),
        "max": float(os.getenv("HUMIDITY_MAX", "80.0")),
        "unit": "percent",
        "anomaly_threshold": float(os.getenv("HUMIDITY_THRESHOLD", "70.0"))
    },
    "pressure_sensor": {
        "min": float(os.getenv("PRESSURE_MIN", "980.0")),
        "max": float(os.getenv("PRESSURE_MAX", "1030.0")),
        "unit": "hPa",
        "anomaly_threshold": float(os.getenv("PRESSURE_THRESHOLD", "1010.0"))
    }
}

def get_redis_config():
    """Get Redis configuration from environment variables"""
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "username": os.getenv("REDIS_USERNAME", ""),
        "password": os.getenv("REDIS_PASSWORD", ""),
        "db": 0,
        "ssl": os.getenv("REDIS_SSL", "false").lower() == "true",
        "ssl_cert_reqs": os.getenv("REDIS_SSL_CERT_REQS", "none"),
        "use_fake_redis": os.getenv("USE_FAKE_REDIS", "false").lower() == "true"
    }

def generate_sensor_data() -> Dict[str, Dict]:
    """Generate simulated sensor data with occasional anomalies"""
    timestamp = datetime.now().isoformat()
    data = {}
    
    # Chance of generating anomalous data
    anomaly_chance = float(os.getenv("ANOMALY_CHANCE", "0.1"))
    generate_anomaly = random.random() < anomaly_chance
    
    for source, config in DATA_SOURCES.items():
        if generate_anomaly and random.random() < 0.5:  # 50% chance per sensor if anomaly triggered
            # Generate anomalous value
            value = config["anomaly_threshold"] + random.uniform(5.0, 15.0)
        else:
            # Generate normal value
            value = random.uniform(config["min"], config["max"])
            
        data[source] = {
            "value": round(value, 2),
            "unit": config["unit"],
            "timestamp": timestamp
        }
    
    return data

async def setup_workflow(broker, topic: str):
    """Set up the workflow with all agents"""
    # Clear any existing agents
    stella_agent.clear_agents()
    
    # Define the data collector agent
    @stella_agent(name="data_collector", broker=broker, topic=topic)
    async def data_collector():
        """Collect data from multiple sources"""
        global current_iteration, max_iterations
        
        # Get current state
        state = await data_collector.get_state()
        collection_count = state.get("collection_count", 0) + 1
        
        # Generate sensor data
        sensor_data = generate_sensor_data()
        
        # Update state with collection metrics
        await data_collector.update_state(
            collection_count=collection_count,
            last_collection_time=datetime.now().isoformat(),
            sources=list(sensor_data.keys()),
            status="active"
        )
        
        # Store the raw data in memory for historical reference
        await data_collector.set_memory(f"raw_data_{collection_count}", sensor_data)
        
        # Log collection metrics
        logger.info(f"Data Collector: Collected data from {len(sensor_data)} sources (run {collection_count})")
        
        # Increment iteration counter
        current_iteration = collection_count
        if current_iteration >= max_iterations:
            logger.info(f"Reached maximum iterations ({max_iterations}), will stop after pipeline completes")
            # Set completion event after the last iteration is started
            # This is a fallback in case the alert manager doesn't set it
            if not execution_complete.is_set():
                # Use a delayed task to set the completion event
                # This gives time for the pipeline to process the last iteration
                asyncio.create_task(delayed_completion_signal(10))  # 10 second delay
        
        return {
            "sensor_data": sensor_data,
            "collection_id": str(uuid.uuid4()),
            "collection_count": collection_count,
            "timestamp": datetime.now().isoformat()
        }
    
    # Define the data processor agent
    @stella_agent(name="data_processor", broker=broker, topic=topic, depends_on=["data_collector"])
    async def data_processor(message):
        """Process and transform the collected data"""
        # Skip if message is not from our dependency
        source = message.get("source")
        if source != "data_collector":
            return None
        
        # Extract the collector data
        collector_data = message.get("dependency_messages", {}).get("data_collector", {}).get("data", {})
        if not collector_data:
            logger.warning("Data Processor: No collector data found in message")
            return None
        
        # Get the sensor data
        sensor_data = collector_data.get("sensor_data", {})
        collection_id = collector_data.get("collection_id")
        collection_count = collector_data.get("collection_count", 0)
        
        # Get current state
        state = await data_processor.get_state()
        processed_count = state.get("processed_count", 0) + 1
        
        # Process the data
        processed_data = {}
        processing_start = datetime.now()
        
        for source, data in sensor_data.items():
            # Normalize the data based on min/max values
            source_config = DATA_SOURCES.get(source, {})
            min_val = source_config.get("min", 0)
            max_val = source_config.get("max", 100)
            
            # Simple normalization to 0-1 range
            normalized_value = (data["value"] - min_val) / (max_val - min_val) if max_val > min_val else 0
            
            # Store processed data
            processed_data[source] = {
                "raw_value": data["value"],
                "normalized_value": normalized_value,
                "unit": source_config.get("unit", ""),
                "timestamp": data["timestamp"]
            }
        
        # Simulate processing time
        await asyncio.sleep(0.1)
        processing_time = (datetime.now() - processing_start).total_seconds()
        
        # Update state with processing metrics
        await data_processor.update_state(
            processed_count=processed_count,
            last_processed_time=datetime.now().isoformat(),
            average_processing_time=((state.get("average_processing_time", 0) * (processed_count - 1)) + processing_time) / processed_count,
            status="active"
        )
        
        # Store the processed data in memory
        await data_processor.set_memory(f"processed_data_{collection_count}", processed_data)
        
        logger.info(f"Data Processor: Processed data from {len(processed_data)} sources (run {collection_count})")
        
        return {
            "processed_data": processed_data,
            "collection_id": collection_id,
            "collection_count": collection_count,
            "processing_time": processing_time,
            "timestamp": datetime.now().isoformat()
        }
    
    # Define the data analyzer agent
    @stella_agent(name="data_analyzer", broker=broker, topic=topic, depends_on=["data_processor"])
    async def data_analyzer(message):
        """Analyze the processed data and generate insights"""
        # Skip if message is not from our dependency
        source = message.get("source")
        if source != "data_processor":
            return None
        
        # Extract the processor data
        processor_data = message.get("dependency_messages", {}).get("data_processor", {}).get("data", {})
        if not processor_data:
            logger.warning("Data Analyzer: No processor data found in message")
            return None
        
        # Get the processed data
        processed_data = processor_data.get("processed_data", {})
        collection_id = processor_data.get("collection_id")
        collection_count = processor_data.get("collection_count", 0)
        
        # Get current state
        state = await data_analyzer.get_state()
        analysis_count = state.get("analysis_count", 0) + 1
        
        # Analyze the data
        analysis_results = {}
        anomalies = []
        
        for source, data in processed_data.items():
            raw_value = data["raw_value"]
            source_config = DATA_SOURCES.get(source, {})
            anomaly_threshold = source_config.get("anomaly_threshold")
            
            # Check for anomalies
            is_anomaly = False
            if anomaly_threshold:
                if source in ["temperature_sensor", "humidity_sensor"] and raw_value > anomaly_threshold:
                    is_anomaly = True
                elif source == "pressure_sensor" and raw_value < anomaly_threshold:
                    is_anomaly = True
            
            # Store analysis result
            analysis_results[source] = {
                "raw_value": raw_value,
                "normalized_value": data["normalized_value"],
                "is_anomaly": is_anomaly,
                "timestamp": data["timestamp"]
            }
            
            if is_anomaly:
                anomalies.append({
                    "source": source,
                    "value": raw_value,
                    "threshold": anomaly_threshold,
                    "timestamp": data["timestamp"]
                })
        
        # Update state with analysis metrics
        await data_analyzer.update_state(
            analysis_count=analysis_count,
            last_analysis_time=datetime.now().isoformat(),
            anomaly_count=state.get("anomaly_count", 0) + len(anomalies),
            status="active"
        )
        
        # Store the analysis results in memory
        await data_analyzer.set_memory(f"analysis_results_{collection_count}", analysis_results)
        
        # Log analysis metrics
        logger.info(f"Data Analyzer: Analyzed data from {len(analysis_results)} sources, found {len(anomalies)} anomalies (run {collection_count})")
        
        return {
            "analysis_results": analysis_results,
            "anomalies": anomalies,
            "collection_id": collection_id,
            "collection_count": collection_count,
            "timestamp": datetime.now().isoformat()
        }
    
    # Define the alert manager agent
    @stella_agent(name="alert_manager", broker=broker, topic=topic, depends_on=["data_analyzer"])
    async def alert_manager(message):
        """Monitor analysis results and generate alerts when needed"""
        global current_iteration, max_iterations, output_filename
        
        # Skip if message is not from our dependency
        source = message.get("source")
        if source != "data_analyzer":
            return None
        
        # Extract the analyzer data
        analyzer_data = message.get("dependency_messages", {}).get("data_analyzer", {}).get("data", {})
        if not analyzer_data:
            logger.warning("Alert Manager: No analyzer data found in message")
            return None
        
        # Get the analysis results and anomalies
        analysis_results = analyzer_data.get("analysis_results", {})
        anomalies = analyzer_data.get("anomalies", [])
        collection_count = analyzer_data.get("collection_count", 0)
        
        # Get current state
        state = await alert_manager.get_state()
        alert_count = state.get("alert_count", 0)
        
        # Generate alerts for anomalies
        alerts = []
        for anomaly in anomalies:
            alert = {
                "source": anomaly["source"],
                "value": anomaly["value"],
                "threshold": anomaly["threshold"],
                "severity": "high" if abs(anomaly["value"] - anomaly["threshold"]) > 10 else "medium",
                "message": f"Anomaly detected in {anomaly['source']}: {anomaly['value']} exceeds threshold {anomaly['threshold']}",
                "timestamp": datetime.now().isoformat()
            }
            alerts.append(alert)
        
        # Update alert count
        alert_count += len(alerts)
        
        # Update state with alert metrics
        await alert_manager.update_state(
            alert_count=alert_count,
            last_alert_time=datetime.now().isoformat() if alerts else state.get("last_alert_time"),
            status="active"
        )
        
        # Store the alerts in memory
        if alerts:
            await alert_manager.set_memory(f"alerts_{collection_count}", alerts)
        
        # Log alert metrics
        if alerts:
            logger.info(f"Alert Manager: Generated {len(alerts)} alerts (run {collection_count})")
        else:
            logger.info(f"Alert Manager: No alerts generated (run {collection_count})")
        
        # If this is the last iteration, save the output to a file
        global current_iteration
        if current_iteration >= max_iterations:
            # Create output with all relevant information
            output = {
                "timestamp": datetime.now().isoformat(),
                "total_alerts": alert_count,
                "state": await alert_manager.get_state(),
                "latest_alerts": alerts if alerts else []
            }
            
            # Save to file
            output_filename = f"alert_manager_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_filename, 'w') as f:
                json.dump(output, f, indent=2)
            
            logger.info(f"Saved alert manager output to {output_filename}")
            
            # Set completion event
            logger.info(f"Completed {max_iterations} iterations, setting completion event")
            execution_complete.set()
        
        # Check if we need to set completion event based on iteration count
        # This is a fallback in case the above condition doesn't trigger
        if current_iteration >= max_iterations:
            if not execution_complete.is_set():
                logger.info(f"Reached max iterations ({max_iterations}), setting completion event")
                execution_complete.set()
        
        return {
            "alerts": alerts if alerts else [],
            "alert_count": len(alerts),
            "total_alerts": alert_count,
            "collection_count": collection_count,
            "timestamp": datetime.now().isoformat()
        }

async def run_workflow():
    """Run the workflow for a specified number of iterations"""
    global max_iterations, output_filename
    
    # Generate a unique topic for this run
    workflow_topic = f"state_memory_{uuid.uuid4().hex[:8]}"
    
    # Create broker
    broker_config = get_redis_config()
    broker = RedisBroker(broker_config)
    
    # Connect to broker
    await broker.connect()
    
    try:
        # Setup workflow
        await setup_workflow(broker, workflow_topic)
        
        # Start workflow
        logger.info(f"Starting workflow with topic '{workflow_topic}' for {max_iterations} iterations")
        await stella_agent.start_workflow()
        
        # Trigger the data collector to start the workflow
        data_collector_agent = stella_agent.get_agents().get("data_collector", {}).get("handler")
        if data_collector_agent:
            # Start the first iteration
            await data_collector_agent()
            
            # Schedule remaining iterations with delays
            for i in range(1, max_iterations):
                # Schedule with increasing delays to avoid message overlap
                asyncio.create_task(schedule_iteration(data_collector_agent, i * 2))  # 2 second intervals
        
        # Wait for completion with timeout
        logger.info("Waiting for workflow completion...")
        try:
            # Wait for completion with a timeout (max_iterations * 5 seconds + 10 seconds buffer)
            timeout = max_iterations * 5 + 10
            logger.info(f"Setting timeout of {timeout} seconds")
            await asyncio.wait_for(execution_complete.wait(), timeout=timeout)
            logger.info("Execution complete event received")
        except asyncio.TimeoutError:
            logger.warning(f"Workflow did not complete within {timeout} seconds, forcing completion")
            # Force completion
            execution_complete.set()
        
        # Get final state from all agents
        agents = stella_agent.get_agents()
        
        logger.info("\n--- Final Agent States ---")
        for agent_name, agent_info in agents.items():
            state = await agent_info["handler"].get_state()
            logger.info(f"{agent_name}: {json.dumps(state, indent=2)}")
        
        logger.info("Workflow completed successfully")
        return output_filename
    
    finally:
        # Stop workflow and clean up
        await stella_agent.stop_workflow()
        await broker.close()

async def schedule_iteration(data_collector_agent, delay):
    """Schedule a data collection iteration with a delay"""
    await asyncio.sleep(delay)
    await data_collector_agent()

async def delayed_completion_signal(delay):
    """Set the completion event after a delay"""
    await asyncio.sleep(delay)
    if not execution_complete.is_set():
        logger.info(f"Setting delayed completion signal after {delay} seconds")
        execution_complete.set()

async def main():
    """Main entry point"""
    try:
        output_file = await run_workflow()
        logger.info(f"Workflow execution complete. Output saved to {output_file}")
    except Exception as e:
        logger.exception(f"Error in workflow: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Workflow interrupted by user")
    except Exception as e:
        logger.exception(f"Error in workflow: {str(e)}")
        sys.exit(1) 