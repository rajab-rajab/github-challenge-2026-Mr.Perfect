"""
MR. PERFECT OS - Tool Registry System

This module provides a centralized decorator-based registry to bridge
Python functions with the LLM's action-taking capabilities.
"""


class ToolRegistry:
    def __init__(self):
        # Stores tool metadata:
        # {
        #   "tool_name": {
        #       "function": callable,
        #       "description": str,
        #       "args_description": str,
        #   }
        # }
        self._tools = {}

    def register(self, name=None, description="", args_description=""):
        """
        Decorator to register a function as an agent tool.

        Args:
            name: The name the LLM will use to call this tool.
            description: A clear explanation of what the tool does.
            args_description: Expected arguments, for example 'filepath, content'.
        """

        def decorator(func):
            tool_name = name or func.__name__
            self._tools[tool_name] = {
                "function": func,
                "description": description,
                "args_description": args_description,
            }
            return func

        return decorator

    def get_tool(self, name):
        """Retrieve a specific tool's metadata by name."""
        return self._tools.get(name)

    def get_all_tools(self):
        """Return the full dictionary of registered tools."""
        return self._tools

    def get_prompt_list(self):
        """Return a formatted string of all tools for prompt construction."""
        listing = []
        for name, info in self._tools.items():
            listing.append(
                f"- {name}: {info['description']} (Args: {info['args_description']})"
            )
        return "\n".join(listing)


# Global registry instance to be imported across the project
tool_registry = ToolRegistry()
