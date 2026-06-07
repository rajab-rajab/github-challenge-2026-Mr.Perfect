# MR. PERFECT OS — Full Project Documentation

## 1. Project Summary
MR. PERFECT OS is a desktop AI agent application built with **CustomTkinter**. It connects to a **local OpenAI-compatible LLM server** and gives the model controlled access to a large set of tools for coding, files, web, OS, network, and Windows package-management tasks.

The project is designed around:
- a visible multi-step agent loop
- a tool registry with decorator-based registration
- a canonical tool package in `agent_tools/`
- safer code generation, validation, save, and recovery behavior

---

## 2. Current Workspace Layout

```text
agent-app-17.py
agent_tools/
  __init__.py
  code_tools.py
  file_tools.py
  network_tools.py
  os_tools.py
  system_tools.py
  web_tools.py
  winget_tools.py
tool_registry.py
tools_container.py
four_number_adder.py
1-Readme.MD
2-Project-Documentation.MD
4-Tools-Reference.MD
all-tools-names.txt
requirements.txt
```

### Main files
- `agent-app-17.py` — GUI and agent loop
- `tool_registry.py` — tool registration system
- `tools_container.py` — aggregates mixins into one `AgentTools` object
- `agent_tools/*.py` — canonical tool implementations
- `four_number_adder.py` — example generated GUI output

---

## 3. Main Architecture

### 3.1 GUI Layer
The GUI is built in `agent-app-17.py` using `customtkinter`.

Main responsibilities:
- chat input/output
- response console output
- system status updates
- session save/load buttons
- visible step-by-step thinking and action logs

### 3.2 Brain / Agent Loop
`MrPerfectBrain` handles:
- building the system prompt
- sending messages to the local LLM
- parsing `STEP`, `THOUGHT`, `ACTION`, and `FINAL RESPONSE`
- sanitizing tool arguments and outputs
- executing tools through the registry
- handling recovery messages when generation/save/validation fails

### 3.3 Tool Registry
`tool_registry.py` provides:
- `@tool_registry.register(...)`
- centralized storage of tool metadata
- tool lookup for the agent
- formatted prompt listing of all tools

### 3.4 Tool Container
`tools_container.py` defines:
- `SafeCalculator`
- `AgentTools`

`AgentTools` inherits all mixins and provides shared state:
- `gui`
- `tavily`
- `BASE_DIR`
- protected program names
- protected self-file names

---

## 4. Tool System Design

### 4.1 Canonical package
The canonical tool source is:
- `agent_tools/`

### 4.2 Active registered tool count
- Active registered tools: **106**

### 4.3 Raw decorator count
- Raw decorator definitions across files: **109**

Why the count differs:
- `create_code_file`
- `write_file`
- `run_file`

exist in more than one module, and later imports override earlier registry entries.

### 4.4 Tool categories
Tools are grouped by module:
- `code_tools.py`
- `file_tools.py`
- `network_tools.py`
- `os_tools.py`
- `system_tools.py`
- `web_tools.py`
- `winget_tools.py`

See `4-Tools-Reference.MD` for the full reference.

---

## 5. Agent Workflow

### 5.1 Request lifecycle
1. User enters a request in the GUI
2. Request is appended to chat history
3. Agent builds system prompt with active tools
4. LLM responds with structured output
5. Agent extracts:
   - `STEP:`
   - `THOUGHT:`
   - `ACTION:`
   - `FINAL RESPONSE:`
6. If an action exists, the corresponding tool runs
7. Observation is appended back into model context
8. Agent continues up to max steps

### 5.2 Current step limit
- `MAX_AGENT_STEPS = 4`

### 5.3 Console behavior
The response console shows:
- current step
- thinking text
- chosen action
- observation/result
- final response

---

## 6. Code Generation Workflow

The coding pipeline has been hardened significantly.

### 6.1 Template generation
`generate_code_template` can now generate starter code for many categories:
- Tkinter GUI
- calculator
- dynamic adder GUIs
- todo apps
- text editors
- Flask/FastAPI APIs
- web servers
- scrapers
- SQLite starters
- CLI starters
- JavaScript starters
- HTML/CSS/SQL starters
- generic fallbacks

### 6.2 Save pipeline
`create_code_file` now supports:
- content cleanup
- filename cleanup
- filename auto-generation
- file-exists handling
- syntax validation
- limited auto-repair
- smoke testing for safe non-GUI scripts

### 6.3 Auto-correction
`auto_correct_code` was added to help repair code after errors.

### 6.4 File conflict handling
When saving a file:
- if the file does not exist → save normally
- if the file exists:
  - default: block and suggest a new filename
  - `auto_rename=True`: save as `name_1.ext`, `name_2.ext`, etc.
  - `overwrite=True`: replace existing file intentionally

---

## 7. Important Configuration

### 7.1 Local LLM endpoint
Configured in `agent-app-17.py`:
- `LOCAL_LLM_URL = "http://127.0.0.1:5000/v1"`
- `LOCAL_MODEL = "GEMMA 4"`

### 7.2 Workspace base directory
Set through `AgentTools` in `tools_container.py`:
- `MR_PERFECT_BASE_DIR` environment variable if present
- otherwise current working directory

### 7.3 Tavily
If `TAVILY_API_KEY` is available, web tools can use Tavily.
Otherwise fallback behavior is used where available.

---

## 8. Dependencies

Core dependencies are listed in `requirements.txt`.

Main runtime dependencies:
- `customtkinter`
- `openai`
- `psutil`
- `tavily-python`
- `playwright`

Optional dependencies may be needed for generated templates:
- `requests`
- `beautifulsoup4`
- `flask`
- `fastapi`
- `uvicorn`

---

## 9. How to Run

### 9.1 Install dependencies
```bash
pip install -r requirements.txt
```

If using Playwright browsing:
```bash
python -m playwright install
```

### 9.2 Start local model server
Make sure your local OpenAI-compatible server is running at:
```text
http://127.0.0.1:5000/v1
```

### 9.3 Launch the application
```bash
python agent-app-17.py
```

### 9.4 Run sample generated app
```bash
python four_number_adder.py
```

---

## 10. Current Strengths
- cleaner canonical package structure
- visible thinking and steps in console
- safer tool-call parsing
- improved filename and code sanitization
- stronger code generation support
- validation before save
- smoke testing for suitable scripts
- file conflict handling
- larger toolset than before

---

## 11. Known Limitations
- the agent cannot guarantee perfect code for every request
- GUI apps are not auto-run by default to avoid timeout problems
- some generated templates may still require manual refinement
- duplicate tool names still exist across some modules, though active registry behavior is understood and documented
- Windows-specific tools depend on Windows environment and available system commands
- browser tooling depends on Playwright installation

---

## 12. Troubleshooting

### Problem: old behavior still appears after code changes
**Cause:** old code is still loaded in memory.

**Fix:**
- fully close the app
- restart `agent-app-17.py`

### Problem: generated filename in final response is wrong
**Fix:**
- ensure the app was restarted after recent changes
- the agent now tries to reuse the exact saved filename from tool observations

### Problem: file save fails because file exists
**Fix:**
- use a new filename
- or use `auto_rename=True`
- or use `overwrite=True` if replacement is intended

### Problem: GUI code times out when run automatically
**Fix:**
- run GUI files manually from terminal
- this is expected behavior for long-running windows

### Problem: Playwright browsing fails
**Fix:**
```bash
python -m playwright install
```

### Problem: web tools have limited results
**Fix:**
- configure `TAVILY_API_KEY`
- restart app after environment changes

---

## 13. Documentation Files
This project now includes:
- `1-Readme.MD` — workspace summary
- `2-Project-Documentation.MD` — full project documentation
- `4-Tools-Reference.MD` — complete tool reference
- `all-tools-names.txt` — active tool names only
- `requirements.txt` — dependency list

---

## 14. Maintenance Advice
Recommended maintenance practices:
- keep `agent_tools/` as the only canonical tool implementation package
- restart the app after tool edits
- periodically verify active registry count
- test critical tools after refactors
- keep documentation updated whenever tool behavior changes
