import os
import subprocess
import sys
from typing import TypedDict, List
from google import genai
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class MockResponse:
    def __init__(self, text):
        self.text = text

class MockModels:
    def generate_content(self, model, contents, **kwargs):
        prompt = str(contents)
        if "Identify which file contains the bug" in prompt:
            print("[Mock LLM] Identifying buggy file...")
            return MockResponse("calculator.py")
        elif "Fix the bug in the file" in prompt or "propose_fix" in prompt:
            print("[Mock LLM] Generating bug fix...")
            return MockResponse("""```python
def calculate_average(numbers):
    # BUG: This will raise ZeroDivisionError if numbers is empty.
    # The requirement is: return 0.0 for empty lists.
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)
```""")
        else:
            return MockResponse("")

class MockClient:
    def __init__(self):
        self.models = MockModels()

# Initialize the Gemini client or fallback to MockClient
client = None
try:
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        client = genai.Client()
except Exception as e:
    pass

if not client:
    print("[Agent Setup] No GEMINI_API_KEY or GOOGLE_API_KEY detected in the environment.")
    print("[Agent Setup] Initializing in Simulation/Mock Mode using MockClient.")
    client = MockClient()

# 1. State Definition (The memory of the agent)
class AgentState(TypedDict):
    issue_description: str
    target_dir: str
    target_file: str      # The file we decide needs fixing
    current_code: str     # The code currently inside that file
    test_output: str      # Stdout/stderr from running pytest
    test_passed: bool     # Flag indicating if the tests succeeded
    iteration: int        # Counter for retry loops
    max_iterations: int   # Limit to prevent infinite loops
    branch_name: str      # The git branch created for this issue


# 2. Tool to run repository verification tests
def run_verification_tests(target_dir: str) -> tuple[bool, str]:
    """Runs verification tests and returns (passed: bool, stdout/stderr: str)"""
    test_cmd_str = os.environ.get("TEST_COMMAND") or "pytest"
    test_cmd = test_cmd_str.split()
    if len(test_cmd) > 0 and test_cmd[0] == "pytest":
        test_cmd = [sys.executable, "-m", "pytest"]
    print(f"[Verification] Running test command: {' '.join(test_cmd)} in {target_dir}")
    result = subprocess.run(test_cmd, cwd=target_dir, capture_output=True, text=True)
    return (result.returncode == 0), result.stdout + "\n" + result.stderr


# 3. LangGraph Nodes

def locate_file_node(state: AgentState) -> AgentState:
    """
    Node 1: Analyze the issue description and select the buggy file to fix.
    """
    if isinstance(client, MockClient):
        print("[Node 1: Locate File] Running in mock/simulation mode.")
        
    # 1. Get a list of files in the target directory dynamically
    files = []
    for root, _, filenames in os.walk(state["target_dir"]):
        for filename in filenames:
            if "__pycache__" in root or ".git" in root or ".venv" in root or ".github" in root or filename.endswith('.pyc') or filename == "agent.py" or not filename.endswith('.py'):
                continue
            rel_path = os.path.relpath(os.path.join(root, filename), state["target_dir"])
            files.append(rel_path)
    
    files_str = "\n".join(files)
    
    # 2. Build the prompt for the LLM
    prompt = f"""
You are an AI software engineer triaging a bug report.

Bug Report: "{state['issue_description']}"

Files in the repository:
{files_str}

Identify which file contains the bug or needs to be modified to fix this issue.
Respond with ONLY the filename (including its path relative to target_dir). Do not write any markdown code blocks, explanation, or extra characters.
Example: calculator.py
"""
    
    # 3. Call the Gemini model
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    
    # 4. Clean up the response and save it to State
    target_file = response.text.strip().replace('`', '').replace('"', '').replace("'", "")
    state["target_file"] = target_file
    
    # 5. Read the target file's current content and load into State
    file_path = os.path.join(state["target_dir"], target_file)
    with open(file_path, "r") as f:
        state["current_code"] = f.read()
        
    print(f"[Node 1: Locate File] Analyzer decided to modify: {target_file}")
    return state


def propose_fix_node(state: AgentState) -> AgentState:
    """
    Node 2: Propose code fix for the target file based on the issue and test feedback.
    """
    if isinstance(client, MockClient):
        print("[Node 2: Propose Fix] Running in mock/simulation mode.")

    # Build feedback context if tests have run and failed previously
    feedback_context = ""
    if state.get("test_output"):
        feedback_context = f"""
Your previous attempt failed the tests with this output:
{state['test_output']}
Please analyze this error trace and fix the code accordingly.
"""
        
    # Build prompt for code generation
    prompt = f"""
You are an expert developer. Fix the bug in the file `{state['target_file']}`.

Issue Description:
{state['issue_description']}

Current File Content:
```python
{state['current_code']}
```
{feedback_context}

Provide the ENTIRE updated content of the file. 
Wrap the python code in a single markdown code block starting with ```python.
Do not output any explanation or commentary outside the code block.
"""
    
    # Call Gemini model
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    
    # Extract python code block from the markdown response
    raw_text = response.text
    if "```python" in raw_text:
        new_code = raw_text.split("```python")[1].split("```")[0].strip()
    elif "```" in raw_text:
        new_code = raw_text.split("```")[1].split("```")[0].strip()
    else:
        new_code = raw_text.strip()
        
    # Write the new code back to the target file
    file_path = os.path.join(state["target_dir"], state["target_file"])
    with open(file_path, "w") as f:
        f.write(new_code)
        
    state["current_code"] = new_code
    state["iteration"] += 1
    
    print(f"[Node 2: Propose Fix] Code written to {state['target_file']} (Iteration {state['iteration']})")
    return state


def test_fix_node(state: AgentState) -> AgentState:
    """
    Node 3: Run verification tests on the target directory and capture the output.
    """
    print(f"[Node 3: Test Fix] Running tests in {state['target_dir']}...")
    passed, output = run_verification_tests(state["target_dir"])
    state["test_output"] = output
    state["test_passed"] = passed
    
    status = "PASSED" if passed else "FAILED"
    print(f"[Node 3: Test Fix] Test status: {status}")
    return state


def create_pull_request_node(state: AgentState) -> AgentState:
    """
    Node 4: Stage changes, commit, push branch, and open a Pull Request on GitHub.
    """
    target_dir = state["target_dir"]
    target_file = state["target_file"]
    branch_name = state["branch_name"]
    issue_num = os.environ.get("ISSUE_NUMBER") or "demo"
    
    # If running locally / simulation mode without GITHUB_WORKSPACE, skip actual Git push/PR
    if not os.environ.get("GITHUB_WORKSPACE"):
        print("[Node 4: PR Creation] Skipping actual Git push and PR creation in local simulation.")
        return state

    print(f"[Node 4: PR Creation] Staging changes in {target_file}...")
    subprocess.run(["git", "add", target_file], cwd=target_dir)
    
    commit_msg = f"fix: resolve issue #{issue_num}\n\nAutomated fix proposed by AI SDLC Agent."
    print(f"[Node 4: PR Creation] Committing changes on branch {branch_name}...")
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=target_dir)
    
    print(f"[Node 4: PR Creation] Pushing branch {branch_name} to origin...")
    subprocess.run(["git", "push", "origin", branch_name], cwd=target_dir)
    
    # Build PR title and body using LLM
    pr_title = f"AI Auto-Fix: Issue #{issue_num}"
    pr_body = f"""### AI-Generated Bounding Box / Bug Fix

This Pull Request was automatically generated by the **AI SDLC Agent** to address issue #{issue_num}.

#### Issue Context:
`{state['issue_description']}`

#### Proposed Fix:
* Fixed file: `{target_file}`
* Test Execution Output:
```text
{state['test_output'][:1500]}
```
"""
    
    print(f"[Node 4: PR Creation] Spawning gh CLI to create Pull Request...")
    # Setup environment for gh cli containing GITHUB_TOKEN
    env = os.environ.copy()
    subprocess.run([
        "gh", "pr", "create", 
        "--title", pr_title, 
        "--body", pr_body, 
        "--head", branch_name, 
        "--base", "main"
    ], cwd=target_dir, env=env)
    
    print(f"[Node 4: PR Creation] PR successfully created for branch {branch_name}!")
    return state


# 4. Define Router/Conditional Edges
def router(state: AgentState):
    """
    Router: Decide whether to loop back for a fix, create a PR, or fail.
    """
    if state["test_passed"]:
        print("[Router] Tests passed! Transitioning to Success.")
        return "create_pr"
    
    if state["iteration"] < state["max_iterations"]:
        print(f"[Router] Tests failed. Retrying (Iteration {state['iteration']}/{state['max_iterations']})...")
        return "propose_fix"
        
    print("[Router] Max iterations reached without passing tests. Transitioning to Failure.")
    return "fail"


# 5. LangGraph Workflow Definition
workflow = StateGraph(AgentState)

# Add our nodes to the graph
workflow.add_node("locate_file", locate_file_node)
workflow.add_node("propose_fix", propose_fix_node)
workflow.add_node("test_fix", test_fix_node)
workflow.add_node("create_pull_request", create_pull_request_node)

# Set entry point
workflow.set_entry_point("locate_file")

# Define edges
workflow.add_edge("locate_file", "propose_fix")
workflow.add_edge("propose_fix", "test_fix")

# Define conditional edges from test_fix
workflow.add_conditional_edges(
    "test_fix",
    router,
    {
        "create_pr": "create_pull_request",
        "propose_fix": "propose_fix",
        "fail": END
    }
)
workflow.add_edge("create_pull_request", END)

# Compile the workflow graph
app = workflow.compile()


if __name__ == "__main__":
    # Check if running in mock/simulation mode
    if isinstance(client, MockClient):
        print("Notice: No Gemini API key detected. Running in Simulation/Mock Mode.")
    elif not client:
        print("Warning: Neither GEMINI_API_KEY nor GOOGLE_API_KEY environment variable is set.")
        print("Please create a '.env' file in this directory or set the environment variable, e.g.:")
        print("  export GEMINI_API_KEY='your_api_key'")
        exit(1)
        
    # Define the target directory (use GITHUB_WORKSPACE in GitHub Action runners, or script directory locally)
    target_dir = os.environ.get("GITHUB_WORKSPACE") or os.path.dirname(os.path.abspath(__file__))
    
    # Read issue description dynamically from environment if set (e.g. in GitHub Actions)
    issue_description = os.environ.get("ISSUE_BODY") or os.environ.get("ISSUE_TITLE") or "Calculate average crashes on empty lists"
    
    # Read issue number and setup git branch
    issue_num = os.environ.get("ISSUE_NUMBER") or "demo"
    import time
    timestamp = int(time.time())
    branch_name = f"ai-fix/issue-{issue_num}-{timestamp}"
    
    # Run git checkout/branch setup if GITHUB_WORKSPACE (GitHub Action runner) is detected
    if os.environ.get("GITHUB_WORKSPACE"):
        print(f"[Git Setup] Configuring git user for branch creation...")
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=target_dir)
        subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=target_dir)
        print(f"[Git Setup] Creating new branch: {branch_name}...")
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=target_dir)

    initial_state = AgentState(
        issue_description=issue_description,
        target_dir=target_dir,
        target_file="",
        current_code="",
        test_output="",
        test_passed=False,
        iteration=0,
        max_iterations=3,
        branch_name=branch_name
    )
    
    print("Starting agent graph execution...")
    final_state = app.invoke(initial_state)
    print("\n--- Execution Finished ---")
    print(f"Final Test Passed: {final_state['test_passed']}")
    print(f"Final Iteration: {final_state['iteration']}")
