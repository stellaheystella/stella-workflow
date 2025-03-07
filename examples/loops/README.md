# Bulk Email Processor Example

This example demonstrates how to use Stella Workflow to process bulk emails with loops. It shows a practical implementation of the loop functionality for processing multiple items in sequence.

## Overview

The example simulates an email campaign system that:

1. Fetches a list of users from a data source
2. Processes each user in a loop to send personalized emails
3. Logs the email sending results for each user
4. Generates a summary report of the email campaign

## Key Concepts Demonstrated

- **Loop Processing**: Using the `@in_loop` decorator to process multiple items in sequence
- **State Management**: Tracking position and progress through the loop
- **Memory Storage**: Storing results for each processed item
- **Conditional Execution**: Filtering users based on campaign type
- **Workflow Completion**: Signaling when all items have been processed
- **Error Handling**: Robust error handling throughout the workflow

## Workflow Structure

The workflow consists of four agents:

1. **User List Agent**: Fetches and filters users based on campaign type
2. **Email Sender Agent**: Processes each user in a loop to send emails
3. **Email Logger Agent**: Logs each email sent in a loop
4. **Campaign Summary Agent**: Generates a summary when all emails are processed

## Loop Implementation

The example uses two loops in the same workflow:

```python
# Email sender loop
@in_loop(
    loop_name="email_loop",
    exit_condition="message.get('state', {}).get('position', 0) >= message['dependency_messages']['user_list']['data']['total'] - 1",
    position=0
)
@stella_agent(name="email_sender", broker=broker, topic=topic, depends_on=["user_list"])
async def email_sender(message):
    # ...

# Email logger loop
@in_loop(
    loop_name="email_loop",
    exit_condition="not message['dependency_messages']['email_sender']['data'].get('has_more', False)",
    position=1
)
@stella_agent(name="email_logger", broker=broker, topic=topic, depends_on=["email_sender"])
async def email_logger(message):
    # ...
```

## Running the Example

To run the example:

```bash
python email_processor.py
```

The example will:
1. Run a newsletter campaign for users who have subscribed to newsletters
2. Run a product update campaign for users who have subscribed to product updates
3. Save the results to a JSON file

## Environment Variables

The example supports the following environment variables:

- `REDIS_HOST`: Redis host (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_USERNAME`: Redis username (optional)
- `REDIS_PASSWORD`: Redis password (optional)
- `REDIS_SSL`: Whether to use SSL (default: false)
- `LOG_LEVEL`: Logging level (default: INFO)
- `EMAIL_DELAY`: Delay between emails in seconds (default: 0.5)

## Output

The example generates a JSON file with the results of the campaigns, including:
- Total number of campaigns
- Number of successful campaigns
- Number of partial campaigns
- Number of failed campaigns
- Details for each campaign

Example output:
```json
{
  "timestamp": "2025-03-07T00:14:11.348399",
  "total_campaigns": 2,
  "successful_campaigns": 2,
  "partial_campaigns": 0,
  "failed_campaigns": 0,
  "results": [
    {
      "campaign_type": "newsletter",
      "total_users": 4,
      "emails_sent": 4,
      "emails_delivered": 5,
      "completion_time": "2025-03-07T00:14:02.264241",
      "status": "completed"
    },
    {
      "campaign_type": "product_update",
      "total_users": 4,
      "emails_sent": 4,
      "emails_delivered": 6,
      "completion_time": "2025-03-07T00:14:10.875542",
      "status": "completed"
    }
  ]
}
```

## Key Implementation Details

1. **Robust Error Handling**: The example includes comprehensive error handling to ensure the workflow continues even if individual steps fail.

2. **Multiple Campaign Types**: The example demonstrates running multiple campaigns with different filtering criteria.

3. **State Management**: Each agent maintains its state to track progress and ensure proper execution.

4. **Memory Storage**: Results are stored in memory for later retrieval and reporting.

5. **Workflow Completion Detection**: The example includes logic to detect when all emails have been processed and signal completion.

6. **Summary Generation**: A comprehensive summary is generated at the end of each campaign.

## Notes

This is a simplified example for demonstration purposes. In a production environment, you would:

1. Use a real email sending service
2. Implement proper error handling and retries
3. Store user data in a database
4. Add authentication and security measures
5. Implement rate limiting to avoid overwhelming email services 