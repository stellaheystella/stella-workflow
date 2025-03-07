import asyncio
import logging
import pytest
import pytest_asyncio
import uuid
from datetime import datetime

from stella_workflow import stella_agent, in_loop

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_loops")

# Global variables to track agent calls
user_list_called = False
email_sender_called = 0  # Counter for multiple calls
email_logger_called = 0  # Counter for multiple calls

# Global variables to store agent outputs
user_list_output = None
email_sender_outputs = []
email_logger_outputs = []

@pytest_asyncio.fixture
async def test_broker(broker):
    """Get the test broker"""
    return broker

@pytest.fixture
def test_topic():
    """Generate a unique topic for each test"""
    return f"test_loops_topic_{uuid.uuid4().hex}"

@pytest.fixture
def reset_tracking():
    """Reset the global tracking variables before each test"""
    global user_list_called, email_sender_called, email_logger_called
    global user_list_output, email_sender_outputs, email_logger_outputs
    
    user_list_called = False
    email_sender_called = 0
    email_logger_called = 0
    
    user_list_output = None
    email_sender_outputs = []
    email_logger_outputs = []

@pytest_asyncio.fixture
async def setup_workflow(test_broker, test_topic, reset_tracking):
    """Set up the workflow with user list, email sender, and email logger agents"""
    global user_list_called, email_sender_called, email_logger_called
    global user_list_output, email_sender_outputs, email_logger_outputs
    
    # Clear any existing agents
    stella_agent.clear_agents()
    
    # Define the user list agent
    @stella_agent(name="user_list", broker=test_broker, topic=test_topic)
    async def user_list_agent():
        """Generate a list of users"""
        global user_list_called, user_list_output
        
        # Generate test data
        user_list_output = {
            "users": [
                {"email": "user1@example.com", "name": "User One"},
                {"email": "user2@example.com", "name": "User Two"},
                {"email": "user3@example.com", "name": "User Three"}
            ],
            "total": 3,
            "timestamp": datetime.now().isoformat()
        }
        
        # Mark the user list as called
        user_list_called = True
        
        logger.info(f"User list agent called, returning: {user_list_output}")
        return user_list_output
    
    # Define the email sender agent with loop
    @in_loop(
        loop_name="email_loop",
        exit_condition="message.get('state', {}).get('position', 0) >= message['dependency_messages']['user_list']['data']['total'] - 1",
        position=0
    )
    @stella_agent(name="email_sender", broker=test_broker, topic=test_topic, depends_on=["user_list"])
    async def email_sender_agent(message):
        """Send emails to users in a loop"""
        global email_sender_called, email_sender_outputs
        
        logger.info(f"Email sender received message: {message}")
        
        # Extract the user list data
        user_list_data = message.get("dependency_messages", {}).get("user_list", {}).get("data", {})
        users = user_list_data.get("users", [])
        
        # Use a global variable to track position across iterations
        global current_position
        if 'current_position' not in globals():
            current_position = 0
        
        logger.info(f"Email sender current position: {current_position}")
        
        # Check if we have users at this position
        if current_position < len(users):
            user = users[current_position]
            
            # Process the data
            output = {
                "email": user.get("email"),
                "name": user.get("name"),
                "position": current_position,
                "has_more": current_position < len(users) - 1,
                "timestamp": datetime.now().isoformat()
            }
            
            # Increment the call counter
            email_sender_called += 1
            
            # Store the output
            email_sender_outputs.append(output)
            
            # Increment position for next iteration
            current_position += 1
            
            logger.info(f"Email sender called ({email_sender_called}), returning: {output}")
            return output
        else:
            logger.warning(f"Email sender called with invalid position: {current_position}")
            return None
    
    # Define the email logger agent with loop
    @in_loop(
        loop_name="email_loop",
        exit_condition="not message['dependency_messages']['email_sender']['data'].get('has_more', False)",
        position=1
    )
    @stella_agent(name="email_logger", broker=test_broker, topic=test_topic, depends_on=["email_sender"])
    async def email_logger_agent(message):
        """Log emails sent in a loop"""
        global email_logger_called, email_logger_outputs
        
        logger.info(f"Email logger received message: {message}")
        
        # Extract the email sender data
        email_data = message.get("dependency_messages", {}).get("email_sender", {}).get("data", {})
        
        # Process the data
        output = {
            "logged_email": email_data.get("email"),
            "logged_name": email_data.get("name"),
            "status": "sent",
            "position": email_data.get("position"),
            "timestamp": datetime.now().isoformat()
        }
        
        # Increment the call counter
        email_logger_called += 1
        
        # Store the output
        email_logger_outputs.append(output)
        
        logger.info(f"Email logger called ({email_logger_called}), returning: {output}")
        return output
    
    yield

async def test_loop_execution(setup_workflow, test_broker, test_topic):
    """Test that the loop executes for each item in the list"""
    logger.info(f"Starting loop execution test with topic: {test_topic}")
    
    # Start the workflow
    await stella_agent.start_workflow()
    
    # Wait for the message flow to complete
    for _ in range(15):  # Try for up to 15 seconds (loops may take longer)
        if user_list_called and email_sender_called >= 3 and email_logger_called >= 3:
            break
        await asyncio.sleep(1)
    
    # Verify that the user list agent was called
    assert user_list_called, "User list agent was not called"
    assert user_list_output is not None, "User list did not generate output"
    assert len(user_list_output.get("users", [])) == 3, "User list output is incorrect"
    
    # Verify that the email sender was called for each user
    assert email_sender_called == 3, f"Email sender was not called for each user (called {email_sender_called} times)"
    assert len(email_sender_outputs) == 3, "Email sender did not generate output for each user"
    
    # Verify that the email logger was called for each email
    assert email_logger_called == 3, f"Email logger was not called for each email (called {email_logger_called} times)"
    assert len(email_logger_outputs) == 3, "Email logger did not generate output for each email"
    
    # Verify the content of the outputs
    for i, output in enumerate(email_sender_outputs):
        assert output.get("email") == user_list_output.get("users")[i].get("email"), f"Email sender output {i} has incorrect email"
        assert output.get("position") == i, f"Email sender output {i} has incorrect position"
        
    for i, output in enumerate(email_logger_outputs):
        assert output.get("logged_email") == email_sender_outputs[i].get("email"), f"Email logger output {i} has incorrect email"
        assert output.get("status") == "sent", f"Email logger output {i} has incorrect status" 