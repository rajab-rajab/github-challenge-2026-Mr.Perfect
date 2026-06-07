import ast
import inspect
import json
import os
import re
import threading
import time
import tkinter.filedialog as fd
from tkinter import messagebox

import customtkinter as ctk
from openai import OpenAI

# Optional project modules
try:
    from tool_registry import tool_registry
except ImportError:
    class _FallbackToolRegistry:
        @staticmethod
        def get_all_tools():
            return {}

    tool_registry = _FallbackToolRegistry()

try:
    import tools_container
except ImportError:
    class _FallbackAgentTools:
        def __init__(self, gui=None):
            self.gui = gui

        def save_session(self, filename):
            data = {"chat_history": getattr(self.gui, "chat_history", [])}
            with open(filename, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
            return f"Session saved to: {filename}"

        def load_session(self, filepath):
            if not os.path.exists(filepath):
                return f"File not found: {filepath}"

            with open(filepath, "r", encoding="utf-8") as file:
                data = json.load(file)

            if self.gui is not None:
                self.gui.chat_history = data.get("chat_history", [])
                self.gui.refresh_chat_display()

            return f"Session loaded from: {filepath}"

    class _FallbackToolsContainer:
        AgentTools = _FallbackAgentTools

    tools_container = _FallbackToolsContainer()


# --- CONFIGURATION ---
LOCAL_LLM_URL = "http://127.0.0.1:5000/v1"
LOCAL_MODEL = "GEMMA 4"
MAX_AGENT_STEPS = 4

client = OpenAI(base_url=LOCAL_LLM_URL, api_key="not-needed")


class MrPerfectBrain:
    def __init__(self, gui_instance):
        self.gui = gui_instance
        self.tools_instance = tools_container.AgentTools(gui=self.gui)
        self.tool_map = {
            name: info["function"]
            for name, info in tool_registry.get_all_tools().items()
            if isinstance(info, dict) and "function" in info
        }
        self.stop_signal = False

    def build_system_prompt(self):
        tool_definitions = []
        for name, info in tool_registry.get_all_tools().items():
            description = info.get("description", "No description available.")
            args_description = info.get("args_description", "No arguments.")
            tool_definitions.append(f"- {name}: {description}. Args: {args_description}")

        tools_str = "\n".join(tool_definitions) if tool_definitions else "- No tools registered."

        return f"""You are 'Mr. Perfect', an Elite Agentic OS.

Current Date/Time: {time.strftime('%Y-%m-%d %H:%M:%S')}

AVAILABLE TOOLS:
{tools_str}

RESPONSE FORMAT FOR EVERY STEP:
STEP: <number>
THOUGHT: <brief visible reasoning for the operator>
ACTION: tool_name(key=\"value\")

OR, WHEN FINISHED:
STEP: <number>
THOUGHT: <brief visible reasoning for the operator>
FINAL RESPONSE: <answer>

RULES:
- Always include STEP and THOUGHT.
- Keep THOUGHT short, clear, and visible in the console.
- Use at most one ACTION per response.
- After OBSERVATION is provided, continue to the next step.
- If no tool is needed, provide FINAL RESPONSE.
- Never use markdown in tool arguments, filenames, code, or final answers.
- Never output links such as [file](url), code fences, bold markers, or italic markers.
- Filenames must be plain valid paths like calculator_gui.py.
- Python code must use exact identifiers such as __init__ and __name__.
- When creating tkinter code, do not use ttk.Entry with unsupported options like bd or relief.
- If a tool argument contains multiline code or text, use triple quotes for that argument.
- If generate_code_template is insufficient or fails, immediately write the full working solution with create_code_file.
- After writing code, ensure it is valid and corrected before giving FINAL RESPONSE.
- If create_code_file reports validation failure or smoke test failure, use auto_correct_code when helpful, then save the corrected code again before FINAL RESPONSE.
- If a tool observation provides an exact saved filename, use that exact filename in later actions and in FINAL RESPONSE.
- If save fails because a file already exists, either choose a new clean filename or use auto_rename=True. Use overwrite=True only when replacing the file is truly intended.
- For GUI apps, do not auto-run them unless the user explicitly asks to run them; instead save the file and explain how to run it.
"""

    def _strip_markdown_links(self, text):
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)

    def _sanitize_filepath(self, filepath):
        filepath = self._strip_markdown_links(filepath)
        filepath = filepath.replace("`", "").replace('"', "").replace("'", "")
        filepath = filepath.strip()
        filepath = re.sub(r"\s+", "_", filepath)
        filepath = re.sub(r"[^A-Za-z0-9_./\\-]", "", filepath)
        filepath = re.sub(r"_+", "_", filepath)
        return filepath

    def _sanitize_generated_text(self, text):
        if not isinstance(text, str):
            return text

        cleaned = text
        previous = None
        while previous != cleaned:
            previous = cleaned
            cleaned = self._strip_markdown_links(cleaned)

        cleaned = cleaned.replace("&lt;", "<").replace("&gt;", ">")
        cleaned = cleaned.replace("\r\n", "\n")

        replacements = {
            "**init**": "__init__",
            "**name**": "__name__",
            "**main**": "__main__",
            "*init*": "__init__",
            "*name*": "__name__",
            "*main*": "__main__",
        }
        for wrong, right in replacements.items():
            cleaned = cleaned.replace(wrong, right)

        cleaned = re.sub(r"```(?:python)?", "", cleaned)
        cleaned = cleaned.replace("```", "")

        if "ttk.Entry(" in cleaned and ("bd=" in cleaned or "relief=" in cleaned):
            cleaned = cleaned.replace("ttk.Entry(", "tk.Entry(")

        return cleaned.strip()

    def _validate_python_code(self, filepath, content):
        if not isinstance(filepath, str) or not filepath.lower().endswith(".py"):
            return
        if not isinstance(content, str):
            return

        try:
            compile(content, filepath, "exec")
            self.gui.log_console(f"✅ Python syntax check passed: {filepath}")
        except SyntaxError as exc:
            self.gui.log_console(
                f"⚠️ Python syntax warning in {filepath}: line {exc.lineno}: {exc.msg}"
            )

    def _prepare_tool_kwargs(self, func_name, kwargs):
        cleaned_kwargs = {}

        for key, value in kwargs.items():
            if isinstance(value, str):
                if key.lower() in {"filepath", "filename", "path"}:
                    new_value = self._sanitize_filepath(value)
                    if new_value != value:
                        self.gui.log_console(f"🧹 Sanitized path: {value} -> {new_value}")
                    cleaned_kwargs[key] = new_value
                else:
                    new_value = self._sanitize_generated_text(value)
                    cleaned_kwargs[key] = new_value
            else:
                cleaned_kwargs[key] = value

        if func_name in {"create_code_file", "write_file", "save_file"}:
            for content_key in ("content", "code", "text"):
                if content_key in cleaned_kwargs and isinstance(cleaned_kwargs[content_key], str):
                    cleaned_kwargs[content_key] = self._sanitize_generated_text(cleaned_kwargs[content_key])

                    target_path = (
                        cleaned_kwargs.get("filepath")
                        or cleaned_kwargs.get("filename")
                        or cleaned_kwargs.get("path")
                    )
                    self._validate_python_code(target_path, cleaned_kwargs[content_key])
                    break

        return cleaned_kwargs

    def _extract_section(self, text, start_tag, end_tags=None):
        if start_tag not in text:
            return ""

        start_index = text.find(start_tag) + len(start_tag)
        end_index = len(text)

        if end_tags:
            positions = []
            for tag in end_tags:
                pos = text.find(tag, start_index)
                if pos != -1:
                    positions.append(pos)
            if positions:
                end_index = min(positions)

        return text[start_index:end_index].strip()

    def _parse_loose_kwargs(self, args_raw):
        kwargs = {}
        i = 0
        n = len(args_raw)

        while i < n:
            while i < n and args_raw[i] in " \t\r\n,":
                i += 1
            if i >= n:
                break

            key_match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", args_raw[i:])
            if not key_match:
                raise ValueError(f"Could not parse argument near: {args_raw[i:i+40]!r}")

            key = key_match.group(0)
            i += len(key)

            while i < n and args_raw[i] in " \t\r\n":
                i += 1
            if i >= n or args_raw[i] != "=":
                raise ValueError(f"Expected '=' after argument name '{key}'")
            i += 1

            while i < n and args_raw[i] in " \t\r\n":
                i += 1
            if i >= n:
                kwargs[key] = ""
                break

            if args_raw.startswith('"""', i) or args_raw.startswith("'''", i):
                quote = args_raw[i:i+3]
                i += 3
                end = args_raw.find(quote, i)
                if end == -1:
                    value = args_raw[i:]
                    i = n
                else:
                    value = args_raw[i:end]
                    i = end + 3
                kwargs[key] = value
            elif args_raw[i] in {'"', "'"}:
                quote = args_raw[i]
                i += 1
                chars = []
                while i < n:
                    ch = args_raw[i]
                    if ch == "\\" and i + 1 < n:
                        chars.append(args_raw[i + 1])
                        i += 2
                        continue
                    if ch == quote:
                        i += 1
                        break
                    chars.append(ch)
                    i += 1
                kwargs[key] = "".join(chars)
            else:
                start = i
                depth = 0
                while i < n:
                    ch = args_raw[i]
                    if ch in "([{":
                        depth += 1
                    elif ch in ")]}":
                        if depth == 0:
                            break
                        depth -= 1
                    elif ch == "," and depth == 0:
                        break
                    i += 1
                raw_value = args_raw[start:i].strip()
                try:
                    kwargs[key] = ast.literal_eval(raw_value)
                except Exception:
                    kwargs[key] = raw_value

            while i < n and args_raw[i] in " \t\r\n":
                i += 1
            if i < n and args_raw[i] == ",":
                i += 1

        return kwargs

    def _parse_action_call(self, action_str):
        try:
            node = ast.parse(action_str, mode="eval").body

            if not isinstance(node, ast.Call):
                raise ValueError("ACTION must be a function call.")

            if not isinstance(node.func, ast.Name):
                raise ValueError("Only direct tool function names are allowed.")

            func_name = node.func.id
            kwargs = {}

            if node.args:
                if len(node.args) == 1:
                    positional_value = ast.literal_eval(node.args[0])
                    if isinstance(positional_value, dict):
                        kwargs.update(positional_value)
                    else:
                        raise ValueError("Only a single dict positional argument is supported.")
                else:
                    raise ValueError("Only keyword arguments are supported.")

            for keyword in node.keywords:
                if keyword.arg is None:
                    raise ValueError("**kwargs is not supported in ACTION.")
                kwargs[keyword.arg] = ast.literal_eval(keyword.value)

            return func_name, kwargs

        except SyntaxError:
            match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$", action_str, re.DOTALL)
            if not match:
                raise ValueError("Invalid ACTION format.")

            func_name = match.group(1)
            args_raw = match.group(2)
            kwargs = self._parse_loose_kwargs(args_raw)
            return func_name, kwargs

    def execute_tool(self, action_str):
        try:
            func_name, kwargs = self._parse_action_call(action_str.strip())
            kwargs = self._prepare_tool_kwargs(func_name, kwargs)

            if func_name not in self.tool_map:
                return f"Error: Tool '{func_name}' not found."

            if func_name == "run_file":
                path_value = kwargs.get("filepath") or kwargs.get("filename") or kwargs.get("path", "")
                if isinstance(path_value, str) and path_value.lower().endswith(".py"):
                    lowered = path_value.lower()
                    if any(tag in lowered for tag in ("gui", "tkinter", "window", "app")):
                        return (
                            f"Skipped automatic run for GUI file '{path_value}'. "
                            f"GUI apps should be launched manually to avoid timeout."
                        )

            func = self.tool_map[func_name]
            parameters = list(inspect.signature(func).parameters.keys())

            if parameters and parameters[0] == "self":
                return func(self.tools_instance, **kwargs)
            return func(**kwargs)

        except Exception as exc:
            return f"Execution Error: {exc}"

    def run_agent_loop(self, user_input):
        self.stop_signal = False
        self.gui.set_busy(True)

        self.gui.chat_history.append({"role": "user", "content": user_input})
        messages = [{"role": "system", "content": self.build_system_prompt()}] + list(self.gui.chat_history)

        self.gui.log_console("=" * 60)
        self.gui.log_console(f"🚀 New request: {user_input}")

        try:
            for step in range(MAX_AGENT_STEPS):
                if self.stop_signal:
                    self.gui.log_console("⏹️ Process stopped by user.")
                    self.gui.log_chat("SYSTEM", "Process stopped by user.")
                    break

                step_no = step + 1
                self.gui.update_status(f"Step {step_no}/{MAX_AGENT_STEPS}: Thinking...")
                self.gui.log_console("")
                self.gui.log_console(f"--- STEP {step_no}/{MAX_AGENT_STEPS} ---")
                self.gui.log_console("🧠 Waiting for model response...")

                response = client.chat.completions.create(
                    model=LOCAL_MODEL,
                    messages=messages,
                    temperature=0.1,
                )

                ai_msg = (response.choices[0].message.content or "").strip()
                messages.append({"role": "assistant", "content": ai_msg})

                model_step = self._extract_section(ai_msg, "STEP:", ["THOUGHT:", "ACTION:", "FINAL RESPONSE:"])
                if model_step:
                    self.gui.log_console(f"🔢 Model step: {model_step}")

                thought = self._extract_section(ai_msg, "THOUGHT:", ["ACTION:", "FINAL RESPONSE:"])
                if thought:
                    self.gui.log_console(f"🧠 THOUGHT: {thought}")

                action_text = self._extract_section(ai_msg, "ACTION:", ["FINAL RESPONSE:"])
                if action_text and not self.stop_signal:
                    self.gui.log_console(f"🛠️ ACTION: {action_text}")
                    observation = self.execute_tool(action_text)
                    if isinstance(observation, str):
                        observation = self._sanitize_generated_text(observation)
                    self.gui.log_console(f"📥 OBSERVATION: {observation}")
                    messages.append({"role": "user", "content": f"OBSERVATION: {observation}"})

                    action_name_match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)", action_text)
                    action_name = action_name_match.group(1) if action_name_match else ""
                    observation_lower = observation.lower() if isinstance(observation, str) else ""

                    if action_name == "generate_code_template" and ("❌" in observation or "error" in observation_lower):
                        recovery = (
                            "RECOVERY INSTRUCTION: Template generation failed or was insufficient. "
                            "Do not call generate_code_template again for this task. "
                            "Now create the full working solution with create_code_file using a clean filename and complete code."
                        )
                        self.gui.log_console(f"🔁 {recovery}")
                        messages.append({"role": "user", "content": recovery})

                    if action_name in {"create_code_file", "write_file"}:
                        saved_match = re.search(r"file\s+([a-zA-Z0-9_./\\-]+)\s+saved successfully", observation, re.IGNORECASE)
                        if saved_match:
                            exact_file = saved_match.group(1)
                            filename_note = (
                                f"SYSTEM NOTE: The exact saved filename is {exact_file}. "
                                f"Use this exact filename in any later action or FINAL RESPONSE."
                            )
                            self.gui.log_console(f"📝 {filename_note}")
                            messages.append({"role": "user", "content": filename_note})

                    if action_name in {"create_code_file", "write_file"} and (
                        "save aborted" in observation_lower
                        or "syntax error" in observation_lower
                        or "validation error" in observation_lower
                        or "smoke test failed" in observation_lower
                    ):
                        recovery = (
                            "RECOVERY INSTRUCTION: The code did not fully validate or run correctly. "
                            "Use auto_correct_code if helpful, then call create_code_file again with corrected content and the same clean filename."
                        )
                        self.gui.log_console(f"🔁 {recovery}")
                        messages.append({"role": "user", "content": recovery})

                    continue

                final_reply = self._extract_section(ai_msg, "FINAL RESPONSE:")
                if final_reply:
                    final_reply = self._sanitize_generated_text(final_reply)
                    self.gui.chat_history.append({"role": "assistant", "content": final_reply})
                    self.gui.log_console(f"✅ FINAL RESPONSE: {final_reply}")
                    self.gui.log_chat("MR. PERFECT", final_reply)
                    break

                if ai_msg:
                    self.gui.log_console("⚠️ Unstructured model output received:")
                    self.gui.log_console(ai_msg)
                    self.gui.chat_history.append({"role": "assistant", "content": ai_msg})
                    self.gui.log_chat("MR. PERFECT", ai_msg)
                    break

            else:
                max_steps_message = "Maximum steps reached without a FINAL RESPONSE."
                self.gui.log_console(f"⚠️ {max_steps_message}")
                self.gui.log_chat("SYSTEM", max_steps_message)

        except Exception as exc:
            self.gui.log_chat("SYSTEM", f"Error: {exc}")
            self.gui.log_console(f"❌ Error: {exc}")

        finally:
            self.gui.update_status("System Idle")
            self.gui.set_busy(False)


class MrPerfectGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Mr. Perfect OS v14 - Pro Edition")
        self.geometry("1450x900")
        ctk.set_appearance_mode("dark")

        self.chat_history = []
        self.brain = MrPerfectBrain(self)

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # SIDEBAR
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")

        ctk.CTkLabel(
            self.sidebar,
            text="MR. PERFECT",
            font=("Consolas", 24, "bold"),
            text_color="#00FF00",
        ).pack(pady=20)

        # SESSION BUTTONS
        ctk.CTkButton(self.sidebar, text="💾 Save Session", command=self.gui_save_session).pack(
            pady=5, padx=20, fill="x"
        )
        ctk.CTkButton(self.sidebar, text="📂 Load Session", command=self.gui_load_session).pack(
            pady=5, padx=20, fill="x"
        )

        # CLEAR BUTTONS
        ctk.CTkLabel(self.sidebar, text="Management", text_color="gray").pack(pady=(20, 0))
        ctk.CTkButton(
            self.sidebar,
            text="🗑️ Clear Prompt",
            fg_color="#444",
            command=lambda: self.entry.delete(0, "end"),
        ).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(
            self.sidebar,
            text="🗑️ Clear Response",
            fg_color="#444",
            command=self.clear_chat,
        ).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(
            self.sidebar,
            text="🧹 Clear Console",
            fg_color="#2E5E2E",
            command=self.clear_console,
        ).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(
            self.sidebar,
            text="📋 Copy Console",
            fg_color="#333",
            command=self.copy_console_content,
        ).pack(pady=5, padx=20, fill="x")

        self.lbl_status = ctk.CTkLabel(self.sidebar, text="System Idle", text_color="#88FF88")
        self.lbl_status.pack(side="bottom", pady=20)

        # CHAT DISPLAY
        self.chat_display = ctk.CTkTextbox(
            self,
            font=("Segoe UI", 15),
            state="disabled",
            wrap="word",
        )
        self.chat_display.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        # RESPONSE CONSOLE ONLY
        self.response_panel = ctk.CTkFrame(self)
        self.response_panel.grid(row=0, column=2, padx=(0, 20), pady=20, sticky="nsew")

        self.response_panel.grid_rowconfigure(1, weight=1)
        self.response_panel.grid_columnconfigure(0, weight=1)

        self.response_title = ctk.CTkLabel(
            self.response_panel,
            text="📟 Response Console",
            font=("Consolas", 18, "bold"),
            text_color="#E8FFE8",
        )
        self.response_title.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="w")

        # CONSOLE - GREEN BACKGROUND AS REQUESTED
        self.console = ctk.CTkTextbox(
            self.response_panel,
            fg_color="#167C1A",
            text_color="#F2FFF2",
            font=("Consolas", 12),
            wrap="word",
        )
        self.console.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.console.configure(state="disabled")

        # INPUT AREA
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=1, column=1, columnspan=2, padx=20, pady=10, sticky="ew")

        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Enter instruction...", height=50)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry.bind("<Return>", lambda event: self.send_message())

        self.btn_send = ctk.CTkButton(
            self.input_frame,
            text="EXECUTE",
            width=100,
            height=50,
            fg_color="#007ACC",
            command=self.send_message,
        )
        self.btn_send.pack(side="left", padx=5)

        self.btn_stop = ctk.CTkButton(
            self.input_frame,
            text="STOP",
            width=80,
            height=50,
            fg_color="darkred",
            hover_color="red",
            command=self.stop_agent,
        )
        self.btn_stop.pack(side="left", padx=5)

        self.log_console("Console ready. Thinking steps will appear here.")

    # --- ACTION METHODS ---

    def stop_agent(self):
        self.brain.stop_signal = True
        self.update_status("Stopping...")
        self.log_console("⏹️ Stop requested by user.")

    def gui_save_session(self):
        file_path = fd.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if file_path:
            res = self.brain.tools_instance.save_session(filename=file_path)
            messagebox.showinfo("Session", res)

    def gui_load_session(self):
        file_path = fd.askopenfilename(filetypes=[("JSON", "*.json")])
        if file_path:
            res = self.brain.tools_instance.load_session(filepath=file_path)
            self.refresh_chat_display()
            messagebox.showinfo("Session", res)

    def copy_console_content(self):
        content = self.console.get("0.0", "end")
        self.clipboard_clear()
        self.clipboard_append(content)
        self.update_status("Console copied to clipboard!")

    def clear_chat(self):
        self.chat_history = []
        self.chat_display.configure(state="normal")
        self.chat_display.delete("0.0", "end")
        self.chat_display.configure(state="disabled")

    def clear_console(self):
        self.console.configure(state="normal")
        self.console.delete("0.0", "end")
        self.console.configure(state="disabled")

    # --- UI HELPERS ---

    def log_chat(self, sender, message):
        self.after(0, lambda: self._update_chat(sender, message))

    def _update_chat(self, sender, message):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"{sender}: {message}\n\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def log_console(self, message):
        self.after(0, lambda: self._append_console(message))

    def _append_console(self, message):
        self.console.configure(state="normal")
        self.console.insert("end", f"> {message}\n")
        self.console.configure(state="disabled")
        self.console.see("end")

    def display_code(self, code):
        self.after(0, lambda: self._show_output_in_console(code))

    def _show_output_in_console(self, code):
        self.console.configure(state="normal")
        self.console.insert("end", "\n> ===== AGENT OUTPUT =====\n")
        self.console.insert("end", f"{code}\n")
        self.console.insert("end", "> ========================\n")
        self.console.configure(state="disabled")
        self.console.see("end")

    def refresh_chat_display(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("0.0", "end")
        for msg in self.chat_history:
            sender = "USER" if msg.get("role") == "user" else "MR. PERFECT"
            self.chat_display.insert("end", f"{sender}: {msg.get('content', '')}\n\n")
        self.chat_display.configure(state="disabled")

    def update_status(self, text):
        self.after(0, lambda: self.lbl_status.configure(text=text))

    def set_busy(self, busy=True):
        def _apply():
            if busy:
                self.btn_send.configure(state="disabled")
                self.entry.configure(state="disabled")
            else:
                self.btn_send.configure(state="normal")
                self.entry.configure(state="normal")

        self.after(0, _apply)

    def send_message(self):
        query = self.entry.get().strip()
        if not query:
            return

        self.entry.delete(0, "end")
        self.log_chat("USER", query)
        threading.Thread(target=self.brain.run_agent_loop, args=(query,), daemon=True).start()


if __name__ == "__main__":
    app = MrPerfectGUI()
    app.mainloop()
