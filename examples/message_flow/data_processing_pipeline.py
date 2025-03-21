#!/usr/bin/env python
"""
Data Processing Pipeline Example

This example demonstrates a production-ready data processing pipeline using Stella Workflow Core.
The pipeline consists of:
1. A data collector that fetches data from a source
2. A data transformer that processes and enriches the data
3. A data validator that validates the transformed data
4. A data storage agent that stores the validated data

Usage:
    python data_processing_pipeline.py

Environment Variables:
    REDIS_HOST: Redis host (default: localhost)
    REDIS_PORT: Redis port (default: 6379)
    REDIS_USERNAME: Redis username (optional)
    REDIS_PASSWORD: Redis password (optional)
    REDIS_SSL: Whether to use SSL (default: false)
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv

# Add the parent directory to the path so we can import stella_workflow
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stella_workflow.brokers import BrokerFactory
from stella_workflow.workflow import stella_agent

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data_pipeline.log")
    ]
)
logger = logging.getLogger("data_pipeline")

# Global variables
pipeline_topic = f"data_pipeline_{uuid.uuid4().hex[:8]}"
pipeline_complete = False

def get_redis_config() -> dict[str, Any]:
    """Get Redis configuration from environment variables"""
    ssl_cert_reqs = os.getenv('REDIS_SSL_CERT_REQS', 'none').lower()

    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", 6379)),
        "username": os.getenv("REDIS_USERNAME", ""),
        "password": os.getenv("REDIS_PASSWORD", ""),
        "ssl": os.getenv("REDIS_SSL", "false").lower() == "true",
        "ssl_cert_reqs": ssl_cert_reqs,
    }

async def setup_pipeline() -> None:
    """Set up the data processing pipeline"""
    global pipeline_topic

    # Create Redis broker
    redis_config = get_redis_config()
    broker = BrokerFactory.create_broker('redis', redis_config)
    await broker.connect()

    logger.info(f"Setting up data pipeline with topic: {pipeline_topic}")

    # Define the data collector agent
    @stella_agent(name="data_collector", broker=broker, topic=pipeline_topic)
    async def data_collector() -> dict[str, Any]:
        """Collect data from a source"""
        logger.info("Data collector: Starting data collection")

        # In a real-world scenario, this would fetch data from an external source
        # such as an API, database, or file
        sample_data = {
            "records": [
                {"id": 1, "name": "Product A", "price": 29.99, "category": "electronics"},
                {"id": 2, "name": "Product B", "price": 49.99, "category": "clothing"},
                {"id": 3, "name": "Product C", "price": 19.99, "category": "home"},
                # Invalid record (missing name)
                {"id": 4, "price": 19.99, "category": "home"}
            ],
            "source": "sample_database",
            "timestamp": datetime.now().isoformat()
        }

        # Update state to track this collection
        await data_collector.update_state(
            records_collected=len(sample_data["records"]),
            last_collection_time=datetime.now().isoformat(),
            status="completed"
        )

        logger.info(
            f"Data collector: Collected {len(sample_data['records'])} records"
        )
        return sample_data

    # Define the data transformer agent
    @stella_agent(
        name="data_transformer",
        broker=broker,
        topic=pipeline_topic,
        depends_on=["data_collector"]
    )
    async def data_transformer(message: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Transform and enrich the collected data"""
        logger.info("Data transformer: Starting data transformation")

        # Skip if message is not from data_collector
        source = message.get("source")
        if source != "data_collector":
            logger.debug(
                f"Data transformer: Skipping message from {source} "
                "(not from data_collector)"
            )
            return None

        # Extract the collected data
        collected_data = (
            message.get("dependency_messages", {})
            .get("data_collector", {})
            .get("data", {})
        )
        records = collected_data.get("records", [])

        # Transform the data
        transformed_records = []
        for record in records:
            # Apply transformations
            transformed_record = record.copy()

            # Add tax to price (10%)
            if "price" in record and isinstance(record["price"], (int, float)):
                transformed_record["price_with_tax"] = round(record["price"] * 1.1, 2)

            # Add processing timestamp
            transformed_record["processed_at"] = datetime.now().isoformat()

            # Add to transformed records
            transformed_records.append(transformed_record)

        transformed_data = {
            "records": transformed_records,
            "original_source": collected_data.get("source"),
            "original_timestamp": collected_data.get("timestamp"),
            "transformation_timestamp": datetime.now().isoformat()
        }

        # Get current state
        current_state = await data_transformer.get_state()
        records_processed = current_state.get("records_processed", 0) + len(records)

        # Update state to track this transformation
        await data_transformer.update_state(
            records_processed=records_processed,
            last_transformation_time=datetime.now().isoformat(),
            status="completed"
        )

        logger.info(f"Data transformer: Transformed {len(records)} records")
        return transformed_data

    # Define the data validator agent
    @stella_agent(
        name="data_validator",
        broker=broker,
        topic=pipeline_topic,
        depends_on=["data_transformer"]
    )
    async def data_validator(message: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Validate the transformed data"""
        logger.info("Data validator: Starting data validation")

        # Skip if message is not from data_transformer
        source = message.get("source")
        if source != "data_transformer":
            logger.debug(
                f"Data validator: Skipping message from {source} "
                "(not from data_transformer)"
            )
            return None

        # Extract the transformed data
        transformed_data = (
            message.get("dependency_messages", {})
            .get("data_transformer", {})
            .get("data", {})
        )
        records = transformed_data.get("records", [])

        # Validate the data
        valid_records = []
        invalid_records = []

        for record in records:
            # Apply validation rules
            is_valid = True
            validation_errors = []

            # Check required fields
            required_fields = ["id", "name", "price", "price_with_tax"]
            for field in required_fields:
                if field not in record:
                    is_valid = False
                    validation_errors.append(f"Missing required field: {field}")

            # Check data types
            if "price" in record and not isinstance(record["price"], (int, float)):
                is_valid = False
                validation_errors.append("Price must be a number")

            if "id" in record and not isinstance(record["id"], int):
                is_valid = False
                validation_errors.append("ID must be an integer")

            # Add validation result
            record_with_validation = record.copy()
            record_with_validation["is_valid"] = is_valid
            record_with_validation["validation_errors"] = validation_errors

            if is_valid:
                valid_records.append(record_with_validation)
            else:
                invalid_records.append(record_with_validation)

        validation_result = {
            "valid_records": valid_records,
            "invalid_records": invalid_records,
            "total_records": len(records),
            "valid_count": len(valid_records),
            "invalid_count": len(invalid_records),
            "original_source": transformed_data.get("original_source"),
            "original_timestamp": transformed_data.get("original_timestamp"),
            "transformation_timestamp": transformed_data.get("transformation_timestamp"),
            "validation_timestamp": datetime.now().isoformat()
        }

        # Get current state
        current_state = await data_validator.get_state()
        records_validated = current_state.get("records_validated", 0) + len(records)
        valid_records_count = current_state.get("valid_records", 0) + len(valid_records)
        invalid_records_count = (
            current_state.get("invalid_records", 0) + len(invalid_records)
        )

        # Update state to track this validation
        await data_validator.update_state(
            records_validated=records_validated,
            valid_records=valid_records_count,
            invalid_records=invalid_records_count,
            last_validation_time=datetime.now().isoformat(),
            status="completed"
        )

        logger.info(
            f"Data validator: Validated {len(records)} records. "
            f"Valid: {len(valid_records)}, Invalid: {len(invalid_records)}"
        )
        return validation_result

    # Define the data storage agent
    @stella_agent(
        name="data_storage",
        broker=broker,
        topic=pipeline_topic,
        depends_on=["data_validator"]
    )
    async def data_storage(message: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Store the validated data"""
        logger.info("Data storage: Starting data storage")

        # Skip if message is not from data_validator
        source = message.get("source")
        if source != "data_validator":
            logger.debug(
                f"Data storage: Skipping message from {source} "
                "(not from data_validator)"
            )
            return None

        # Extract the validated data
        validated_data = (
            message.get("dependency_messages", {})
            .get("data_validator", {})
            .get("data", {})
        )

        # In a real-world scenario, this would store the data in a database
        # For this example, we'll just write to a JSON file
        output_file = f"processed_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump(validated_data, f, indent=2)

        storage_result = {
            "output_file": output_file,
            "total_records": validated_data.get("total_records", 0),
            "valid_records": validated_data.get("valid_count", 0),
            "invalid_records": validated_data.get("invalid_count", 0),
            "storage_timestamp": datetime.now().isoformat()
        }

        # Get current state
        current_state = await data_storage.get_state()
        files_written = current_state.get("files_written", 0) + 1
        records_stored = current_state.get("records_stored", 0) + storage_result["total_records"]

        # Update state to track this storage operation
        await data_storage.update_state(
            files_written=files_written,
            records_stored=records_stored,
            last_file=output_file,
            last_storage_time=datetime.now().isoformat(),
            status="completed"
        )

        logger.info(
            f"Data storage: Stored {storage_result['total_records']} records "
            f"to {output_file}"
        )
        return storage_result

async def run_pipeline() -> None:
    """Run the data processing pipeline"""
    global pipeline_complete

    try:
        # Set up the pipeline
        await setup_pipeline()

        # Start the workflow
        await stella_agent.start_workflow()

        # Wait for pipeline to complete
        while not pipeline_complete:
            # Get the registered agents
            agents = stella_agent.get_agents()

            # Check if all agents have completed
            all_completed = True
            for name, agent in agents.items():
                try:
                    state = await agent["handler"].get_state()
                    status = state.get("status")
                    if status != "completed":
                        all_completed = False
                        break
                except Exception as e:
                    logger.error(f"Error checking agent {name} state: {e!s}")
                    all_completed = False
                    break

            if all_completed:
                pipeline_complete = True
                logger.info("Pipeline completed successfully")
                break

            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Error running pipeline: {e!s}")
        raise
    finally:
        # Stop the workflow
        await stella_agent.stop_workflow()

def main() -> None:
    """Main entry point"""
    try:
        asyncio.run(run_pipeline())
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {e!s}")
        sys.exit(1)

if __name__ == "__main__":
    main()
