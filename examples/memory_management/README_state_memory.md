# State and Memory Management in Stella Workflow

This example demonstrates how to effectively use state and memory management in a Stella Workflow to build a production-ready data processing pipeline.

## Overview

The example implements a data processing pipeline with the following components:

1. **Data Collector**: Simulates collecting data from multiple sensors (temperature, humidity, pressure)
2. **Data Processor**: Processes and transforms the collected data (normalization)
3. **Data Analyzer**: Analyzes the processed data and detects anomalies
4. **Alert Manager**: Monitors analysis results and generates alerts for anomalies

Each agent maintains its state and uses memory to track processing history and metrics.

## Key Concepts Demonstrated

### State vs. Memory: What's the Difference?

In Stella Workflow, **state** and **memory** serve different but complementary purposes:

#### State
State is a special type of memory that:
- Stores lightweight operational metadata about an agent
- Contains only essential metrics and status information
- Is updated atomically with each processing cycle
- Is accessed via dedicated methods (`get_state()`, `update_state()`)
- Is stored under a special key called 'state' in the underlying memory system

State is ideal for:
- Tracking processing counts and timestamps
- Maintaining status flags and operational modes
- Storing cumulative metrics (totals, averages)
- Persisting configuration settings

#### Memory
Memory is a general-purpose key-value store that:
- Stores arbitrary data with custom keys
- Can hold large datasets and historical information
- Is accessed via direct methods (`get_memory()`, `set_memory()`)
- Allows for flexible organization with custom naming schemes

Memory is ideal for:
- Storing historical data (raw inputs, processed outputs)
- Maintaining large datasets that don't fit in state
- Creating relationships between different processing cycles
- Implementing caches and lookup tables

### State Management

Each agent maintains its own state that persists across message processing cycles:

- **Collection metrics**: Number of collections, timestamps, data sources
- **Processing metrics**: Number of processed messages, average processing time
- **Analysis metrics**: Number of analyses, anomaly counts
- **Alert metrics**: Number of alerts, last alert time

State is updated using the `update_state()` method:

```python
await agent.update_state(
    counter=counter + 1,
    last_processed_time=datetime.now().isoformat(),
    status="active"
)
```

### Memory Management

Agents store data in memory for historical reference and retrieval:

- **Raw data**: Original sensor readings
- **Processed data**: Transformed sensor data
- **Analysis results**: Anomaly detection results
- **Alerts**: Generated alerts for anomalies

Memory is managed using the `set_memory()` and `get_memory()` methods:

```python
# Store data in memory
await agent.set_memory(f"data_{collection_id}", data)

# Retrieve data from memory
stored_data = await agent.get_memory(f"data_{collection_id}")
```

### Why Both Are Needed

1. **Separation of Concerns**:
   - State focuses on agent metadata and operational status
   - Memory focuses on data storage and historical records

2. **Performance Optimization**:
   - State updates are optimized for frequent, small changes
   - Memory operations are optimized for larger data storage

3. **Conceptual Clarity**:
   - State represents "how the agent is doing"
   - Memory represents "what the agent knows or has seen"

4. **Implementation Patterns**:
   - State follows a consistent schema across processing cycles
   - Memory can use dynamic keys and varied data structures

### Message Flow

The example demonstrates a complete message flow with dependencies:

```
Data Collector → Data Processor → Data Analyzer → Alert Manager
```

Each agent depends on the output of the previous agent in the pipeline.

## Running the Example

### Prerequisites

- Python 3.8 or higher
- Redis server (or use the `USE_FAKE_REDIS=true` environment variable for testing)

### Installation

1. Install the Stella Workflow package and dependencies:

```bash
pip install -r requirements.txt
```

2. Configure the environment:

Copy the example environment file and modify as needed:

```bash
cp .env.example .env
```

Edit the `.env` file to configure Redis connection, logging, and workflow parameters.

### Usage

Run the example:

```bash
python state_memory_pipeline.py
```

### Environment Variables

The example uses the following environment variables (with defaults):

#### Redis Configuration
- `REDIS_HOST`: Redis host (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_USERNAME`: Redis username (optional)
- `REDIS_PASSWORD`: Redis password (optional)
- `REDIS_SSL`: Whether to use SSL (default: false)
- `REDIS_SSL_CERT_REQS`: SSL certificate requirements (default: none)
- `USE_FAKE_REDIS`: Use fake Redis for testing (default: false)

#### Logging Configuration
- `LOG_LEVEL`: Logging level (default: INFO)

#### Workflow Configuration
- `MAX_ITERATIONS`: Number of iterations to run (default: 5)
- `ANOMALY_CHANCE`: Probability of generating anomalous data (default: 0.1)

#### Data Sources Configuration
- `TEMPERATURE_MIN`: Minimum temperature value (default: 15.0)
- `TEMPERATURE_MAX`: Maximum temperature value (default: 35.0)
- `TEMPERATURE_THRESHOLD`: Anomaly threshold for temperature (default: 30.0)
- `HUMIDITY_MIN`: Minimum humidity value (default: 30.0)
- `HUMIDITY_MAX`: Maximum humidity value (default: 80.0)
- `HUMIDITY_THRESHOLD`: Anomaly threshold for humidity (default: 70.0)
- `PRESSURE_MIN`: Minimum pressure value (default: 980.0)
- `PRESSURE_MAX`: Maximum pressure value (default: 1030.0)
- `PRESSURE_THRESHOLD`: Anomaly threshold for pressure (default: 1010.0)

## Output Files

The example generates the following output files:

1. **Log File**: `state_memory_pipeline.log` - Contains detailed logs of the workflow execution
2. **Alert Manager Output**: `alert_manager_output_YYYYMMDD_HHMMSS.json` - Contains the final state and alerts from the alert manager

The Alert Manager output file is generated directly by the alert_manager agent when it processes the last iteration, demonstrating how agents can interact with external systems (in this case, the file system).

## Example Output

```
2024-05-01 12:00:00 - state_memory_pipeline - INFO - Starting workflow with topic 'state_memory_a1b2c3d4' for 5 iterations
2024-05-01 12:00:00 - state_memory_pipeline - INFO - Data Collector: Collected data from 3 sources (run 1)
2024-05-01 12:00:01 - state_memory_pipeline - INFO - Data Processor: Processed data from 3 sources (run 1)
2024-05-01 12:00:01 - state_memory_pipeline - INFO - Data Analyzer: Analyzed data from 3 sources, found 0 anomalies (run 1)
2024-05-01 12:00:01 - state_memory_pipeline - INFO - Alert Manager: No alerts generated (run 1)
...
2024-05-01 12:00:05 - state_memory_pipeline - INFO - Data Collector: Collected data from 3 sources (run 5)
2024-05-01 12:00:05 - state_memory_pipeline - INFO - Data Processor: Processed data from 3 sources (run 5)
2024-05-01 12:00:05 - state_memory_pipeline - INFO - Data Analyzer: Analyzed data from 3 sources, found 2 anomalies (run 5)
2024-05-01 12:00:05 - state_memory_pipeline - INFO - Alert Manager: Generated 2 alerts (run 5)
2024-05-01 12:00:05 - state_memory_pipeline - INFO - Saved alert manager output to alert_manager_output_20240501_120005.json
2024-05-01 12:00:05 - state_memory_pipeline - INFO - Completed 5 iterations, setting completion event

--- Final Agent States ---
data_collector: {
  "collection_count": 5,
  "last_collection_time": "2024-05-01T12:00:05.123456",
  "sources": ["temperature_sensor", "humidity_sensor", "pressure_sensor"],
  "status": "active"
}
data_processor: {
  "processed_count": 5,
  "last_processed_time": "2024-05-01T12:00:05.234567",
  "average_processing_time": 0.105,
  "status": "active"
}
data_analyzer: {
  "analysis_count": 5,
  "last_analysis_time": "2024-05-01T12:00:05.345678",
  "anomaly_count": 3,
  "status": "active"
}
alert_manager: {
  "alert_count": 3,
  "last_alert_time": "2024-05-01T12:00:05.456789",
  "status": "active"
}
```

## Example Alert Manager Output File

```json
{
  "timestamp": "2024-05-01T12:00:05.456789",
  "total_alerts": 3,
  "state": {
    "alert_count": 3,
    "last_alert_time": "2024-05-01T12:00:05.456789",
    "status": "active"
  },
  "latest_alerts": [
    {
      "source": "temperature_sensor",
      "value": 35.42,
      "threshold": 30.0,
      "severity": "medium",
      "message": "Anomaly detected in temperature_sensor: 35.42 exceeds threshold 30.0",
      "timestamp": "2024-05-01T12:00:05.456789"
    },
    {
      "source": "humidity_sensor",
      "value": 75.18,
      "threshold": 70.0,
      "severity": "medium",
      "message": "Anomaly detected in humidity_sensor: 75.18 exceeds threshold 70.0",
      "timestamp": "2024-05-01T12:00:05.456789"
    }
  ]
}
```

## Visualizing State and Memory

The example includes a visualization utility to help you understand the state and memory of the agents:

```bash
python visualize_state_memory.py --agent data_analyzer --memory --plot analysis_results
```

This will:
1. Connect to Redis
2. Display the state of the data_analyzer agent
3. Show the memory contents of the agent
4. Generate a plot of the analysis results

For more information on the visualization utility, run:

```bash
python visualize_state_memory.py --help
```

## Best Practices for State and Memory Management

1. **Keep state lightweight**: Store only essential metrics and status information in state.
2. **Use memory for historical data**: Store larger datasets in memory with unique keys.
3. **Handle state initialization**: Always check if state exists before accessing it.
4. **Use atomic updates**: Update state in a single operation to avoid race conditions.
5. **Clean up old data**: Implement a strategy to clean up old memory entries if needed.
6. **Error handling**: Always handle potential errors when accessing state or memory.

## Advanced Usage

### Retrieving Historical Data

```python
# Get all raw data from the last 10 collections
for i in range(collection_count - 10, collection_count + 1):
    try:
        historical_data = await agent.get_memory(f"raw_data_{i}")
        # Process historical data
    except KeyError:
        # Handle missing data
        pass
```

### Implementing State-Based Logic

```python
# Get current state
state = await agent.get_state()

# Implement different logic based on state
if state.get("anomaly_count", 0) > 10:
    # High anomaly count, take special action
    await agent.update_state(status="alert")
else:
    # Normal operation
    await agent.update_state(status="normal")
```

### Tracking Performance Metrics

```python
# Calculate and store performance metrics
processing_start = datetime.now()
result = process_data(data)
processing_time = (datetime.now() - processing_start).total_seconds()

# Update rolling average
state = await agent.get_state()
count = state.get("processed_count", 0) + 1
avg_time = state.get("avg_processing_time", 0)
new_avg = ((avg_time * (count - 1)) + processing_time) / count

# Update state with new metrics
await agent.update_state(
    processed_count=count,
    avg_processing_time=new_avg
)
``` 