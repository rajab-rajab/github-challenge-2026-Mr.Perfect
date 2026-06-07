# GitHub Project Description — MR. PERFECT OS

## Project Title
**MR. PERFECT OS**

## One-Line Description
A local AI agent desktop app with a tool-driven architecture for coding, automation, files, web, OS, network, and package-management tasks.

## Short Description
MR. PERFECT OS is a CustomTkinter-based desktop AI agent that connects to a local OpenAI-compatible model server and executes structured tool actions for coding, file handling, web intelligence, system operations, and automation workflows.

## Medium Description
MR. PERFECT OS is an experimental desktop agentic operating environment built in Python with CustomTkinter. It uses a decorator-based tool registry and a modular tool package to let a local LLM reason step by step, call tools, observe results, and respond through a visible operator console.

The project includes a large active toolset for code generation, code repair, file management, web tasks, OS and network inspection, and Windows package-management actions. It also includes safer parsing, filename sanitization, validation before save, smoke testing for safe scripts, and fallback code-correction workflows.

## Long Description
MR. PERFECT OS is a local-first AI agent desktop application designed to combine a visible agent loop with a broad tool ecosystem. The interface is built using CustomTkinter and provides a chat area, a green response console, session save/load controls, and a step-by-step operator view of the model's reasoning flow.

The system is built around three main layers:
- a GUI layer (`agent-app-17.py`)
- a centralized tool registry (`tool_registry.py`)
- a modular tool container (`tools_container.py`) that aggregates tool mixins from `agent_tools/`

The active toolset covers:
- code generation and code correction
- syntax validation and smoke testing
- file and directory management
- web search and browsing helpers
- OS and system inspection
- network utilities
- Windows service and package-management actions

MR. PERFECT OS is intended as a developer-focused agent platform for experimenting with local AI automation, agent tool orchestration, and desktop task execution.

## Key Features
- Local OpenAI-compatible LLM integration
- Visible step-by-step agent execution
- Tool registry with modular mixin architecture
- 100+ active registered tools
- Code generation, repair, and validation workflow
- File conflict handling with overwrite and auto-rename support
- GUI and non-GUI project scaffolding support
- Session save/load support
- Cleaned documentation and asset structure

## Suggested GitHub About Text
**Local AI agent desktop app with 100+ tools for coding, automation, files, web, network, and system tasks.**

## Suggested Topics / Tags
- ai-agent
- local-llm
- python
- customtkinter
- desktop-app
- automation
- coding-agent
- tool-calling
- agentic-ai
- developer-tools
- openai-compatible
- windows-tools

## Suggested Repository Subtitle Variants
1. Elite Local AI Agent for Coding and Automation
2. Tool-Driven Desktop AI Agent Platform
3. Local Agentic OS for Developers and Automation
4. Desktop LLM Agent with Coding and System Tools

## Suggested Social / Portfolio Pitch
MR. PERFECT OS is a local desktop AI agent platform that combines step-based reasoning, tool calling, code generation, and operator-visible execution in a CustomTkinter interface.
