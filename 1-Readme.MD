# MR. PERFECT OS Workspace Review

## Overview
This workspace contains a cleaned Python project for **Mr. Perfect OS**, a CustomTkinter desktop agent that talks to a local OpenAI-compatible LLM server and can call registered tools for coding, files, web, OS, network, and package-management tasks.

## Current Workspace Structure
- `agent-app-17.py` — main GUI application
- `tool_registry.py` — decorator-based tool registry
- `tools_container.py` — loads and combines all tool mixins
- `agent_tools/` — canonical tool package
  - `code_tools.py`
  - `file_tools.py`
  - `network_tools.py`
  - `os_tools.py`
  - `system_tools.py`
  - `web_tools.py`
  - `winget_tools.py`
  - `__init__.py`
- `four_number_adder.py` — sample generated GUI app
- `requirements.txt` — Python dependencies
- `all-tools-names.txt` — active registered tool names
- `2-Project-Documentation.MD` — full project documentation
- `4-Tools-Reference.MD` — detailed tool reference
- `5-Cover-Image-Prompt.MD` — cover image prompt for project branding
- `CHANGELOG.MD` — documented workspace changes
- `tool-summary.json` — structured metadata for active tool registry
- `LICENSE` — current license notice
- `3-GitHub-Project-Description.MD` — GitHub/project description copy
- `6-Release-Checklist.MD` — release preparation checklist
- `7-License-Guide.MD` — license selection guidance
- `docs/INDEX.MD` — documentation entry page
- `docs/RELEASE-NOTES.MD` — release notes draft
- `project-cover.png` — main generated cover image
- `project-cover-corporate.png` — cleaner corporate variant
- `project-cover-portrait.png` — portrait documentation cover variant

## Main Features
- Local LLM agent loop with visible step-by-step console output
- Green response console
- Max agent steps set to 4
- Chat/session save and load support
- Tool execution with safer parsing and sanitization
- Better handling of markdown-corrupted filenames and code
- Smarter code generation templates for GUI and non-GUI tasks
- Automatic validation and smoke-test behavior for saved code
- File conflict handling when saving code or files

## Important Runtime Notes
### 1. Local LLM endpoint
The app is configured for:
- `http://127.0.0.1:5000/v1`

Make sure your local OpenAI-compatible server is running before launching the app.

### 2. Restart required after code changes
If you change tool files or the registry, fully restart the app so the updated tools reload in memory.

### 3. Canonical source layout
The project now uses the `agent_tools/` package as the main source of tool implementations.

## Registered Tools Summary
- Active registered tools: **106**
- Raw decorator definitions across files: **109**

Why the numbers differ:
- `create_code_file`
- `write_file`
- `run_file`

are defined in both `agent_tools/file_tools.py` and `agent_tools/code_tools.py`.
Because `agent_tools/code_tools.py` is imported after `agent_tools/file_tools.py`, its versions override the earlier registry entries.

See `all-tools-names.txt` for the active final list.

## Save Behavior / File Exists Handling
The workspace now supports safer save behavior.

### In code/file saving tools
If a target file already exists:
- default behavior: save is blocked with an error and a suggested new filename
- `auto_rename=True`: saves as `name_1.ext`, `name_2.ext`, etc.
- `overwrite=True`: replaces the existing file intentionally

### Recommended usage
- Use `auto_rename=True` when you want to avoid conflicts safely
- Use `overwrite=True` only when replacing the file is intended

## Coding Tooling Improvements
The coding workflow is now stronger than before:
- generalized `generate_code_template`
- automatic clean filename generation
- code validation before save
- optional smoke testing for safe non-GUI/non-server files
- `auto_correct_code` for common repairs
- better Tkinter cleanup
- improved final-response filename accuracy

## Example Run
To launch the main app:
```bash
python agent-app-17.py
```

To run the sample four-number GUI adder:
```bash
python four_number_adder.py
```

## Dependencies
See `requirements.txt`.

Install with:
```bash
pip install -r requirements.txt
```

For Playwright, also run:
```bash
python -m playwright install
```

## Optional/Template Dependencies
Some generated templates may use packages that are not required by the core app itself, for example:
- `requests`
- `beautifulsoup4`
- `flask`
- `fastapi`
- `uvicorn`

These are noted in `requirements.txt` as optional comments.

## Recommended Next Step
If you continue development later, the next good improvement would be:
- end-to-end regression testing for the agent loop and tool registry
- or a dedicated tool-test script that verifies all tool registrations at startup
