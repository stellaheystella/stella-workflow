#!/usr/bin/env python3
"""
Document Processing Pipeline

A practical example of using Stella Workflow for document processing.
Each document type (invoice, receipt, contract) is processed differently
based on its type and content.

Usage:
    python processor.py

Environment Variables:
    REDIS_HOST: Redis host (default: localhost)
    REDIS_PORT: Redis port (default: 6379)
    REDIS_USERNAME: Redis username (optional)
    REDIS_PASSWORD: Redis password (optional)
    REDIS_SSL: Whether to use SSL (default: false)
    LOG_LEVEL: Logging level (default: INFO)
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

from stella_workflow.workflow import stella_agent
from stella_workflow.brokers import RedisBroker

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("document_processor.log")
    ]
)
logger = logging.getLogger("document_processor")

# Global variables to track execution
workflow_complete = False
workflow_topic = "document_processing"
output_filename = "document_processor_results.json"

def get_redis_config():
    """Get Redis configuration from environment variables"""
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "username": os.getenv("REDIS_USERNAME", ""),
        "password": os.getenv("REDIS_PASSWORD", ""),
        "db": 0,
        "ssl": os.getenv("REDIS_SSL", "false").lower() == "true",
        "ssl_cert_reqs": os.getenv("REDIS_SSL_CERT_REQS", "none")
    }

async def setup_workflow(broker, topic: str, input_document: Dict[str, Any]):
    """Set up the document processing workflow"""
    # Clear any existing agents
    stella_agent.clear_agents()
    
    # Define the document reader agent
    @stella_agent(name="document_reader", broker=broker, topic=topic)
    async def document_reader():
        """Read and validate the document"""
        try:
            # Get current state
            state = await document_reader.get_state()
            documents_read = state.get("documents_read", 0) + 1
            
            # Create a copy of the input document and add metadata
            document = {
                **input_document,
                "processed_at": datetime.now().isoformat(),
                "status": "read"
            }
            
            # Update state
            await document_reader.update_state(
                documents_read=documents_read,
                last_read_time=datetime.now().isoformat(),
                last_document_id=document.get("id"),
                status="active"
            )
            
            # Store the document in memory
            await document_reader.set_memory(f"document_{document['id']}", document)
            
            logger.info(f"Read document: {document.get('id')} of type {document.get('type')}")
            return document
        except Exception as e:
            logger.error(f"Error reading document: {str(e)}")
            return None
    
    # Define the invoice processor agent
    @stella_agent(
        name="invoice_processor",
        broker=broker,
        topic=topic,
        depends_on=["document_reader"],
        condition="message['dependency_messages']['document_reader']['data']['type'] == 'invoice'"
    )
    async def invoice_processor(message):
        """Process invoice documents"""
        try:
            # Skip if message is not from our dependency
            source = message.get("source")
            if source != "document_reader":
                return None
            
            # Get the document from reader
            doc = message["dependency_messages"]["document_reader"]["data"]
            
            # Get current state
            state = await invoice_processor.get_state()
            invoices_processed = state.get("invoices_processed", 0) + 1
            
            # Process invoice-specific fields
            processed = {
                "id": doc["id"],
                "type": "invoice",
                "processed_at": datetime.now().isoformat(),
                "total_amount": float(doc["amount"]),
                "tax_amount": float(doc["amount"]) * 0.2,  # 20% tax
                "vendor": doc["vendor"],
                "status": "processed"
            }
            
            # Update state
            await invoice_processor.update_state(
                invoices_processed=invoices_processed,
                last_processed_time=datetime.now().isoformat(),
                last_invoice_id=doc["id"],
                status="active"
            )
            
            # Store processed invoice in memory
            await invoice_processor.set_memory(f"invoice_{doc['id']}", processed)
            
            logger.info(f"Processed invoice: {doc['id']}")
            return processed
        except Exception as e:
            logger.error(f"Error processing invoice: {str(e)}")
            return None
    
    # Define the receipt processor agent
    @stella_agent(
        name="receipt_processor",
        broker=broker,
        topic=topic,
        depends_on=["document_reader"],
        condition="message['dependency_messages']['document_reader']['data']['type'] == 'receipt'"
    )
    async def receipt_processor(message):
        """Process receipt documents"""
        try:
            # Skip if message is not from our dependency
            source = message.get("source")
            if source != "document_reader":
                return None
            
            # Get the document from reader
            doc = message["dependency_messages"]["document_reader"]["data"]
            
            # Get current state
            state = await receipt_processor.get_state()
            receipts_processed = state.get("receipts_processed", 0) + 1
            
            # Process receipt-specific fields
            processed = {
                "id": doc["id"],
                "type": "receipt",
                "processed_at": datetime.now().isoformat(),
                "items": doc["items"],
                "total_amount": sum(item["price"] for item in doc["items"]),
                "store": doc["store"],
                "status": "processed"
            }
            
            # Update state
            await receipt_processor.update_state(
                receipts_processed=receipts_processed,
                last_processed_time=datetime.now().isoformat(),
                last_receipt_id=doc["id"],
                status="active"
            )
            
            # Store processed receipt in memory
            await receipt_processor.set_memory(f"receipt_{doc['id']}", processed)
            
            logger.info(f"Processed receipt: {doc['id']}")
            return processed
        except Exception as e:
            logger.error(f"Error processing receipt: {str(e)}")
            return None
    
    # Define the contract processor agent
    @stella_agent(
        name="contract_processor",
        broker=broker,
        topic=topic,
        depends_on=["document_reader"],
        condition="message['dependency_messages']['document_reader']['data']['type'] == 'contract'"
    )
    async def contract_processor(message):
        """Process contract documents"""
        try:
            # Skip if message is not from our dependency
            source = message.get("source")
            if source != "document_reader":
                return None
            
            # Get the document from reader
            doc = message["dependency_messages"]["document_reader"]["data"]
            
            # Get current state
            state = await contract_processor.get_state()
            contracts_processed = state.get("contracts_processed", 0) + 1
            
            # Process contract-specific fields
            processed = {
                "id": doc["id"],
                "type": "contract",
                "processed_at": datetime.now().isoformat(),
                "parties": doc["parties"],
                "start_date": doc["start_date"],
                "end_date": doc["end_date"],
                "value": float(doc["value"]),
                "status": "processed"
            }
            
            # Update state
            await contract_processor.update_state(
                contracts_processed=contracts_processed,
                last_processed_time=datetime.now().isoformat(),
                last_contract_id=doc["id"],
                status="active"
            )
            
            # Store processed contract in memory
            await contract_processor.set_memory(f"contract_{doc['id']}", processed)
            
            logger.info(f"Processed contract: {doc['id']}")
            return processed
        except Exception as e:
            logger.error(f"Error processing contract: {str(e)}")
            return None
    
    # Define the document archiver agent
    @stella_agent(
        name="document_archiver",
        broker=broker,
        topic=topic,
        depends_on=["invoice_processor", "receipt_processor", "contract_processor"]
    )
    async def document_archiver(message):
        """Archive the processed document"""
        try:
            # Get the processed document from whichever processor handled it
            doc = None
            
            # Check each dependency in order
            for processor in ["invoice_processor", "receipt_processor", "contract_processor"]:
                if processor in message["dependency_messages"] and message["dependency_messages"][processor].get("data"):
                    doc = message["dependency_messages"][processor]["data"]
                    logger.info(f"Found document from {processor}")
                    break
            
            if not doc:
                logger.error("No processed document found in any processor")
                return None
            
            # Get current state
            state = await document_archiver.get_state()
            documents_archived = state.get("documents_archived", 0) + 1
            
            # Add archival information
            archived = {
                **doc,
                "archived_at": datetime.now().isoformat(),
                "archive_id": f"ARCH-{doc['id']}",
                "status": "archived"
            }
            
            # Update state
            await document_archiver.update_state(
                documents_archived=documents_archived,
                last_archived_time=datetime.now().isoformat(),
                last_archive_id=archived["archive_id"],
                status="active"
            )
            
            # Store archived document in memory
            memory_key = f"archive_{doc['id']}"
            await document_archiver.set_memory(memory_key, archived)
            
            logger.info(f"Archived document: {doc['id']}")
            
            # Signal workflow completion
            global workflow_complete
            workflow_complete = True
            
            return archived
        except Exception as e:
            logger.error(f"Error archiving document: {str(e)}")
            return None
    
    return broker

async def process_document(document: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single document through the workflow"""
    global workflow_complete
    workflow_complete = False
    broker = None
    
    try:
        # Create broker
        broker = RedisBroker(get_redis_config())
        await broker.connect()
        
        # Setup workflow with the document
        await setup_workflow(broker, workflow_topic, document)
        
        # Start workflow
        logger.info(f"Starting document processing workflow for {document['id']} of type {document['type']}")
        await stella_agent.start_workflow()
        
        # Wait for processing to complete
        for _ in range(15):  # Try for up to 15 seconds
            if workflow_complete:
                logger.info(f"Workflow completed for document {document['id']}")
                break
            await asyncio.sleep(1)
        
        # Get the final result from archiver
        archiver = stella_agent.get_agents().get("document_archiver", {}).get("handler")
        if archiver:
            try:
                memory_key = f"archive_{document['id']}"
                memory = await archiver.get_memory(memory_key)
                if memory:
                    logger.info(f"Retrieved archived document {document['id']} from memory")
                    return memory
                else:
                    logger.error(f"No memory found for key {memory_key}")
            except Exception as e:
                logger.error(f"Error retrieving memory: {str(e)}")
        
        if not workflow_complete:
            logger.error(f"Document processing timed out for {document['id']}")
        
        return None
    
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        return None
    
    finally:
        # Stop workflow and clean up
        try:
            await stella_agent.stop_workflow()
        except Exception as e:
            logger.error(f"Error stopping workflow: {str(e)}")
        
        if broker:
            try:
                await broker.close()
            except Exception as e:
                logger.error(f"Error closing broker: {str(e)}")

async def main():
    """Main entry point"""
    global output_filename
    
    # Generate a unique output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"document_processor_results_{timestamp}.json"
    
    # Sample documents for testing
    documents = [
        {
            "id": "INV-001",
            "type": "invoice",
            "amount": "1000.00",
            "vendor": "Acme Corp",
            "date": "2024-03-05"
        },
        {
            "id": "RCP-001",
            "type": "receipt",
            "store": "Supermarket",
            "items": [
                {"name": "Item 1", "price": 10.00},
                {"name": "Item 2", "price": 20.00}
            ],
            "date": "2024-03-05"
        },
        {
            "id": "CTR-001",
            "type": "contract",
            "parties": ["Party A", "Party B"],
            "start_date": "2024-03-05",
            "end_date": "2025-03-05",
            "value": "5000.00"
        }
    ]
    
    # Store results
    results = []
    
    try:
        # Process each document
        for doc in documents:
            result = await process_document(doc)
            if result:
                print(f"\nProcessed {doc['type']}:")
                print(json.dumps(result, indent=2))
                results.append(result)
            else:
                print(f"\nFailed to process {doc['type']}: {doc['id']}")
                # Add failure record
                results.append({
                    "id": doc["id"],
                    "type": doc["type"],
                    "status": "failed",
                    "processed_at": datetime.now().isoformat()
                })
        
        # Save results to file
        with open(output_filename, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_documents": len(documents),
                "successful_documents": sum(1 for r in results if r.get("status") != "failed"),
                "failed_documents": sum(1 for r in results if r.get("status") == "failed"),
                "results": results
            }, f, indent=2)
        
        print(f"\nResults saved to {output_filename}")
    
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProcessing interrupted by user")
    except Exception as e:
        print(f"Error: {str(e)}") 