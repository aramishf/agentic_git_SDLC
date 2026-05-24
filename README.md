# Git SDLC Agentic AI

An autonomous AI coding agent built with LangGraph and the Google GenAI SDK that acts as an automated software engineer. 

### Key Features
* **Automated Debugging:** When given a bug report, the agent automatically scans the project, identifies the file causing the issue, rewrites the code to fix the bug, and runs the unit tests to prove the fix works.
* **Autonomous Workflow:** Implements a stateful, multi-node workflow that ingests issue descriptions, parses local codebases, injects code fixes, and executes isolated pytest suites to verify correctness.
* **Simulation Mode:** Engineered with a resilient fallback system ("Mock/Simulation mode") that allows the agent's workflow logic to be tested and demonstrated end-to-end even when live API keys are unavailable.
* **Environment Automation:** Automatically scopes test execution within isolated Python virtual environments to ensure secure and accurate local testing.

### Tech Stack
* Python
* LangGraph
* Google GenAI SDK (Gemini)
* Pytest
