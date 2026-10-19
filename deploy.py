from __future__ import annotations

import os

import vertexai
from vertexai import agent_engines

from campuspulse.agent import CampusPulseAgent


def main() -> None:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    bucket = os.environ["STAGING_BUCKET"]

    vertexai.init(
        project=project,
        location=location,
        staging_bucket=bucket,
    )

    app = CampusPulseAgent(
        project=project,
        location=location,
    )

    remote = agent_engines.create(
        agent_engine=app,
        requirements=[
            "google-cloud-aiplatform[agent_engines]>=1.88.0",
            "google-genai>=1.30.0",
            "mcp>=1.9.0,<2",
            "tzdata>=2024.1",
        ],
        extra_packages=["./campuspulse"],
        display_name="campuspulse-ai",
        description=(
            "CampusPulse AI: student assistant with MCP tools "
            "on Vertex AI Agent Engine."
        ),
    )

    print("AGENT_ENGINE_RESOURCE=" + remote.resource_name)


if __name__ == "__main__":
    main()
