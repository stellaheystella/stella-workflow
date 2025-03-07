"""LLM implementations for testing purposes only."""
import json
from openai import AsyncOpenAI
from stella_workflow.auto import LLMInterface

class OpenAILLM(LLMInterface):
    """OpenAI implementation of LLMInterface for testing."""
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def generate_plan(self, system_prompt: str, user_prompt: str, schema: dict) -> str:
        response = await self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{user_prompt}\n\nResponse should match this JSON schema:\n{json.dumps(schema, indent=2)}"}
            ]
        )
        return response.choices[0].message.content

class MockLLM(LLMInterface):
    """Mock implementation of LLMInterface for testing."""
    def __init__(self):
        self.next_function = "test_function"  # Default function
    
    def set_next_function(self, function_name: str):
        """Set the function name to return in the next plan"""
        self.next_function = function_name
    
    async def generate_plan(self, system_prompt: str, user_prompt: str, schema: dict) -> str:
        return json.dumps({
            "function_calls": [
                {
                    "function_name": self.next_function,
                    "reason": "Testing function execution",
                    "order": 1
                }
            ]
        }) 