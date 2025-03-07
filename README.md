# Stella Workflow

[![PyPI version](https://img.shields.io/pypi/v/stella-workflow.svg)](https://pypi.org/project/stella-workflow/)
[![Python Versions](https://img.shields.io/pypi/pyversions/stella-workflow.svg)](https://pypi.org/project/stella-workflow/)
[![License](https://img.shields.io/github/license/stellaheystella/stella-workflow.svg)](https://github.com/stellaheystella/stella-workflow/blob/main/LICENSE)
[![Tests](https://github.com/stellaheystella/stella-workflow/actions/workflows/python-test.yml/badge.svg)](https://github.com/stellaheystella/stella-workflow/actions/workflows/python-test.yml)

A powerful, flexible workflow engine for AI agents and asynchronous task processing.

## Features

- **Agent-Based Architecture**: Define independent agents that communicate through messages
- **Asynchronous Processing**: Built on Python's asyncio for efficient concurrent execution
- **State Management**: Track and persist agent state across executions
- **Memory Storage**: Store and retrieve data between agent invocations
- **Conditional Execution**: Control agent execution based on dynamic conditions
- **Loop Processing**: Process collections of items with built-in loop functionality
- **Redis Integration**: Use Redis as a reliable message broker and storage backend
- **Extensible Design**: Easily add new brokers, agents, and functionality

## Installation

```bash
pip install stella-workflow
```

## Quick Start

```python
import asyncio
from stella_workflow.workflow import stella_agent
from stella_workflow.brokers import RedisBroker

# Create a broker
broker = RedisBroker({
    "host": "localhost",
    "port": 6379
})

# Define agents
@stella_agent(name="data_producer", broker=broker, topic="example_workflow")
async def data_producer():
    return {"message": "Hello from producer!"}

@stella_agent(name="data_consumer", broker=broker, topic="example_workflow", depends_on=["data_producer"])
async def data_consumer(message):
    producer_data = message["dependency_messages"]["data_producer"]["data"]
    print(f"Received: {producer_data['message']}")
    return {"status": "processed"}

async def main():
    # Connect to broker
    await broker.connect()
    
    try:
        # Start the workflow
        await stella_agent.start_workflow()
        
        # Wait for processing to complete
        await asyncio.sleep(2)
    finally:
        # Clean up
        await stella_agent.stop_workflow()
        await broker.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Examples

The package includes several examples demonstrating different use cases:

- **Document Processor**: Process different document types through a workflow
- **Bulk Email Processor**: Send personalized emails to a list of users
- **State Memory Pipeline**: Collect, process, and analyze data with state tracking
- **Message Flow**: Create complex message flows between multiple agents
- **Multiple Producers**: Handle messages from multiple producer agents

Check the `examples/` directory for complete implementations.

## Documentation

For detailed documentation, see:

- [Agent System](docs/CORE_AGENT.md)

Additional documentation is coming soon!

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/stella-workflow.git
cd stella-workflow

# Install dependencies
pip install poetry
poetry install
```

### Testing

```bash
# Run all tests
poetry run pytest

# Run specific tests
poetry run pytest tests/test_workflow.py
```

### Linting

```bash
# Run linting
poetry run ruff check .

# Run formatting
poetry run ruff format .
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
