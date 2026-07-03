import unittest
from unittest.mock import AsyncMock, patch
import httpx
import json
from framework.ai.base import Message, Role, ToolCall
from framework.ai.gemini import GeminiProvider

class TestBug1GeminiName(unittest.IsolatedAsyncioTestCase):
    async def test_tool_message_has_name(self):
        # Bug 1: Gemini provider crashed because it accessed m.name which didn't exist.
        # This test confirms that Role.TOOL messages now successfully provide the 'name' field
        # to the Gemini functionResponse protocol.
        
        provider = GeminiProvider(api_key="fake_key")
        messages = [
            Message(Role.USER, "What's the weather?"),
            Message(Role.ASSISTANT, "Calling weather tool...", tool_calls=[
                ToolCall(id="1", name="get_weather", arguments={"location": "London"})
            ]),
            Message(
                Role.TOOL, 
                content='{"temp": 20}', 
                tool_call_id="1", 
                name="get_weather" # This is the field we added
            )
        ]
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(spec=httpx.Response)
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "It's 20C in London."}]}}]
            }
            
            await provider.chat(messages)
            
            # Check the payload sent to Gemini
            args, kwargs = mock_post.call_args
            payload = kwargs["json"]
            
            # Find the tool message in the payload
            # contents -> [{role: user, parts: [{text}]}, {role: model, parts: [{functionCall}]}, {role: function, parts: [{functionResponse}]}]
            tool_content = payload["contents"][2]
            self.assertEqual(tool_content["role"], "function")
            self.assertEqual(tool_content["parts"][0]["functionResponse"]["name"], "get_weather")
            self.assertEqual(tool_content["parts"][0]["functionResponse"]["response"]["result"], '{"temp": 20}')

if __name__ == "__main__":
    unittest.main()
