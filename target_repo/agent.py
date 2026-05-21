import os
import subprocess
from typing import TypedDict, List

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

# 2. Tool to check pytest
def run_pytest(target_dir: str) -> tuple[bool, str]:
    """Runs pytest and returns (passed: bool, stdout/stderr: str)"""
    result = subprocess.run(["pytest"], cwd=target_dir, capture_output=True, text=True)
    return (result.returncode == 0), result.stdout + "\n" + result.stderr


# 3. LangGraph Nodes
# Python function that accepts current STATE, performs actions (calling LLM) returns updated STATE
# Node 1: Locate buggy file

def locate_file_node(state: AgentState) -> AgentState:
    # Here, we list all files in state['target_dir'] and present them to the LLM.
    # We ask the LLM: "Given the issue: 'Calculate average crashes on empty lists', which file is buggy?"
    # The LLM responds: "calculator.py"
    # We load that file's contents into the state.
    state["target_file"] = "calculator.py"  # In practice, LLM fills this.
    
    with open(os.path.join(state["target_dir"], state["target_file"]), "r") as f:
        state["current_code"] = f.read()
        
    return state

# Node 2: Propose Code fix 
def propose_fix_node(state: AgentState) -> AgentState:
    # We prompt the LLM:
    # "Here is the issue: {issue_description}. Here is the current code: {current_code}. 
    #  If available, here is the error: {test_output}. Fix the code."
    
    # After receiving the response, we write the code back to the file:
    fixed_code = "# Code written by the LLM..." 
    
    with open(os.path.join(state["target_dir"], state["target_file"]), "w") as f:
        f.write(fixed_code)
        
    state["current_code"] = fixed_code
    state["iteration"] += 1
    return state


# Node 3: Test the fix
def test_fix_node(state: AgentState) -> AgentState:
    passed, output = run_pytest(state["target_dir"])
    state["test_output"] = output
    state["test_passed"] = passed
    return state

# Define Router/Conditional Edges
def router(state: AgentState):
    if state["test_passed"]:
        return "create_pr"
    
    if state["iteration"] < state["max_iterations"]:
        return "propose_fix"  # Loop back to fix the code with the error logs!
        
    return "fail"