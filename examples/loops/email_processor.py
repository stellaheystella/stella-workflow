#!/usr/bin/env python3
"""
Bulk Email Processor

A practical example of using Stella Workflow for processing bulk emails with loops.
This example demonstrates how to:
1. Fetch a list of users from a data source
2. Process each user in a loop to send personalized emails
3. Log the email sending results for each user
4. Generate a summary report of the email campaign

Usage:
    python email_processor.py

Environment Variables:
    REDIS_HOST: Redis host (default: localhost)
    REDIS_PORT: Redis port (default: 6379)
    REDIS_USERNAME: Redis username (optional)
    REDIS_PASSWORD: Redis password (optional)
    REDIS_SSL: Whether to use SSL (default: false)
    LOG_LEVEL: Logging level (default: INFO)
    EMAIL_DELAY: Delay between emails in seconds (default: 0.5)
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from stella_workflow.brokers import RedisBroker
from stella_workflow.loop import in_loop
from stella_workflow.workflow import stella_agent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bulk_email_processor.log")
    ]
)
logger = logging.getLogger("bulk_email_processor")

# Global variables to track execution
workflow_complete = False
workflow_topic = f"bulk_email_processor_{uuid.uuid4().hex[:8]}"
output_filename = "email_campaign_results.json"
email_delay = float(os.getenv("EMAIL_DELAY", "0.5"))  # Delay between emails

def get_redis_config() -> dict[str, Any]:
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

def get_sample_users() -> list[dict[str, Any]]:
    """Generate sample user data for the example"""
    return [
        {
            "id": "U001",
            "email": "john.doe@example.com",
            "name": "John Doe",
            "preferences": {
                "newsletter": True,
                "product_updates": True
            }
        },
        {
            "id": "U002",
            "email": "jane.smith@example.com",
            "name": "Jane Smith",
            "preferences": {
                "newsletter": True,
                "product_updates": False
            }
        },
        {
            "id": "U003",
            "email": "bob.johnson@example.com",
            "name": "Bob Johnson",
            "preferences": {
                "newsletter": False,
                "product_updates": True
            }
        },
        {
            "id": "U004",
            "email": "alice.williams@example.com",
            "name": "Alice Williams",
            "preferences": {
                "newsletter": True,
                "product_updates": True
            }
        },
        {
            "id": "U005",
            "email": "charlie.brown@example.com",
            "name": "Charlie Brown",
            "preferences": {
                "newsletter": True,
                "product_updates": True
            }
        }
    ]

async def setup_workflow(broker: RedisBroker, topic: str, campaign_type: str) -> None:
    """Set up the email processing workflow"""
    # Clear any existing agents
    stella_agent.clear_agents()

    # Define the user list agent
    @stella_agent(name="user_list", broker=broker, topic=topic)
    async def user_list() -> dict[str, Any] | None:
        """Fetch the list of users for the email campaign"""
        try:
            # In a real application, this would fetch users from a database
            # For this example, we'll use sample data
            users = get_sample_users()

            # Filter users based on campaign type
            if campaign_type == "newsletter":
                users = [
                    user for user in users
                    if user["preferences"]["newsletter"]
                ]
            elif campaign_type == "product_update":
                users = [
                    user for user in users
                    if user["preferences"]["product_updates"]
                ]

            # Prepare the output
            output = {
                "users": users,
                "total": len(users),
                "campaign_type": campaign_type,
                "timestamp": datetime.now().isoformat()
            }

            # Update state
            await user_list.update_state(
                users_count=len(users),
                campaign_type=campaign_type,
                last_run=datetime.now().isoformat(),
                status="completed"
            )

            # Store the user list in memory
            await user_list.set_memory("user_list", output)

            # Log collection metrics
            logger.info(f"Fetched {len(users)} users for {campaign_type} campaign")
            return output
        except Exception as e:
            logger.error(f"Error fetching user list: {e!s}")
            return None

    # Define the email sender agent with loop
    @in_loop(
        loop_name="email_loop",
        exit_condition=(
            "message.get('state', {}).get('position', 0) >= "
            "message['dependency_messages']['user_list']['data']['total'] - 1"
        ),
        position=0
    )
    @stella_agent(
        name="email_sender",
        broker=broker,
        topic=topic,
        depends_on=["user_list"]
    )
    async def email_sender(message: dict[str, Any]) -> dict[str, Any] | None:
        """Send emails to users in a loop"""
        try:
            # Skip if message is not from our dependency
            source = message.get("source")
            if source != "user_list" and not source.startswith("email_sender"):
                return None

            # Extract the user list data
            user_list_data = (
                message.get("dependency_messages", {})
                .get("user_list", {})
                .get("data", {})
            )
            users = user_list_data.get("users", [])
            campaign_type = user_list_data.get("campaign_type", "")

            # Get current state and position
            state = await email_sender.get_state()
            position = state.get("position", 0)

            logger.info(f"Email sender processing position: {position}")

            # Check if we have users at this position
            if position < len(users):
                user = users[position]

                # In a real application, this would send an actual email
                # For this example, we'll simulate sending

                # Add a small delay to simulate email sending
                await asyncio.sleep(email_delay)

                # Prepare email content based on campaign type
                if campaign_type == "newsletter":
                    subject = "Your Weekly Newsletter"
                    content = f"Hello {user['name']}, here's your weekly newsletter!"
                elif campaign_type == "product_update":
                    subject = "New Product Updates"
                    content = f"Hello {user['name']}, check out our latest product updates!"
                else:
                    subject = "Important Information"
                    content = f"Hello {user['name']}, we have important information for you!"

                # Prepare the output
                output = {
                    "user_id": user.get("id"),
                    "email": user.get("email"),
                    "name": user.get("name"),
                    "subject": subject,
                    "content": content,
                    "position": position,
                    "has_more": position < len(users) - 1,
                    "timestamp": datetime.now().isoformat()
                }

                # Update state with new position for next iteration
                await email_sender.update_state(
                    position=position + 1,
                    emails_sent=state.get("emails_sent", 0) + 1,
                    last_email=user.get("email"),
                    status="active"
                )

                # Store the email in memory
                await email_sender.set_memory(f"email_{user['id']}", output)

                logger.info(f"Sent email to {user['email']} (position {position})")
                return output
            else:
                # We've processed all users
                logger.info("All users processed, no more emails to send")

                # Update state to indicate completion
                await email_sender.update_state(
                    status="completed"
                )

                # Return a completion message
                return {
                    "message": "All emails sent",
                    "position": position,
                    "has_more": False,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error sending email: {e!s}")
            return None

    # Define the email logger agent with loop
    @in_loop(
        loop_name="email_loop",
        exit_condition=(
            "not message['dependency_messages']['email_sender']['data']"
            ".get('has_more', False)"
        ),
        position=1
    )
    @stella_agent(
        name="email_logger",
        broker=broker,
        topic=topic,
        depends_on=["email_sender"]
    )
    async def email_logger(message: dict[str, Any]) -> dict[str, Any] | None:
        """Log email sending results"""
        try:
            # Skip if message is not from our dependency
            source = message.get("source")
            if source != "email_sender" and not source.startswith("email_logger"):
                return None

            # Extract the email data
            email_data = (
                message.get("dependency_messages", {})
                .get("email_sender", {})
                .get("data", {})
            )

            # In a real application, this would log to a database or monitoring system
            # For this example, we'll just create a log entry

            # Prepare the output
            output = {
                "user_id": email_data.get("user_id"),
                "email": email_data.get("email"),
                "name": email_data.get("name"),
                "subject": email_data.get("subject"),
                "status": "delivered",  # In a real app, this would be the actual delivery status
                "position": email_data.get("position"),
                "timestamp": datetime.now().isoformat()
            }

            # Get current state
            state = await email_logger.get_state()

            # Update state
            await email_logger.update_state(
                emails_logged=state.get("emails_logged", 0) + 1,
                last_logged=email_data.get("email"),
                status="active"
            )

            # Store the log in memory
            await email_logger.set_memory(f"log_{email_data.get('user_id')}", output)

            logger.info(f"Email logger processing position: {email_data.get('position')}")

            # Check if this is the last email
            if not email_data.get("has_more", False):
                logger.info("All emails logged, no more to process")
                global workflow_complete
                workflow_complete = True

                # Generate campaign summary immediately
                user_list_state = await user_list.get_state()
                email_sender_state = await email_sender.get_state()
                email_logger_state = await email_logger.get_state()

                # Prepare the summary
                summary = {
                    "campaign_type": user_list_state.get("campaign_type", "unknown"),
                    "total_users": user_list_state.get("users_count", 0),
                    "emails_sent": email_sender_state.get("emails_sent", 0),
                    "emails_delivered": email_logger_state.get("emails_logged", 0),
                    "completion_time": datetime.now().isoformat(),
                    "status": "completed"
                }

                # Store the summary in memory
                await campaign_summary.set_memory("campaign_summary", summary)
                logger.info(f"Campaign summary: {summary['emails_sent']} emails sent")

            return output
        except Exception as e:
            logger.error(f"Error logging email: {e!s}")
            return None

    # Define the campaign summary agent
    @stella_agent(name="campaign_summary", broker=broker, topic=topic, depends_on=["email_logger"])
    async def campaign_summary(message: dict[str, Any]) -> dict[str, Any] | None:
        """Generate a summary of the email campaign"""
        try:
            # Skip if workflow is not complete
            global workflow_complete
            if not workflow_complete:
                return None

            # Try to get the summary from memory first
            try:
                summary = await campaign_summary.get_memory("campaign_summary")
                if summary:
                    logger.info(f"Retrieved existing campaign summary: {summary}")
                    return summary
            except Exception:
                # If memory retrieval fails, generate a new summary
                pass

            # Get states from all agents
            user_list_state = await user_list.get_state()
            email_sender_state = await email_sender.get_state()
            email_logger_state = await email_logger.get_state()

            # Prepare the summary
            summary = {
                "campaign_type": user_list_state.get("campaign_type", "unknown"),
                "total_users": user_list_state.get("users_count", 0),
                "emails_sent": email_sender_state.get("emails_sent", 0),
                "emails_delivered": email_logger_state.get("emails_logged", 0),
                "completion_time": datetime.now().isoformat(),
                "status": "completed"
            }

            # Update state
            await campaign_summary.update_state(
                campaign_type=summary["campaign_type"],
                total_users=summary["total_users"],
                emails_sent=summary["emails_sent"],
                emails_delivered=summary["emails_delivered"],
                status="completed"
            )

            # Store the summary in memory
            await campaign_summary.set_memory("campaign_summary", summary)

            logger.info(f"Generated new campaign summary: {summary}")
            return summary
        except Exception as e:
            logger.error(f"Error generating campaign summary: {e!s}")
            return None

    return broker

async def run_email_campaign(campaign_type: str) -> dict:
    """Run an email campaign for the specified type"""
    global workflow_complete
    workflow_complete = False
    broker = None

    try:
        # Create broker
        broker = RedisBroker(get_redis_config())
        await broker.connect()

        # Setup workflow
        await setup_workflow(broker, workflow_topic, campaign_type)

        # Start workflow
        logger.info(f"Starting email campaign workflow for {campaign_type}")
        await stella_agent.start_workflow()

        # Wait for processing to complete
        for _ in range(30):  # Try for up to 30 seconds
            if workflow_complete:
                logger.info(f"Workflow completed for {campaign_type} campaign")
                # Give a little time for the campaign summary to be stored
                await asyncio.sleep(1)
                break
            await asyncio.sleep(1)

        # Get the campaign summary
        summary_agent = stella_agent.get_agents().get("campaign_summary", {}).get("handler")
        if summary_agent:
            try:
                summary = await summary_agent.get_memory("campaign_summary")
                if summary:
                    logger.info("Retrieved campaign summary")
                    return summary
                else:
                    # Try to generate the summary directly
                    summary = await summary_agent()
                    if summary:
                        logger.info("Generated campaign summary directly")
                        return summary
                    else:
                        logger.error("Failed to generate campaign summary")
            except Exception as e:
                logger.error(f"Error retrieving campaign summary: {e!s}")

        if not workflow_complete:
            logger.error("Campaign processing timed out")

            # Create a partial summary from available state
            agents = stella_agent.get_agents()
            user_list_agent = agents.get("user_list", {}).get("handler")
            email_sender_agent = agents.get("email_sender", {}).get("handler")

            if user_list_agent and email_sender_agent:
                try:
                    user_list_state = await user_list_agent.get_state()
                    email_sender_state = await email_sender_agent.get_state()

                    return {
                        "campaign_type": campaign_type,
                        "total_users": user_list_state.get("users_count", 0),
                        "emails_sent": email_sender_state.get("emails_sent", 0),
                        # Assume all sent emails were delivered
                        "emails_delivered": email_sender_state.get("emails_sent", 0),
                        "completion_time": datetime.now().isoformat(),
                        "status": "partial"
                    }
                except Exception as e:
                    logger.error(f"Error creating partial summary: {e!s}")

        # If all else fails, return a basic summary
        return {
            "campaign_type": campaign_type,
            "status": "unknown",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error running email campaign: {e!s}")
        return {
            "campaign_type": campaign_type,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

    finally:
        # Stop workflow and clean up
        try:
            await stella_agent.stop_workflow()
        except Exception as e:
            logger.error(f"Error in workflow: {e!s}")
            sys.exit(1)

        if broker:
            try:
                await broker.close()
            except Exception as e:
                logger.error(f"Error closing broker: {e!s}")

async def main() -> None:
    """Main entry point"""
    global output_filename

    # Generate a unique output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"email_campaign_results_{timestamp}.json"

    # Campaign types to run
    campaign_types = ["newsletter", "product_update"]

    # Store results
    results = []

    try:
        # Run each campaign type
        for campaign_type in campaign_types:
            logger.info(f"Starting {campaign_type} campaign")

            # Run the campaign
            summary = await run_email_campaign(campaign_type)

            if summary:
                # Check if the campaign was successful
                if summary.get("status") == "completed":
                    print(f"\nCompleted {campaign_type} campaign successfully:")
                    print(json.dumps(summary, indent=2))
                    results.append(summary)
                elif summary.get("status") == "partial":
                    print(f"\nPartially completed {campaign_type} campaign:")
                    print(json.dumps(summary, indent=2))
                    results.append(summary)
                else:
                    print(f"\nFailed to complete {campaign_type} campaign:")
                    print(json.dumps(summary, indent=2))
                    results.append(summary)
            else:
                print(f"\nNo results for {campaign_type} campaign")
                # Add failure record
                results.append({
                    "campaign_type": campaign_type,
                    "status": "failed",
                    "timestamp": datetime.now().isoformat()
                })

        # Calculate success metrics
        successful = sum(1 for r in results if r.get("status") == "completed")
        partial = sum(1 for r in results if r.get("status") == "partial")
        failed = sum(1 for r in results if r.get("status") not in ["completed", "partial"])

        # Save results to file
        with open(output_filename, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_campaigns": len(campaign_types),
                "successful_campaigns": successful,
                "partial_campaigns": partial,
                "failed_campaigns": failed,
                "results": results
            }, f, indent=2)

        print(f"\nResults saved to {output_filename}")

        # Print summary
        print("\nCampaign Summary:")
        print(f"  Total campaigns: {len(campaign_types)}")
        print(f"  Successful: {successful}")
        print(f"  Partial: {partial}")
        print(f"  Failed: {failed}")

    except Exception as e:
        logger.error(f"Error in main: {e!s}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Workflow interrupted by user")
    except Exception as e:
        logger.error(f"Error in workflow: {e!s}")
        sys.exit(1)
