from abc import ABC, abstractmethod
import os
import asyncio
import json
import networkx as nx
import matplotlib.pyplot as plt
import logging
import pandas as pd
from typing import Any, Dict, List, Optional, Callable, Set, Union
from functools import wraps
import uuid
from datetime import datetime
from .utils import Colors
from .brokers import MessageBroker, BrokerFactory

# Disable Matplotlib debug logging
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)  # Also disable Pillow debug messages if present

# Create a custom formatter class
class ColoredFormatter(logging.Formatter):
    level_colors = {
        logging.DEBUG: Colors.DEBUG,
        logging.INFO: Colors.INFO,
        logging.WARNING: Colors.WARNING,
        logging.ERROR: Colors.ERROR,
        logging.CRITICAL: Colors.ERROR
    }

    def format(self, record):
        # Add color to the level name
        color = self.level_colors.get(record.levelno)
        if color:
            record.levelname = f"{color}{record.levelname}{Colors.ENDC}"
            record.msg = f"{color}{record.msg}{Colors.ENDC}"
        return super().format(record)

logger = logging.getLogger(__name__)

class stella_agent:
    _agents = {}
    _workflow_graph = nx.DiGraph()
    _broker = None
    _subscription_tasks = []
    
    def __init__(self, name=None, topic=None, depends_on=None, broker=None, 
                 condition=None):
        """Initialize the agent with the given parameters.
        
        Args:
            name (str): Name of the agent
            topic (str): Topic to publish/subscribe to
            depends_on (List[str], optional): List of agent names this agent depends on
            broker (MessageBroker): Message broker instance
            condition (str, optional): Condition for execution
        """
        # First check required parameters before any validation
        if name is None:
            raise ValueError("Agent name is required")
        if broker is None:
            raise ValueError("Broker is required")
        if topic is None:
            raise ValueError("Topic is required")
            
        # Now validate parameters
        self._validate_name(name)
        self._validate_topic(topic)
        self._validate_depends_on(depends_on)
        self._validate_condition(condition)
            
        self.name = name
        self.topic = topic
        self.depends_on = depends_on or []
        self._broker = broker
        stella_agent._broker = broker
        
        self._agents[name] = {
            'topic': topic,
            'depends_on': self.depends_on,
            'function': None,
            'handler': None,
            'condition': condition
        }
        
        for dep in self.depends_on:
            self._workflow_graph.add_edge(dep, name)

    def _validate_name(self, name):
        """Validate agent name"""
        if not isinstance(name, str):
            raise ValueError("Agent name must be a string")
        if not name:
            raise ValueError("Agent name cannot be empty")
        if name in self._agents:
            raise ValueError(f"Agent name '{name}' is already registered")

    def _validate_depends_on(self, deps):
        """Validate dependencies list"""
        if deps is not None:
            if not isinstance(deps, list):
                raise ValueError("depends_on must be a list of strings")
            if not all(isinstance(d, str) for d in deps):
                raise ValueError("depends_on must be a list of strings")

    def _validate_condition(self, cond):
        """Validate condition syntax"""
        if cond is not None:
            try:
                compile(cond, '<string>', 'eval')
            except SyntaxError:
                raise SyntaxError(f"Invalid condition syntax: {cond}")

    def _validate_topic(self, topic):
        """Validate topic name"""
        if not isinstance(topic, str):
            raise ValueError("Topic must be a string")
        if not topic:
            raise ValueError("Topic cannot be empty")
        # Add validation for topic format - for example, no special characters
        if any(c in topic for c in "/\\?#"):
            raise ValueError("Topic contains invalid characters")

    def __call__(self, func):
        """Decorator implementation"""
        self._agents[self.name]['function'] = func
        
        # Add properties to the function for test assertions
        func._agent_name = self.name
        func._broker = self._broker
        func._topic = self.topic
        func._depends_on = self.depends_on
        func._condition = self._agents[self.name]['condition']
        
        # Set _agents attribute on the function
        func._agents = self._agents
        
        # Add memory and state management methods to the function
        func.get_memory = self.get_memory
        func.set_memory = self.set_memory
        func.get_state = self.get_state
        func.update_state = self.update_state
        func.get_state_value = self.get_state_value
        
        # Store the decorated function in the handler field
        self._agents[self.name]['handler'] = func
        
        # Create the message handler
        message_handler = self.create_message_handler(func)
        self._agents[self.name]['message_handler'] = message_handler
        
        # Store initialization flag
        self._memory_initialized = False
        
        return func

    async def _ensure_memory_initialized(self):
        """Ensure memory is initialized for this agent."""
        if not self._memory_initialized:
            try:
                # Initialize with empty state if not exists
                try:
                    await self.get_memory('state')
                except KeyError:
                    await self.set_memory('state', {})
                self._memory_initialized = True
            except Exception as e:
                logger.warning(f"Could not initialize memory for agent {self.name}: {str(e)}")

    def create_message_handler(self, func):
        """Creates a message handler for this agent"""
        # Store received messages from dependencies
        dependency_messages = {}
        
        @wraps(func)
        async def handle_message(message_data=None):
            try:
                # Initialize memory if needed
                await self._ensure_memory_initialized()
                
                # For entry points
                if not self.depends_on:
                    logger.info(f"{self.name}: Starting entry point")
                    result = await func()
                    if result:
                        # Validate message format
                        if not isinstance(result, dict):
                            logger.warning(f"{self.name}: Invalid message format - must be dict")
                            return None
                        
                        logger.debug(f"{self.name}: Publishing message: {result}")
                        await self._broker.publish(self.topic, result, source=self.name)
                    return result

                # Skip if no message data
                if not message_data:
                    return None

                # Add orange color to dependency message logs
                logger.debug(f"{Colors.ORANGE}{self.name}: Processing message: {message_data}{Colors.ENDC}")
                
                # Skip if message is from self
                source = message_data.get('source')
                if source == self.name:
                    logger.debug(f"{self.name}: Skipping message from self")
                    return None

                # Store message from this dependency
                logger.info(f"{Colors.ORANGE}{self.name}: Received message from {source}{Colors.ENDC}")
                dependency_messages[source] = {
                    "source": source,
                    "data": message_data.get('data', {}),
                    "id": message_data.get('id'),
                    "received_at": datetime.now().isoformat()
                }
                logger.debug(f"{Colors.ORANGE}{self.name}: Current dependency messages: {dependency_messages}{Colors.ENDC}")
                
                # Check if we have all required dependencies
                logger.debug(f"{self.name}: Checking dependencies - have: {set(dependency_messages.keys())}, need: {set(self.depends_on)}")
                if set(dependency_messages.keys()).issuperset(set(self.depends_on)):
                    logger.info(f"{self.name}: Processing messages from all dependencies")
                    
                    # Create the message to pass to the agent function
                    merged_data = {
                        "source": source,
                        "data": message_data.get('data', {})
                    }
                    
                    # Also provide access to all dependency messages
                    merged_data["dependency_messages"] = dependency_messages
                    
                    logger.debug(f"{self.name}: Final merged data: {merged_data}")
                    
                    # Check condition if specified
                    if self._agents[self.name]['condition']:
                        logger.debug(f"{self.name}: Evaluating condition: {self._agents[self.name]['condition']}")
                        logger.debug(f"{self.name}: Evaluating condition with data: {merged_data}")
                        try:
                            # Extract the value being evaluated for better debugging
                            eval_context = {'message': merged_data}
                            condition_value = eval(self._agents[self.name]['condition'], eval_context)
                            logger.debug(f"{self.name}: Raw condition value before boolean conversion: {condition_value}, type: {type(condition_value)}")
                            condition_result = bool(condition_value)
                            logger.debug(f"{self.name}: Condition result after boolean conversion: {condition_result}")
                            logger.debug(f"{self.name}: Condition evaluation details - message content: {merged_data.get('data')}")
                            if not condition_result:
                                logger.info(f"{self.name}: Skipping execution due to condition")
                                dependency_messages.clear()
                                return None
                        except Exception as e:
                            logger.error(f"{self.name}: Error evaluating condition: {str(e)}")
                            logger.error(f"{self.name}: Error details - condition: {self._agents[self.name]['condition']}, data: {merged_data}")
                            dependency_messages.clear()
                            return None
                    
                    # Execute function with merged data
                    logger.info(f"{self.name}: Executing function with merged data")
                    result = await func(merged_data)
                    if result:
                        # Validate message format
                        if not isinstance(result, dict):
                            logger.warning(f"{self.name}: Invalid message format - must be dict")
                            return None
                        
                        # Wrap the result in the expected format with source
                        wrapped_result = {
                            "source": self.name,
                            "data": result
                        }
                        
                        logger.debug(f"{self.name}: Publishing message: {wrapped_result}")
                        await self._broker.publish(self.topic, wrapped_result, source=self.name)
                    return result
                else:
                    logger.debug(f"{self.name}: Waiting for messages from {set(self.depends_on) - set(dependency_messages.keys())}")
                    return None

            except Exception as e:
                logger.error(f"Error in {self.name}: {str(e)}")
                raise

        return handle_message

    @classmethod
    async def start_workflow(cls):
        """Start all agents with their dependencies"""
        if not cls._broker:
            raise ValueError("No broker configured")
            
        await cls._broker.connect()
        
        # First, set up all subscriptions
        subscription_tasks = []
        for name, agent in cls._agents.items():
            if agent['depends_on']:  # Subscribe agents with dependencies
                logger.info(f"Starting agent {name} listening for messages from {agent['depends_on']}")
                task = asyncio.create_task(
                    cls._broker.subscribe(
                        agent['topic'],
                        agent['message_handler']
                    )
                )
                subscription_tasks.append(task)
        
        # Wait a moment for subscriptions to be ready
        await asyncio.sleep(1)
        
        # Then trigger entry points
        for name, agent in cls._agents.items():
            if not agent['depends_on']:  # Execute entry point agents
                logger.info(f"Executing entry point agent: {name}")
                task = asyncio.create_task(agent['message_handler'](None))
                cls._subscription_tasks.append(task)
        
        return cls._subscription_tasks

    @classmethod
    async def stop_workflow(cls):
        """Stop the workflow and cleanup"""
        logger.info("Stopping workflow")
        if hasattr(cls, '_subscription_tasks'):
            # Cancel all subscription tasks
            for task in cls._subscription_tasks:
                task.cancel()
            await asyncio.gather(*cls._subscription_tasks, return_exceptions=True)
        await cls._broker.close()
        logger.info("Workflow stopped")

    @classmethod
    def visualise_workflow(cls):
        """Visualize the workflow using networkx"""
        logger.info("Generating workflow visualization")
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(cls._workflow_graph)
        nx.draw(
            cls._workflow_graph, 
            pos, 
            with_labels=True,
            node_color='lightblue',
            node_size=2000,
            font_size=10,
            font_weight='bold'
        )
        plt.title("Workflow DAG")
        plt.show()
        logger.info("Workflow visualization complete")

    @classmethod
    def clear_agents(cls):
        """Clear all registered agents"""
        cls._agents.clear()
        cls._workflow_graph.clear()
        cls._broker = None
        cls._subscription_tasks.clear()

    @classmethod
    def get_agents(cls):
        """Get all registered agents
        
        Returns:
            Dict: Dictionary of registered agents
        """
        return cls._agents

    async def get_memory(self, key: str) -> Any:
        """Get a value from agent memory.
        
        Args:
            key (str): The key to retrieve
            
        Returns:
            Any: The stored value, or raises KeyError if not found
            
        Raises:
            KeyError: If the key doesn't exist in memory
            RuntimeError: If no broker is configured
        """
        if not hasattr(self, '_broker') or not self._broker:
            raise RuntimeError("No broker configured")
            
        return await self._broker.get_memory(self.name, key)

    async def set_memory(self, key: str, value: Any) -> None:
        """Set a value in agent memory.
        
        Args:
            key (str): The key to store
            value (Any): The value to store (must be JSON serializable)
            
        Raises:
            RuntimeError: If no broker is configured
        """
        if not hasattr(self, '_broker') or not self._broker:
            raise RuntimeError("No broker configured")
            
        await self._broker.set_memory(self.name, key, value)

    async def get_state(self) -> Dict:
        """Get the agent's current state.
        
        Returns:
            Dict: The current state dictionary
            
        Note:
            Creates empty state if none exists
        """
        try:
            return await self.get_memory('state')
        except KeyError:
            await self.set_memory('state', {})
            return {}
            
    async def update_state(self, **kwargs) -> None:
        """Update the agent's state with new values.
        
        Args:
            **kwargs: Key-value pairs to update in the state
            
        Example:
            await agent.update_state(counter=5, status="running")
        """
        current_state = await self.get_state()
        current_state.update(kwargs)
        await self.set_memory('state', current_state)
        
    async def get_state_value(self, key: str, default: Any = None) -> Any:
        """Get a specific value from the agent's state.
        
        Args:
            key: The state key to retrieve
            default: Value to return if key doesn't exist
            
        Returns:
            The value for the key, or the default if not found
        """
        state = await self.get_state()
        return state.get(key, default)

