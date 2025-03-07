# Stella Workflow Core Examples

This directory contains production-ready examples of how to use the Stella Workflow Core library in real-world scenarios.

## Data Processing Pipeline

The `data_processing_pipeline.py` example demonstrates a complete data processing pipeline using Stella Workflow Core. The pipeline consists of:

1. **Data Collector**: Fetches data from a source (simulated in this example)
2. **Data Transformer**: Processes and enriches the data (adds tax calculations and timestamps)
3. **Data Validator**: Validates the transformed data against business rules
4. **Data Storage**: Stores the validated data (writes to JSON files in this example)

### Prerequisites

- Python 3.8 or higher
- Redis server (local or remote)
- Stella Workflow Core library

### Configuration

The example uses environment variables for configuration. You can set these in a `.env` file in the same directory:

```
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_USERNAME=your_username  # Optional
REDIS_PASSWORD=your_password  # Optional
REDIS_SSL=false
```

### Running the Example

To run the data processing pipeline example:

```bash
cd examples
python data_processing_pipeline.py
```

### Output

The example will:

1. Create a unique topic for the pipeline
2. Set up the four agents (collector, transformer, validator, storage)
3. Run the pipeline
4. Write valid records to a file named `valid_records_YYYYMMDD_HHMMSS.json`
5. Write invalid records (if any) to a file named `invalid_records_YYYYMMDD_HHMMSS.json`
6. Log the pipeline statistics
7. Clean up resources

### Logs

The example logs to both the console and a file named `data_pipeline.log`. You can check this file for detailed information about the pipeline execution.

### Extending the Example

You can extend this example for your own use cases:

- **Data Collector**: Modify to fetch data from your own data sources (APIs, databases, files, etc.)
- **Data Transformer**: Add your own data transformation logic
- **Data Validator**: Customize validation rules based on your business requirements
- **Data Storage**: Change to store data in your preferred storage system (database, cloud storage, etc.)

## Best Practices Demonstrated

This example demonstrates several best practices for using Stella Workflow Core in production:

1. **Proper Error Handling**: Try/except blocks to catch and log errors
2. **Resource Cleanup**: Properly closing connections in finally blocks
3. **State Management**: Using the built-in state management to track progress
4. **Logging**: Comprehensive logging for monitoring and debugging
5. **Configuration**: Using environment variables for configuration
6. **Timeout Handling**: Setting timeouts to prevent infinite waiting
7. **Pipeline Statistics**: Collecting and reporting pipeline statistics 