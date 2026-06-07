from tool_registry import tool_registry

import datetime
import json
import os
import secrets
import shutil
import string
import tempfile
from pathlib import Path
import urllib.request

import psutil


class SystemToolsMixin:
    def _base_dir(self) -> Path:
        return Path(getattr(self, "BASE_DIR", Path.cwd()))

    def _clean_text(self, value):
        if value is None:
            return ""
        text = str(value)
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        return text.strip()

    def _safe_filename(self, filename: str, default_name: str = "session.json") -> str:
        name = self._clean_text(filename)
        name = name.replace('"', "").replace("'", "")
        name = Path(name).name
        return name or default_name

    @tool_registry.register(
        name="get_datetime",
        description="Get current date and time.",
        args_description="format_type",
    )
    def get_datetime(self, format_type: str = "default") -> str:
        now = datetime.datetime.now()
        formats = {
            "default": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "iso": now.isoformat(),
            "unix": str(int(now.timestamp())),
            "day": now.strftime("%A"),
            "day_short": now.strftime("%a"),
            "full": now.strftime("%A, %B %d, %Y"),
            "full_with_time": now.strftime("%A, %B %d, %Y at %H:%M:%S"),
        }
        return formats.get(self._clean_text(format_type), formats["default"])

    @tool_registry.register(
        name="save_session",
        description="Saves chat history to JSON.",
        args_description="filename",
    )
    def save_session(self, filename: str = None) -> str:
        try:
            if not hasattr(self, "gui") or not getattr(self.gui, "chat_history", None):
                return "No session history to save."

            if not filename:
                filename = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            safe_name = self._safe_filename(filename)
            target_path = self._base_dir() / safe_name
            data = {
                "metadata": {
                    "project": "Mr. Perfect OS",
                    "timestamp": self.get_datetime("iso"),
                },
                "history": self.gui.chat_history,
            }
            with open(target_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
            return f"Session saved to {target_path.name}"
        except Exception as exc:
            return f"Save error: {exc}"

    @tool_registry.register(
        name="load_session",
        description="Restores chat history from JSON.",
        args_description="filepath",
    )
    def load_session(self, filepath: str) -> str:
        try:
            safe_name = self._safe_filename(filepath)
            target_path = self._base_dir() / safe_name
            if not target_path.exists():
                return f"File not found: {filepath}"

            with open(target_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            history_data = data.get("history") or data.get("chat_history", [])
            if not history_data:
                return "Loaded file contains no history."

            if hasattr(self, "gui") and self.gui is not None:
                self.gui.chat_history = history_data
                self.gui.after(0, self.gui.refresh_chat_display)
            return f"Memory restored: {len(history_data)} messages."
        except Exception as exc:
            return f"Load error: {exc}"

    @tool_registry.register(
        name="calculate",
        description="Safely evaluate math expressions.",
        args_description="expression",
    )
    def calculate(self, expression: str) -> str:
        if hasattr(self, "calculate_math"):
            return self.calculate_math(expression)
        return "Error: Math utility not available."

    @tool_registry.register(
        name="generate_password",
        description="Generate a secure random password.",
        args_description="length, include_special",
    )
    def generate_password(self, length: int = 16, include_special: bool = True) -> str:
        length = max(8, min(128, int(length)))
        alphabet = string.ascii_letters + string.digits
        if include_special:
            alphabet += string.punctuation

        while True:
            password = "".join(secrets.choice(alphabet) for _ in range(length))
            if (
                any(ch.islower() for ch in password)
                and any(ch.isupper() for ch in password)
                and any(ch.isdigit() for ch in password)
            ):
                return password

    @tool_registry.register(
        name="validate_update_safety",
        description="Validate update source safety.",
        args_description="program_name, download_url",
    )
    def validate_update_safety(self, program_name: str, download_url: str) -> str:
        if hasattr(self, "validate_program_safety"):
            return self.validate_program_safety(program_name, download_url)
        return "VERIFY_NEEDED"

    @tool_registry.register(
        name="execute_update",
        description="Download and run an update.",
        args_description="program_name, download_url",
    )
    def execute_update(self, program_name: str, download_url: str) -> str:
        try:
            temp_dir = tempfile.mkdtemp(prefix="mrperfect_update_")
            safe_program = self._safe_filename(program_name, default_name="program")
            file_path = os.path.join(temp_dir, f"{Path(safe_program).stem}_update.exe")

            request = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                with open(file_path, "wb") as out_file:
                    shutil.copyfileobj(response, out_file)

            import subprocess

            result = subprocess.run(
                [file_path],
                capture_output=True,
                text=True,
                shell=True,
                timeout=300,
            )
            output = (result.stdout or result.stderr or "").strip()
            return f"Update of '{program_name}' result: {output[:200] or 'No output'}"
        except Exception as exc:
            return f"Update error: {exc}"

    @tool_registry.register(
        name="validate_self_protection",
        description="Check if path is critical.",
        args_description="path",
    )
    def validate_self_protection(self, path: str) -> str:
        path_lower = self._clean_text(path).lower()
        protected_files = set(
            getattr(
                self,
                "PROTECTED_SELF_FILES",
                {
                    "agent.py",
                    "main.py",
                    "tool_registry.py",
                    "requirements.txt",
                },
            )
        )

        for protected in protected_files:
            if protected.lower() in path_lower:
                return f"PROTECTED: Cannot modify critical file '{path}'"

        for proc in psutil.process_iter(["name"]):
            try:
                proc_name = (proc.info.get("name") or "").lower()
                if any(token in proc_name for token in ["ollama", "lmstudio", "lm studio"]):
                    if "model" in path_lower:
                        return "PROTECTED: LLM model files are currently in use."
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return "OK"

    @tool_registry.register(
        name="get_agent_info",
        description="Get agent status and stats.",
        args_description="",
    )
    def get_agent_info(self) -> str:
        total_tools = len(tool_registry.get_all_tools())
        workspace = self._base_dir()
        return (
            "MR. PERFECT OS\n"
            "Status: Operational\n"
            f"Total Tools Loaded: {total_tools}\n"
            f"Workspace: {workspace}"
        )
