# Stella Workflow Core Agent Documentation

## Core Concepts

### Agent
An agent is the fundamental building block of a Stella workflow. It represents a single unit of work that can:
- Process incoming messages
- Maintain state
- Produce output messages
- Interact with other agents through a message broker

Example agent output:
```json
{
    "source": "temperature_sensor",
    "data": {
        "value": 25.5,
        "unit": "celsius",
        "timestamp": "2024-02-14T12:00:00Z"
    }
}
```

### Message Flow
Messages in Stella follow these rules:
1. Must be JSON-serializable dictionaries
2. Must contain a `source` field identifying the sender
3. Must contain a `data` field with the actual payload
4. Can optionally contain additional metadata

Example message flow:
```json
// Simple flow: Producer -> Processor -> Consumer

// 1. Producer Configuration
@stella_agent(name="producer",broker=broker,topic="data")

// Input: None (Entry Point)

// Output:
{
    "source": "producer",
    "data": {
        "value": "raw_data"
    }
}

// 2. Processor Configuration
@stella_agent(name="processor",broker=broker,topic="data",depends_on=["producer"])

// Input Message:
{
    "source": "producer",
    "data": {
        "value": "raw_data"
    }
}

// Dependencies in Memory:
{
    "dependency_messages": {
        "producer": {
            "source": "producer",
            "data": {
                "value": "raw_data"
            },
            "received_at": "2024-02-14T12:00:00Z"
        }
    }
}

// Output:
{
    "source": "processor",
    "data": {
        "value": "PROCESSED_DATA"
    }
}

// 3. Consumer Configuration
@stella_agent(name="consumer",broker=broker,topic="data",depends_on=["processor"])

// Input Message:
{
    "source": "processor",
    "data": {
        "value": "PROCESSED_DATA"
    }
}

// Dependencies in Memory:
{
    "dependency_messages": {
        "processor": {
            "source": "processor",
            "data": {
                "value": "PROCESSED_DATA"
            },
            "received_at": "2024-02-14T12:00:00Z"
        }
    }
}

// Output: None (End of Chain)
```

Key points:
1. Entry points have no input
2. Each dependent agent receives both input message and dependency memory
3. Dependencies are stored with timestamps
4. Messages maintain consistent structure

### Dependencies
Agents can depend on messages from other agents:
- Dependencies are specified by agent names
- All dependencies must be satisfied before processing
- Messages from dependencies are collected and merged before processing
- Timeout mechanism prevents indefinite waiting

Example:
```json
// Multiple Producers -> Single Consumer Flow

// 1. Counter Producer Configuration
@stella_agent(name="counter",broker=broker,topic="data")

// Input: None (Entry Point)

// Output:
{
    "source": "counter",
    "data": {
        "count": 42
    }
}

// 2. Namer Producer Configuration
@stella_agent(name="namer",broker=broker,topic="data")

// Input: None (Entry Point)

// Output:
{
    "source": "namer",
    "data": {
        "name": "test"
    }
}

// 3. Consumer Configuration
@stella_agent(name="consumer",broker=broker,topic="data",depends_on=["counter", "namer"])

// Input Messages (received separately):
{
    "source": "counter",
    "data": {
        "count": 42
    }
}

{
    "source": "namer",
    "data": {
        "name": "test"
    }
}

// Dependencies in Memory (after receiving both):
{
    "dependency_messages": {
        "counter": {
            "source": "counter",
            "data": {
                "count": 42
            },
            "received_at": "2024-02-14T12:00:00Z"
        },
        "namer": {
            "source": "namer",
            "data": {
                "name": "test"
            },
            "received_at": "2024-02-14T12:00:01Z"
        }
    }
}

// Output (after processing both messages):
{
    "source": "consumer",
    "data": {
        "result": "test_42"
    }
}
```

Key points:
1. Multiple producers can run independently
2. Consumer waits for all dependency messages
3. Processing starts only when all dependencies are in memory
4. Timestamps track message arrival order

### Memory Management

Each agent maintains two types of memory: State and Dependencies.

State Memory tracks operational metrics and agent status:
- `messages_processed`: Counter of successfully handled messages
- `last_processed_time`: Timestamp of most recent message processing
- `errors`: List of recent error events (if any)
- `status`: Current operational state of the agent

Dependencies Memory stores incoming messages from other agents until processing is complete.

Example workflow:
```json
// Data Collection Flow with Memory States

// 1. Sensor Configuration
@stella_agent(name="sensor",broker=broker,topic="data")

// Input: None (Entry Point)

// State Memory:
{
    "state": {
        "messages_processed": 42,
        "last_processed_time": "2024-02-14T12:00:00Z",
        "errors": [],
        "status": "running"
    }
}

// Output:
{
    "source": "sensor",
    "data": {
        "value": 42
    }
}

// 2. Processor Configuration
@stella_agent(name="processor",broker=broker,topic="data",depends_on=["sensor"])

// Input Message:
{
    "source": "sensor",
    "data": {
        "value": 42
    }
}

// State Memory:
{
    "state": {
        "messages_processed": 15,
        "last_processed_time": "2024-02-14T12:00:01Z",
        "errors": [],
        "status": "running"
    }
}

// Dependencies in Memory:
{
    "dependency_messages": {
        "sensor": {
            "source": "sensor",
            "data": {
                "value": 42
            },
            "received_at": "2024-02-14T12:00:00Z"
        }
    }
}

// Output:
{
    "source": "processor",
    "data": {
        "processed_value": 84
    }
}

// 3. Analyzer Configuration
@stella_agent(name="analyzer",broker=broker,topic="data",depends_on=["processor"])

// Input Message:
{
    "source": "processor",
    "data": {
        "processed_value": 84
    }
}

// State Memory:
{
    "state": {
        "messages_processed": 7,
        "last_processed_time": "2024-02-14T12:00:02Z",
        "errors": [],
        "status": "running"
    }
}

// Dependencies in Memory:
{
    "dependency_messages": {
        "processor": {
            "source": "processor",
            "data": {
                "processed_value": 84
            },
            "received_at": "2024-02-14T12:00:01Z"
        }
    }
}

// Output: None (End of Chain)
```

Key points:
1. State Memory tracks agent's operational status
2. Dependency Memory stores incoming messages
3. Each message in memory includes receipt timestamp
4. Memory is cleared after processing

### Conditions

Conditions allow agents to selectively process messages based on their content. They are specified in the `@stella_agent` decorator.

Example condition flow:
```json
// Temperature Alert Flow

// 1. Sensor Configuration
@stella_agent(name="temp_sensor",broker=broker,topic="sensors")

// Input: None (Entry Point)

// Output:
{
    "source": "temp_sensor",
    "data": {
        "temperature": 35,
        "humidity": 85,
        "location": "server_room"
    }
}

// 2. Alert Configuration
@stella_agent(
    name="temp_alert",
    broker=broker,
    topic="sensors",
    depends_on=["temp_sensor"],
    condition="dependency_messages['temp_sensor']['data']['temperature'] > 30"
)

// Input Message:
{
    "source": "temp_sensor",
    "data": {
        "temperature": 35,
        "humidity": 85,
        "location": "server_room"
    }
}

// State Memory:
{
    "state": {
        "messages_processed": 5,
        "last_processed_time": "2024-02-14T12:00:00Z",
        "last_condition_check": true,
        "status": "running"
    }
}

// Dependencies in Memory:
{
    "dependency_messages": {
        "temp_sensor": {
            "source": "temp_sensor",
            "data": {
                "temperature": 35,
                "humidity": 85,
                "location": "server_room"
            },
            "received_at": "2024-02-14T12:00:00Z"
        }
    }
}

// Condition Check: true (dependency_messages['temp_sensor']['data']['temperature'] > 30)
// Output (condition passed):
{
    "source": "temp_alert",
    "data": {
        "alert": "High Temperature",
        "temperature": 35,
        "location": "server_room"
    }
}

// Example with Failed Condition:
// Input Message:
{
    "source": "temp_sensor",
    "data": {
        "temperature": 25,
        "humidity": 60,
        "location": "server_room"
    }
}

// State Memory Updated:
{
    "state": {
        "messages_processed": 5,
        "last_processed_time": "2024-02-14T12:00:01Z",
        "last_condition_check": false,
        "status": "running"
    }
}

// Condition Check: false (25 ≤ 30)
// Output: None (condition failed)
```

Key points:
1. Conditions are evaluated before message processing
2. Messages are skipped if condition evaluates to False
3. State memory tracks condition evaluation results
4. Failed conditions do not generate output messages

### loops

### Loops

Loops allow agents to process messages repeatedly until an exit condition is met. They are specified using the `@in_loop` decorator.

Example loop flow:
```json
// Email Processing Flow

// 1. User List Configuration
@stella_agent(name="user_list",broker=broker,topic="email")

// Input: None (Entry Point)

// State Memory:
{
    "state": {
        "messages_processed": 1,
        "last_processed_time": "2024-02-14T12:00:00Z",
        "errors": [],
        "status": "running"
    }
}

// Output:
{
    "source": "user_list",
    "data": {
        "users": [
            {"email": "user1@example.com"},
            {"email": "user2@example.com"}
        ],
        "total": 2,
        "timestamp": "2024-02-14T12:00:00Z"
    }
}

// 2. Email Sender Configuration
@in_loop(
    loop_name="email_loop",
    exit_condition="dependency_messages['email_sender']['data'].get('position', 0) >= dependency_messages['user_list']['data']['total']",
    position=0
)
@stella_agent(
    name="email_sender",
    broker=broker,
    topic="email",
    depends_on=["user_list"]
)

// First Iteration:
// Dependencies in Memory:
{
    "dependency_messages": {
        "user_list": {
            "source": "user_list",
            "data": {
                "users": [
                    {"email": "user1@example.com"},
                    {"email": "user2@example.com"}
                ],
                "total": 2,
                "timestamp": "2024-02-14T12:00:00Z"
            },
            "received_at": "2024-02-14T12:00:00Z"
        }
    }
}

// State Memory:
{
    "state": {
        "messages_processed": 1,
        "last_processed_time": "2024-02-14T12:00:01Z",
        "errors": [],
        "status": "running",
        "loop_iteration": 1,
        "position": 0
    }
}

// Output (First Email):
{
    "source": "email_sender",
    "data": {
        "email": "user1@example.com",
        "position": 0,
        "has_more": true,
        "timestamp": "2024-02-14T12:00:01Z"
    }
}

// Second Iteration:
// Dependencies in Memory:
{
    "dependency_messages": {
        "user_list": {
            "source": "user_list",
            "data": {
                "users": [
                    {"email": "user1@example.com"},
                    {"email": "user2@example.com"}
                ],
                "total": 2,
                "timestamp": "2024-02-14T12:00:00Z"
            },
            "received_at": "2024-02-14T12:00:00Z"
        }
    }
}

// State Memory:
{
    "state": {
        "messages_processed": 2,
        "last_processed_time": "2024-02-14T12:00:02Z",
        "errors": [],
        "status": "running",
        "loop_iteration": 2,
        "position": 1
    }
}

// Output (Second Email):
{
    "source": "email_sender",
    "data": {
        "email": "user2@example.com",
        "position": 1,
        "has_more": false,
        "timestamp": "2024-02-14T12:00:02Z"
    }
}

// 3. Email Logger Configuration
@in_loop(
    loop_name="email_loop",
    exit_condition="dependency_messages['email_sender']['data'].get('has_more') is False",
    position=1
)
@stella_agent(
    name="email_logger",
    broker=broker,
    topic="email",
    depends_on=["email_sender"]
)

// First Iteration:
// Dependencies in Memory:
{
    "dependency_messages": {
        "email_sender": {
            "source": "email_sender",
            "data": {
                "email": "user1@example.com",
                "position": 0,
                "has_more": true,
                "timestamp": "2024-02-14T12:00:01Z"
            },
            "received_at": "2024-02-14T12:00:01Z"
        }
    }
}

// State Memory:
{
    "state": {
        "messages_processed": 1,
        "last_processed_time": "2024-02-14T12:00:01Z",
        "errors": [],
        "status": "running",
        "loop_iteration": 1
    }
}

// Output (First Log):
{
    "source": "email_logger",
    "data": {
        "logged_email": "user1@example.com",
        "status": "sent",
        "timestamp": "2024-02-14T12:00:01Z"
    }
}

// Second Iteration:
// Dependencies in Memory:
{
    "dependency_messages": {
        "email_sender": {
            "source": "email_sender",
            "data": {
                "email": "user2@example.com",
                "position": 1,
                "has_more": false,
                "timestamp": "2024-02-14T12:00:02Z"
            },
            "received_at": "2024-02-14T12:00:02Z"
        }
    }
}

// State Memory:
{
    "state": {
        "messages_processed": 2,
        "last_processed_time": "2024-02-14T12:00:02Z",
        "errors": [],
        "status": "running",
        "loop_iteration": 2
    }
}

// Output (Final Log):
{
    "source": "email_logger",
    "data": {
        "logged_email": "user2@example.com",
        "status": "sent",
        "timestamp": "2024-02-14T12:00:02Z"
    }
}
```

Key points:
1. Loops require an exit condition based on dependency messages
2. Each agent in the loop maintains its own state and position
3. Loop iterations are tracked in state memory
4. Messages maintain consistent structure across iterations