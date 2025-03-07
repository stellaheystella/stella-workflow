from functools import wraps
import inspect
import logging
import asyncio
from typing import Dict, List, Any, Optional
from .workflow import stella_agent

logger = logging.getLogger(__name__)

class LoopController:
    """Controller for managing loop execution."""

    _loops = {}  # Dictionary to store loop instances by name

    def __init__(self, name: str, exit_condition: str = None, max_iterations: int = None):
        """Initialize the loop controller."""
        self.name = name
        self.exit_condition = exit_condition
        self.max_iterations = max_iterations
        self.agents = {}  # Dictionary to store agents by name
        self._agent_states = {}  # Dictionary to store agent states
        logger.debug(f"Created loop controller {name} with exit_condition={exit_condition}, max_iterations={max_iterations}")

    def add_agent(self, agent, position: int):
        """Add an agent to the loop at the specified position."""
        agent_name = f"{agent._agent_name}_iter_{position}"
        self.agents[agent_name] = agent
        logger.debug(f"Added agent {agent._agent_name} at position {position} to loop {self.name}")

    async def start(self) -> None:
        """Start the loop execution."""
        logger.info(f"Starting loop {self.name}")
        message_data = {'content': {}}
        iteration = 0

        while iteration < self.max_iterations:
            logger.debug(f"Starting iteration {iteration} of loop {self.name}")
            
            # Execute each agent in order
            for agent_name, agent in sorted(self.agents.items()):
                logger.debug(f"Creating wrapped agent {agent_name} with dependencies {agent._agents[agent._agent_name].get('depends_on', [])}")
                
                # Create wrapped agent for this iteration
                @wraps(agent)
                async def wrapped_agent(message_data):
                    """Wrap an agent to handle dependencies and state."""
                    logger.debug(f"Executing wrapped agent {agent_name}")
                    
                    # Initialize message_data if None
                    if message_data is None:
                        message_data = {'content': {}}

                    # Get dependencies for this agent
                    dependencies = agent._agents[agent._agent_name].get('depends_on', [])
                    
                    # Handle dependencies first to ensure we have initiator data
                    if dependencies:
                        for dep in dependencies:
                            if dep not in message_data.get('content', {}):
                                # Get the dependency's handler
                                dep_handler = agent._agents[dep]['handler']
                                # Execute dependency and update message data
                                try:
                                    dep_result = await dep_handler(message_data)
                                    if dep_result:
                                        if 'content' not in message_data:
                                            message_data['content'] = {}
                                        message_data['content'][dep] = dep_result
                                except Exception as e:
                                    logger.error(f"Error in dependency {dep}: {str(e)}")
                                    raise
                    
                    # Initialize agent state if needed
                    base_name = agent._agent_name.split('_iter_')[0]
                    if base_name not in self._agent_states:
                        # Initialize with default state including position
                        self._agent_states[base_name] = {
                            'count': 0,
                            'position': 0,
                            'data': [],
                            'batch_size': 1
                        }
                        
                        # If this is a batch processor and we have initiator data, use it
                        if base_name == 'batch_processor' and 'initiator' in message_data.get('content', {}):
                            initiator_data = message_data['content']['initiator']
                            self._agent_states[base_name].update({
                                'data': initiator_data.get('data', []),
                                'batch_size': initiator_data.get('batch_size', 1),
                                'position': 0
                            })
                    
                    # Set the agent's state
                    setattr(agent, 'state', self._agent_states[base_name])
                    
                    # Execute the agent's handler
                    try:
                        # Check if the agent function expects message_data
                        sig = inspect.signature(agent)
                        if len(sig.parameters) > 0:
                            result = await agent(message_data)
                        else:
                            result = await agent()
                            
                        # Update agent state after execution
                        self._agent_states[base_name] = getattr(agent, 'state', self._agent_states[base_name])
                        
                        # Update message data with result
                        if 'content' not in message_data:
                            message_data['content'] = {}
                        message_data['content'][base_name] = result
                        
                        return result
                    except Exception as e:
                        logger.error(f"Error in loop agent {agent_name}: {str(e)}")
                        raise

                # Execute the wrapped agent
                try:
                    logger.debug(f"Executing wrapped agent {agent_name}")
                    result = await wrapped_agent(message_data)  # Pass message_data to handler
                except Exception as e:
                    logger.error(f"Error executing agent {agent_name}: {str(e)}")
                    raise

            # Check exit condition after all agents have executed
            if self.exit_condition:
                try:
                    should_exit = eval(self.exit_condition, {'message': message_data})
                    if should_exit:
                        logger.info(f"Loop {self.name} exit condition met")
                        return
                except Exception as e:
                    logger.error(f"Error evaluating exit condition: {str(e)}")
                    raise

            iteration += 1
            if iteration >= self.max_iterations:
                logger.info(f"Loop {self.name} reached max iterations")
                break

        logger.info(f"Loop {self.name} finished")

def in_loop(loop_name: str, exit_condition: str, max_iterations: int = None, position: int = 0):
    """
    Decorator to add an agent to a loop.
    
    Args:
        loop_name: Name of the loop to add the agent to
        exit_condition: Python expression that evaluates to bool, determines when to exit loop
        max_iterations: Optional maximum number of iterations
        position: Position of the agent in the loop execution sequence
    """
    def decorator(agent):
        # Create loop controller if it doesn't exist
        if loop_name not in LoopController._loops:
            loop = LoopController(
                name=loop_name,
                exit_condition=exit_condition,
                max_iterations=max_iterations
            )
            LoopController._loops[loop_name] = loop
        else:
            loop = LoopController._loops[loop_name]
            
        # If agent is already decorated with stella_agent, add it to loop now
        if hasattr(agent, '_broker'):
            loop.add_agent(agent, position)
            agent._loop = loop
            return agent
            
        # If agent is not yet decorated with stella_agent, return a wrapper
        @wraps(agent)
        def wrapper(*args, **kwargs):
            # Add to loop after stella_agent decoration
            if not hasattr(wrapper, '_loop'):
                loop.add_agent(agent, position)
                wrapper._loop = loop
            return agent(*args, **kwargs)
            
        # Copy any existing attributes
        for attr in dir(agent):
            if not attr.startswith('__'):
                setattr(wrapper, attr, getattr(agent, attr))
                
        return wrapper
    return decorator