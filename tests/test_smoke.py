from __future__ import annotations

import asyncio
import json
import sys
import unittest
from types import SimpleNamespace

from google.genai import types

from campuspulse import mcp_server
from campuspulse.agent import CampusPulseAgent, _to_schema


class FakeModels:
    def __init__(self) -> None:
        self.calls = 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        last = contents[-1]
        has_function_response = any(
            getattr(part, "function_response", None)
            for part in (last.parts or [])
        )
        if has_function_response:
            content = types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text="Ближайший дедлайн по Raft уже в данных."
                    )
                ],
            )
        else:
            content = types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            name="get_deadlines",
                            args={"course": "Raft", "days": 7},
                        )
                    )
                ],
            )
        return SimpleNamespace(
            candidates=[SimpleNamespace(content=content)]
        )


class FakeClient:
    def __init__(self) -> None:
        self.models = FakeModels()


class TestCampusPulse(unittest.TestCase):
    def test_tools(self) -> None:
        courses = json.loads(mcp_server.list_courses())
        self.assertEqual(len(courses["records"]), 3)

        deadlines = json.loads(mcp_server.get_deadlines("Raft", 7))
        self.assertTrue(deadlines["records"])
        self.assertEqual(deadlines["records"][0]["course"], "CS310")

        events = json.loads(mcp_server.search_events("AI", 7))
        titles = [item["title"] for item in events["records"]]
        self.assertIn("GDG Astana: AI Night", titles)

        spots = json.loads(mcp_server.find_study_spot("silent,power,coffee"))
        self.assertTrue(spots["records"])

        missing = json.loads(mcp_server.find_study_spot("аптека"))
        self.assertEqual(missing["records"], [])

    def test_schema(self) -> None:
        schema = _to_schema(
            {
                "type": "object",
                "properties": {
                    "course": {"type": "string"},
                    "days": {"type": "integer"},
                },
                "required": ["course"],
            }
        )
        self.assertEqual(schema.type, types.Type.OBJECT)
        self.assertEqual(schema.properties["days"].type, types.Type.INTEGER)
        self.assertEqual(schema.required, ["course"])

    def test_agent_loop(self) -> None:
        agent = CampusPulseAgent(project="demo-project")
        fake = FakeClient()
        agent._client = fake

        result = agent.query("Что горит по Raft?")

        self.assertIn("Raft", result["answer"])
        self.assertEqual(fake.models.calls, 2)
        self.assertTrue(
            any(
                step["step"] == "tool"
                and step["tool"] == "get_deadlines"
                for step in result["trace"]
            )
        )
        self.assertIn("campuspulse://courses", result["sources"])

    def test_mcp_server(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def run() -> None:
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "campuspulse.mcp_server"],
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    self.assertEqual(
                        {item.name for item in tools},
                        {
                            "list_courses",
                            "get_deadlines",
                            "search_events",
                            "find_study_spot",
                        },
                    )
                    result = await session.call_tool(
                        "search_events",
                        {"query": "AI", "days": 7},
                    )
                    self.assertIn("AI Night", result.content[0].text)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
