from tool_registry import tool_registry

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
import difflib


class CodeToolsMixin:
    def _base_dir(self) -> Path:
        return Path(getattr(self, "BASE_DIR", Path.cwd()))

    def _repair_tkinter_code(self, text: str) -> str:
        if "tkinter" not in text.lower() and "customtkinter" not in text.lower():
            return text

        repaired = text
        previous = None
        while previous != repaired:
            previous = repaired
            repaired = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", repaired)

        repaired = re.sub(r"\[tk\.Tk\]\([^)]*\)", "tk.Tk", repaired)
        repaired = re.sub(r"\[(\w+(?:\.\w+)*)\]\([^)]*\)", r"\1", repaired)

        if "ttk.Entry(" in repaired and ("bd=" in repaired or "relief=" in repaired):
            repaired = repaired.replace("ttk.Entry(", "tk.Entry(")

        if "mainloop(" not in repaired:
            if re.search(r"^\s*root\s*=\s*tk\.Tk\(\)", repaired, re.MULTILINE):
                repaired = repaired.rstrip() + "\n\nroot.mainloop()\n"

        return repaired

    def _clean_text(self, value):
        if value is None:
            return ""

        text = str(value)
        text = text.replace("&lt;", "<").replace("&gt;", ">")

        previous = None
        while previous != text:
            previous = text
            text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)

        text = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", text)
        text = text.replace("```", "")

        replacements = {
            "**init**": "__init__",
            "**name**": "__name__",
            "**main**": "__main__",
            "*init*": "__init__",
            "*name*": "__name__",
            "*main*": "__main__",
        }
        for wrong, right in replacements.items():
            text = text.replace(wrong, right)

        text = self._repair_tkinter_code(text)
        return text.strip()

    def _extract_value(self, direct_value=None, kwargs=None, *names):
        if direct_value not in (None, ""):
            return direct_value

        kwargs = kwargs or {}
        for name in names:
            if name in kwargs and kwargs[name] not in (None, ""):
                return kwargs[name]
        return None

    def _unwrap_json_payload(self, value, fallback_language=None):
        cleaned = self._clean_text(value)
        language = fallback_language

        if cleaned.startswith("{") and cleaned.endswith("}"):
            try:
                data = json.loads(cleaned)
                code = data.get("code") or data.get("content") or data.get("script") or cleaned
                language = data.get("language") or language
                return self._clean_text(code), language
            except Exception:
                pass

        return cleaned, language

    def _sanitize_filepath(self, filepath: str) -> str:
        cleaned = self._clean_text(filepath)
        cleaned = cleaned.replace('"', "").replace("'", "").strip()
        cleaned = re.sub(r"\s+", "_", cleaned)
        cleaned = re.sub(r"[^A-Za-z0-9_./\\-]", "", cleaned)
        cleaned = cleaned.replace("\\", "/")
        cleaned = re.sub(r"/+", "/", cleaned)

        if not cleaned:
            cleaned = "generated_file.txt"

        return cleaned

    def _slugify(self, text: str) -> str:
        text = self._clean_text(text).lower()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text or "generated_app"

    def _guess_extension(self, language: str, content: str = "") -> str:
        normalized = (language or "python").lower().strip()
        content_lower = (content or "").lower()

        if normalized in {"python", "py"}:
            return ".py"
        if normalized in {"javascript", "js", "node"}:
            return ".js"
        if normalized in {"html", "htm"}:
            return ".html"
        if normalized == "css":
            return ".css"
        if normalized == "sql":
            return ".sql"

        if "tkinter" in content_lower or "def " in content_lower or "import " in content_lower:
            return ".py"
        if "function " in content_lower or "const " in content_lower or "console.log" in content_lower:
            return ".js"
        if "<html" in content_lower or "<!doctype html" in content_lower:
            return ".html"
        return ".txt"

    def _guess_filename_from_task(self, task: str = "", language: str = "python", content: str = "") -> str:
        task_lower = (task or "").lower()
        extension = self._guess_extension(language, content)

        if any(word in task_lower for word in ("calculator", "calc")):
            stem = "calculator_app"
        elif any(word in task_lower for word in ("todo", "to-do", "task list")):
            stem = "todo_app"
        elif any(word in task_lower for word in ("text editor", "notepad", "editor")):
            stem = "text_editor"
        elif any(word in task_lower for word in ("api", "flask", "fastapi", "rest")):
            stem = "api_app"
        elif any(word in task_lower for word in ("server", "web server", "http server")):
            stem = "server_app"
        elif any(word in task_lower for word in ("scrape", "crawler", "scraper")):
            stem = "web_scraper"
        elif any(word in task_lower for word in ("database", "sqlite", "crud", "db")):
            stem = "database_app"
        elif any(word in task_lower for word in ("gui", "tkinter", "desktop", "window", "form")):
            count = self._detect_input_count(task, default=0)
            if count >= 2 and any(word in task_lower for word in ("add", "sum", "adder")):
                stem = f"{count}_number_adder"
            else:
                stem = self._slugify(task)[:50] or "gui_app"
        else:
            stem = self._slugify(task)[:50] or "generated_app"

        return f"{stem}{extension}"

    def _looks_like_gui_or_long_running(self, filepath: str, content: str) -> bool:
        suffix = Path(filepath).suffix.lower()
        text = (content or "").lower()
        if suffix not in {".py", ".js"}:
            return True

        gui_markers = (
            "tkinter",
            "customtkinter",
            "pyqt",
            "kivy",
            "mainloop(",
            "express(",
            "app.listen(",
            "flask(",
            "fastapi(",
            "serve_forever(",
            "streamlit",
            "gradio",
        )
        interactive_markers = ("input(", "argparse", "sys.argv", "process.argv")
        return any(marker in text for marker in gui_markers + interactive_markers)

    def _attempt_auto_fix(self, filepath: str, content: str) -> str:
        fixed = self._clean_text(content)
        suffix = Path(filepath).suffix.lower()

        if suffix == ".py":
            fixed = self._repair_tkinter_code(fixed)

            if "if __name__ == \"__main__\":" in fixed and re.search(
                r"if __name__ == \"__main__\":\s*$", fixed, re.MULTILINE
            ) and "def main(" in fixed:
                fixed = fixed.rstrip() + "\n    main()\n"

            if "tk.Tk()" in fixed and "mainloop(" not in fixed:
                fixed = fixed.rstrip() + "\n\nroot.mainloop()\n"

        return fixed

    def _next_available_path(self, target_path: Path) -> Path:
        candidate = target_path
        index = 1
        while candidate.exists():
            candidate = target_path.with_name(f"{target_path.stem}_{index}{target_path.suffix}")
            index += 1
        return candidate

    def _handle_existing_file_conflict(self, target_path: Path, overwrite: bool = False, auto_rename: bool = False):
        if not target_path.exists() or overwrite:
            return target_path, ""

        suggested = self._next_available_path(target_path)
        if auto_rename:
            return suggested, f"⚠️ File already existed. Saved as {suggested.name} instead."

        message = (
            f"❌ File already exists: {target_path.name}.\n"
            f"Suggested available filename: {suggested.name}.\n"
            f"Use overwrite=True to replace it or auto_rename=True to save as the suggested filename."
        )
        return None, message

    def _syntax_check_message(self, filepath: str, content: str) -> str:
        if not filepath.lower().endswith(".py"):
            return ""

        try:
            ast.parse(content)
            return "\n✅ Python syntax check passed."
        except SyntaxError as exc:
            return f"\n⚠️ Python syntax warning: line {exc.lineno}: {exc.msg}"

    def _word_number_map(self):
        return {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
        }

    def _detect_input_count(self, task_text: str, default: int = 2) -> int:
        task_lower = task_text.lower()

        digit_match = re.search(r"\b(\d{1,2})\s+(?:numbers?|inputs?|values?|fields?)\b", task_lower)
        if digit_match:
            return max(1, min(10, int(digit_match.group(1))))

        for word, number in sorted(self._word_number_map().items(), key=lambda item: -len(item[0])):
            if re.search(rf"\b{word}\s+(?:numbers?|inputs?|values?|fields?)\b", task_lower):
                return number

        if "adder" in task_lower or "sum" in task_lower or "add" in task_lower:
            for word, number in self._word_number_map().items():
                if re.search(rf"\b{word}\b", task_lower):
                    return number
            short_digit = re.search(r"\b(\d{1,2})\b", task_lower)
            if short_digit:
                return max(1, min(10, int(short_digit.group(1))))

        return default

    def _number_label(self, index: int) -> str:
        labels = {
            1: "First",
            2: "Second",
            3: "Third",
            4: "Fourth",
            5: "Fifth",
            6: "Sixth",
            7: "Seventh",
            8: "Eighth",
            9: "Ninth",
            10: "Tenth",
        }
        return labels.get(index, f"Input {index}")

    def _build_tkinter_adder(self, count: int) -> str:
        count = max(2, min(10, int(count)))
        labels = [self._number_label(i) for i in range(1, count + 1)]
        geometry_height = 180 + (count * 45)
        labels_repr = repr([f"{label} Number" for label in labels])
        button_text = f"Add All {count}" if count > 2 else "Add"
        title = f"{count} Number Adder"

        return dedent(
            f'''
            import tkinter as tk


            def add_numbers():
                try:
                    values = [float(entry.get()) for entry in entries]
                    result_var.set(f"Result: {{sum(values)}}")
                except ValueError:
                    result_var.set("Please enter valid numbers in all fields.")


            root = tk.Tk()
            root.title("{title}")
            root.geometry("360x{geometry_height}")
            root.resizable(False, False)


            entries = []
            labels = {labels_repr}

            for index, label_text in enumerate(labels):
                top_pad = (15, 5) if index == 0 else (5, 5)
                tk.Label(root, text=label_text).pack(pady=top_pad)
                entry = tk.Entry(root)
                entry.pack(pady=3)
                entries.append(entry)


            tk.Button(root, text="{button_text}", command=add_numbers).pack(pady=15)


            result_var = tk.StringVar(value="Result will appear here")
            tk.Label(root, textvariable=result_var, font=("Arial", 14, "bold")).pack(pady=10)


            root.mainloop()
            '''
        ).strip()

    def _build_tkinter_calculator(self) -> str:
        return dedent(
            '''
            import tkinter as tk


            def on_click(value):
                current = display_var.get()
                display_var.set(current + value)


            def clear_display():
                display_var.set("")


            def calculate():
                try:
                    result = eval(display_var.get(), {"__builtins__": {}}, {})
                    display_var.set(str(result))
                except Exception:
                    display_var.set("Error")


            root = tk.Tk()
            root.title("Calculator")
            root.geometry("320x420")
            root.resizable(False, False)


            display_var = tk.StringVar()
            display = tk.Entry(root, textvariable=display_var, font=("Arial", 20), justify="right")
            display.grid(row=0, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")


            buttons = [
                ("7", 1, 0), ("8", 1, 1), ("9", 1, 2), ("/", 1, 3),
                ("4", 2, 0), ("5", 2, 1), ("6", 2, 2), ("*", 2, 3),
                ("1", 3, 0), ("2", 3, 1), ("3", 3, 2), ("-", 3, 3),
                ("0", 4, 0), (".", 4, 1), ("=", 4, 2), ("+", 4, 3),
                ("C", 5, 0), ("(", 5, 1), (")", 5, 2), ("%", 5, 3),
            ]

            for text, row, column in buttons:
                if text == "=":
                    command = calculate
                elif text == "C":
                    command = clear_display
                else:
                    command = lambda value=text: on_click(value)

                tk.Button(root, text=text, command=command, width=5, height=2).grid(
                    row=row, column=column, padx=5, pady=5, sticky="nsew"
                )

            for row in range(6):
                root.grid_rowconfigure(row, weight=1)
            for column in range(4):
                root.grid_columnconfigure(column, weight=1)


            root.mainloop()
            '''
        ).strip()

    def _build_tkinter_todo(self) -> str:
        return dedent(
            '''
            import tkinter as tk
            from tkinter import messagebox


            def add_task():
                task = task_var.get().strip()
                if not task:
                    messagebox.showwarning("Missing Task", "Please enter a task.")
                    return
                task_list.insert(tk.END, task)
                task_var.set("")


            def remove_task():
                selected = task_list.curselection()
                if not selected:
                    messagebox.showwarning("No Selection", "Select a task to remove.")
                    return
                task_list.delete(selected[0])


            root = tk.Tk()
            root.title("To-Do App")
            root.geometry("420x420")
            root.resizable(False, False)


            task_var = tk.StringVar()

            tk.Label(root, text="Task", font=("Arial", 12, "bold")).pack(pady=(15, 5))
            tk.Entry(root, textvariable=task_var, width=35).pack(pady=5)
            tk.Button(root, text="Add Task", command=add_task).pack(pady=5)

            task_list = tk.Listbox(root, width=45, height=12)
            task_list.pack(pady=15)

            tk.Button(root, text="Remove Selected Task", command=remove_task).pack(pady=5)


            root.mainloop()
            '''
        ).strip()

    def _build_tkinter_text_editor(self) -> str:
        return dedent(
            '''
            import tkinter as tk
            from tkinter import filedialog, messagebox


            def open_file():
                filepath = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
                if not filepath:
                    return
                with open(filepath, "r", encoding="utf-8", errors="ignore") as file:
                    editor.delete("1.0", tk.END)
                    editor.insert("1.0", file.read())


            def save_file():
                filepath = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
                if not filepath:
                    return
                with open(filepath, "w", encoding="utf-8") as file:
                    file.write(editor.get("1.0", tk.END))
                messagebox.showinfo("Saved", f"File saved to {filepath}")


            root = tk.Tk()
            root.title("Simple Text Editor")
            root.geometry("700x500")

            toolbar = tk.Frame(root)
            toolbar.pack(fill="x", padx=10, pady=10)

            tk.Button(toolbar, text="Open", command=open_file).pack(side="left", padx=5)
            tk.Button(toolbar, text="Save", command=save_file).pack(side="left", padx=5)

            editor = tk.Text(root, wrap="word", font=("Consolas", 12))
            editor.pack(expand=True, fill="both", padx=10, pady=(0, 10))


            root.mainloop()
            '''
        ).strip()

    def _build_generic_tkinter_app(self, task_text: str) -> str:
        title = (task_text or "GUI App").strip().title()[:40]
        title = title if title else "GUI App"
        return dedent(
            f'''
            import tkinter as tk


            def on_action():
                output_var.set("Action executed successfully.")


            root = tk.Tk()
            root.title("{title}")
            root.geometry("420x280")
            root.resizable(False, False)


            tk.Label(root, text="{title}", font=("Arial", 16, "bold")).pack(pady=(20, 10))
            tk.Label(root, text="This is a starter template. Add your widgets and logic here.").pack(pady=5)

            input_entry = tk.Entry(root, width=35)
            input_entry.pack(pady=10)

            tk.Button(root, text="Run", command=on_action).pack(pady=10)

            output_var = tk.StringVar(value="Output will appear here")
            tk.Label(root, textvariable=output_var, font=("Arial", 12)).pack(pady=10)


            root.mainloop()
            '''
        ).strip()

    def _build_python_api_template(self, task_text: str) -> str:
        if "fastapi" in task_text.lower():
            return dedent(
                '''
                from fastapi import FastAPI


                app = FastAPI()


                @app.get("/")
                def read_root():
                    return {"message": "API is running"}


                @app.get("/health")
                def health_check():
                    return {"status": "ok"}
                '''
            ).strip()

        return dedent(
            '''
            from flask import Flask, jsonify, request


            app = Flask(__name__)


            @app.route("/")
            def home():
                return jsonify({"message": "API is running"})


            @app.route("/echo", methods=["POST"])
            def echo():
                data = request.get_json(silent=True) or {}
                return jsonify({"received": data})


            if __name__ == "__main__":
                app.run(debug=True)
            '''
        ).strip()

    def _build_python_web_server_template(self) -> str:
        return dedent(
            '''
            import http.server
            import socketserver


            PORT = 8080
            Handler = http.server.SimpleHTTPRequestHandler


            with socketserver.TCPServer(("", PORT), Handler) as httpd:
                print(f"Server running at http://localhost:{PORT}")
                httpd.serve_forever()
            '''
        ).strip()

    def _build_python_scraper_template(self) -> str:
        return dedent(
            '''
            import requests
            from bs4 import BeautifulSoup


            def scrape_page(url: str):
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else "No title"
                return {"title": title, "links": [a.get("href") for a in soup.find_all("a", href=True)[:10]]}


            if __name__ == "__main__":
                example = scrape_page("https://example.com")
                print(example)
            '''
        ).strip()

    def _build_python_cli_template(self, task_text: str) -> str:
        app_name = re.sub(r"[^A-Za-z0-9]+", "_", task_text.strip().lower()).strip("_") or "cli_app"
        return dedent(
            f'''
            import argparse


            def main():
                parser = argparse.ArgumentParser(description="{task_text.strip() or 'CLI application'}")
                parser.add_argument("input", nargs="?", default="world", help="Sample positional input")
                args = parser.parse_args()
                print(f"Hello, {{args.input}} from {app_name}!")


            if __name__ == "__main__":
                main()
            '''
        ).strip()

    def _build_python_sqlite_template(self) -> str:
        return dedent(
            '''
            import sqlite3


            def initialize_database(db_name="app.db"):
                connection = sqlite3.connect(db_name)
                cursor = connection.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.commit()
                connection.close()


            if __name__ == "__main__":
                initialize_database()
                print("Database initialized successfully.")
            '''
        ).strip()

    def _build_python_class_template(self) -> str:
        return dedent(
            '''
            class MyClass:
                def __init__(self, name):
                    self.name = name

                def greet(self):
                    return f"Hello {self.name}"
            '''
        ).strip()

    def _build_python_function_template(self) -> str:
        return dedent(
            '''
            def my_function(data):
                return data
            '''
        ).strip()

    def _build_python_generic_app(self, task_text: str) -> str:
        task_text = task_text.strip() or "general application"
        return dedent(
            f'''
            def main():
                """Starter template for: {task_text}"""
                print("Application started")
                print("Task description: {task_text}")
                print("Add your logic here.")


            if __name__ == "__main__":
                main()
            '''
        ).strip()

    def _generate_python_template(self, task_text: str) -> str:
        task_lower = task_text.lower()

        if any(word in task_lower for word in ("calculator", "calc")) and any(
            word in task_lower for word in ("gui", "tkinter", "desktop")
        ):
            return self._build_tkinter_calculator()

        if any(word in task_lower for word in ("todo", "to-do", "task list")) and any(
            word in task_lower for word in ("gui", "tkinter", "desktop")
        ):
            return self._build_tkinter_todo()

        if any(word in task_lower for word in ("text editor", "notepad", "editor")) and any(
            word in task_lower for word in ("gui", "tkinter", "desktop")
        ):
            return self._build_tkinter_text_editor()

        if any(word in task_lower for word in ("add", "sum", "adder")) and any(
            word in task_lower for word in ("gui", "tkinter", "desktop", "inputs", "numbers")
        ):
            count = self._detect_input_count(task_text, default=2)
            return self._build_tkinter_adder(count)

        if any(word in task_lower for word in ("gui", "tkinter", "desktop app", "window", "form")):
            return self._build_generic_tkinter_app(task_text)

        if any(word in task_lower for word in ("fastapi", "flask", "api", "rest")):
            return self._build_python_api_template(task_text)

        if any(word in task_lower for word in ("server", "http server", "web server")):
            return self._build_python_web_server_template()

        if any(word in task_lower for word in ("scrape", "crawler", "beautifulsoup", "requests", "web scraping")):
            return self._build_python_scraper_template()

        if any(word in task_lower for word in ("sqlite", "database", "crud", "db")):
            return self._build_python_sqlite_template()

        if any(word in task_lower for word in ("cli", "command line", "terminal", "console app")):
            return self._build_python_cli_template(task_text)

        if any(word in task_lower for word in ("class", "object")):
            return self._build_python_class_template()

        if any(word in task_lower for word in ("function", "def", "utility function")):
            return self._build_python_function_template()

        return self._build_python_generic_app(task_text)

    def _generate_javascript_template(self, task_text: str) -> str:
        task_lower = task_text.lower()

        if any(word in task_lower for word in ("api", "rest", "express")):
            return dedent(
                '''
                const express = require("express");

                const app = express();
                const PORT = 3000;

                app.use(express.json());

                app.get("/", (req, res) => {
                  res.json({ message: "API is running" });
                });

                app.post("/echo", (req, res) => {
                  res.json({ received: req.body });
                });

                app.listen(PORT, () => {
                  console.log(`Server running at http://localhost:${PORT}`);
                });
                '''
            ).strip()

        if any(word in task_lower for word in ("cli", "command line", "terminal")):
            return dedent(
                '''
                const args = process.argv.slice(2);
                const name = args[0] || "world";
                console.log(`Hello, ${name}!`);
                '''
            ).strip()

        if any(word in task_lower for word in ("web", "browser", "frontend", "html page")):
            return dedent(
                '''
                document.addEventListener("DOMContentLoaded", () => {
                  const app = document.getElementById("app");
                  if (app) {
                    app.textContent = "JavaScript app loaded successfully.";
                  }
                });
                '''
            ).strip()

        if any(word in task_lower for word in ("class", "object")):
            return dedent(
                '''
                class MyClass {
                  constructor(name) {
                    this.name = name;
                  }

                  greet() {
                    return `Hello ${this.name}`;
                  }
                }
                '''
            ).strip()

        if any(word in task_lower for word in ("function", "utility")):
            return dedent(
                '''
                function myFunction(data) {
                  return data;
                }
                '''
            ).strip()

        return dedent(
            '''
            function main() {
              console.log("JavaScript application starter template");
            }

            main();
            '''
        ).strip()

    def _generate_html_template(self, task_text: str) -> str:
        title = (task_text.strip().title() or "Web App")[:50]
        return dedent(
            f'''
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{title}</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        margin: 40px;
                        background: #f5f5f5;
                    }}
                    .card {{
                        max-width: 600px;
                        margin: auto;
                        padding: 24px;
                        background: white;
                        border-radius: 12px;
                        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
                    }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>{title}</h1>
                    <p>This is a starter template for your HTML app.</p>
                    <div id="app"></div>
                </div>
            </body>
            </html>
            '''
        ).strip()

    def _generate_css_template(self, task_text: str) -> str:
        return dedent(
            '''
            :root {
                --primary: #2563eb;
                --background: #f8fafc;
                --text: #0f172a;
            }

            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: var(--background);
                color: var(--text);
            }

            .container {
                max-width: 960px;
                margin: 0 auto;
                padding: 24px;
            }

            .button {
                background: var(--primary);
                color: white;
                border: none;
                padding: 12px 18px;
                border-radius: 8px;
                cursor: pointer;
            }
            '''
        ).strip()

    def _generate_sql_template(self, task_text: str) -> str:
        return dedent(
            '''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            INSERT INTO items (name) VALUES ('Sample Item');

            SELECT * FROM items ORDER BY created_at DESC;
            '''
        ).strip()

    def _generate_template_by_language(self, task_text: str, language: str) -> str:
        normalized = language.lower().strip()

        if normalized in ("python", "py"):
            return self._generate_python_template(task_text)
        if normalized in ("javascript", "js", "node"):
            return self._generate_javascript_template(task_text)
        if normalized in ("html", "htm"):
            return self._generate_html_template(task_text)
        if normalized == "css":
            return self._generate_css_template(task_text)
        if normalized == "sql":
            return self._generate_sql_template(task_text)

        return self._generate_python_template(task_text)

    @tool_registry.register(
        name="execute_code",
        description="Executes code snippets dynamically and returns output.",
        args_description="code, language (python/javascript)",
    )
    def execute_code(self, code: str = None, language: str = "python", **kwargs) -> str:
        input_val = self._extract_value(code, kwargs, "code", "content", "script")
        lang_val = self._extract_value(language, kwargs, "language") or "python"

        if not input_val:
            return "❌ Error: No code provided to execute."

        input_val, lang_val = self._unwrap_json_payload(input_val, lang_val)
        lang_val = (lang_val or "python").lower()

        suffix = ".py" if "python" in lang_val else ".js"
        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=suffix,
                delete=False,
                mode="w",
                encoding="utf-8",
            ) as tmp_file:
                tmp_file.write(input_val)
                tmp_path = tmp_file.name

            cmd = [sys.executable, tmp_path] if suffix == ".py" else ["node", tmp_path]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self._base_dir()),
            )

            output = (result.stdout or "").strip()
            errors = (result.stderr or "").strip()

            if result.returncode == 0:
                return output if output else "✅ Execution successful (no printed output)."

            return f"❌ Runtime Error:\n{errors or 'Unknown runtime error.'}"

        except subprocess.TimeoutExpired:
            return "❌ Error: Execution timed out (30s limit)."
        except FileNotFoundError as exc:
            return f"❌ System Error: Required runtime not found: {exc}"
        except Exception as exc:
            return f"❌ System Error: {exc}"
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    @tool_registry.register(
        name="generate_code_template",
        description="Generate intelligent starter code for many app types including GUI and non-GUI projects.",
        args_description="task description, language",
    )
    def generate_code_template(self, task: str = None, language: str = "python", **kwargs) -> str:
        actual_task = self._extract_value(task, kwargs, "task", "description", "prompt")
        actual_lang = self._extract_value(language, kwargs, "language") or "python"

        if not actual_task:
            return "❌ Error: No task provided."

        task_text = self._clean_text(actual_task)
        generated = self._generate_template_by_language(task_text, actual_lang)
        generated = self._clean_text(generated)

        if not generated:
            fallback = self._generate_python_template(task_text)
            return self._clean_text(fallback)

        return generated

    @tool_registry.register(
        name="check_code_syntax",
        description="Verify code syntax without executing it.",
        args_description="code, language",
    )
    def check_code_syntax(self, code: str = None, language: str = "python", **kwargs) -> str:
        target_code = self._extract_value(code, kwargs, "code", "content")
        target_language = (self._extract_value(language, kwargs, "language") or "python").lower()

        if not target_code:
            return "❌ No code provided."

        target_code = self._clean_text(target_code)

        try:
            if target_language == "python":
                ast.parse(target_code)
                return "✅ Python syntax is valid."

            if target_language == "javascript":
                temp_name = None
                try:
                    with tempfile.NamedTemporaryFile(
                        suffix=".js",
                        delete=False,
                        mode="w",
                        encoding="utf-8",
                    ) as temp:
                        temp.write(target_code)
                        temp_name = temp.name

                    result = subprocess.run(
                        ["node", "--check", temp_name],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )

                    if result.returncode == 0:
                        return "✅ JavaScript syntax is valid."
                    return f"❌ JS Syntax Error:\n{(result.stderr or '').strip()}"
                finally:
                    if temp_name and os.path.exists(temp_name):
                        os.unlink(temp_name)

            return f"❌ Syntax check not supported for {target_language}"

        except SyntaxError as exc:
            return f"❌ Syntax Error: {exc.msg} at line {exc.lineno}"
        except FileNotFoundError:
            return "❌ Error: Node.js is not installed or not available in PATH."
        except Exception as exc:
            return f"❌ Error: {exc}"

    def _validate_code_before_save(self, filepath: str, content: str):
        suffix = Path(filepath).suffix.lower()

        if suffix == ".py":
            try:
                ast.parse(content)
                return True, "✅ Python syntax check passed."
            except SyntaxError as exc:
                return False, f"❌ Python syntax error at line {exc.lineno}: {exc.msg}"

        if suffix == ".js":
            temp_name = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w", encoding="utf-8") as temp:
                    temp.write(content)
                    temp_name = temp.name

                result = subprocess.run(
                    ["node", "--check", temp_name],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode == 0:
                    return True, "✅ JavaScript syntax check passed."
                return False, f"❌ JavaScript syntax error:\n{(result.stderr or '').strip()}"
            except FileNotFoundError:
                return True, "⚠️ Node.js not available, JavaScript syntax check skipped."
            except Exception as exc:
                return False, f"❌ JavaScript validation error: {exc}"
            finally:
                if temp_name and os.path.exists(temp_name):
                    os.unlink(temp_name)

        return True, "✅ File validation passed."

    def _run_smoke_test(self, target_path: Path, content: str):
        if self._looks_like_gui_or_long_running(target_path.name, content):
            return True, "⚠️ Smoke test skipped for GUI, interactive, or long-running app."

        try:
            if target_path.suffix.lower() == ".py":
                cmd = [sys.executable, str(target_path)]
            elif target_path.suffix.lower() == ".js":
                cmd = ["node", str(target_path)]
            else:
                return True, "⚠️ Smoke test skipped for this file type."

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(self._base_dir()),
            )

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()

            if result.returncode == 0:
                extra = f" Output: {stdout[:120]}" if stdout else ""
                return True, f"✅ Smoke test passed.{extra}"
            return False, f"❌ Smoke test failed: {stderr or stdout or 'Unknown runtime error.'}"

        except subprocess.TimeoutExpired:
            return True, "⚠️ Smoke test skipped because execution exceeded 5 seconds."
        except FileNotFoundError as exc:
            return True, f"⚠️ Smoke test skipped: runtime not available ({exc})."
        except Exception as exc:
            return False, f"❌ Smoke test error: {exc}"

    @tool_registry.register(
        name="create_code_file",
        description="Saves code to a file.",
        args_description="filepath, content, overwrite(optional), auto_rename(optional)",
    )
    def create_code_file(
        self,
        filepath: str = None,
        content: str = None,
        overwrite: bool = False,
        auto_rename: bool = False,
        **kwargs,
    ) -> str:
        file_value = self._extract_value(filepath, kwargs, "filepath", "path", "filename")
        code_value = self._extract_value(content, kwargs, "content", "code", "text")
        task_value = self._extract_value(None, kwargs, "task", "description", "prompt") or ""
        language_value = self._extract_value(None, kwargs, "language") or "python"
        overwrite = bool(self._extract_value(overwrite, kwargs, "overwrite"))
        auto_rename = bool(self._extract_value(auto_rename, kwargs, "auto_rename", "rename_if_exists"))

        if not code_value:
            return "❌ Error: Missing content."

        explicit_filename = bool(file_value)
        if file_value:
            safe_path = self._sanitize_filepath(file_value)
        else:
            safe_path = self._guess_filename_from_task(task_value, language_value, str(code_value))
            auto_rename = True

        if not safe_path or safe_path in {"generated_file.txt", ".txt"}:
            safe_path = self._guess_filename_from_task(task_value, language_value, str(code_value))
            auto_rename = True

        if not Path(safe_path).suffix:
            safe_path = safe_path + self._guess_extension(language_value, str(code_value))

        code_text = self._clean_text(code_value)
        if safe_path.lower().endswith(".py"):
            code_text = self._repair_tkinter_code(code_text)

        requested_path = self._base_dir() / Path(safe_path).name
        target_path, conflict_message = self._handle_existing_file_conflict(
            requested_path,
            overwrite=overwrite,
            auto_rename=auto_rename and not overwrite,
        )
        if target_path is None:
            return conflict_message

        is_valid, validation_message = self._validate_code_before_save(target_path.name, code_text)

        auto_fixed = False
        if not is_valid:
            repaired_code = self._attempt_auto_fix(target_path.name, code_text)
            if repaired_code != code_text:
                retry_valid, retry_message = self._validate_code_before_save(target_path.name, repaired_code)
                if retry_valid:
                    code_text = repaired_code
                    is_valid = True
                    validation_message = retry_message + "\n✅ Auto-repair applied before save."
                    auto_fixed = True

        if not is_valid:
            return (
                f"❌ Save aborted for {target_path.name}.\n"
                f"{validation_message}\n"
                f"Use create_code_file again with corrected code."
            )

        target_path.write_text(code_text, encoding="utf-8")

        smoke_ok, smoke_message = self._run_smoke_test(target_path, code_text)

        if hasattr(self, "gui") and getattr(self, "gui", None) is not None:
            try:
                self.gui.display_code(code_text)
            except Exception:
                pass

        status_lines = [f"✅ File {target_path.name} saved successfully.", validation_message]
        if conflict_message:
            status_lines.append(conflict_message)
        if explicit_filename and requested_path != target_path:
            status_lines.append(f"⚠️ Requested filename was changed to avoid overwrite: {target_path.name}")
        if auto_fixed:
            status_lines.append("✅ Common issues were repaired automatically.")
        status_lines.append(smoke_message)

        if not smoke_ok:
            status_lines.append("⚠️ Review and correct the code, then save again.")

        return "\n".join(status_lines)

    @tool_registry.register(
        name="write_file",
        description="Writes text or code to a file.",
        args_description="filepath, content",
    )
    def write_file(self, filepath: str = None, content: str = None, **kwargs) -> str:
        return self.create_code_file(filepath=filepath, content=content, **kwargs)

    @tool_registry.register(
        name="run_file",
        description="Runs a saved file and returns output.",
        args_description="filepath",
    )
    def run_file(self, filepath: str = None, **kwargs) -> str:
        file_value = self._extract_value(filepath, kwargs, "filepath", "path", "filename")
        if not file_value:
            return "❌ Error: Missing filepath."

        safe_path = self._sanitize_filepath(file_value)
        target_path = self._base_dir() / Path(safe_path).name

        if not target_path.exists():
            return f"❌ Error: File not found: {target_path.name}"

        lowered_name = target_path.name.lower()
        file_text = target_path.read_text(encoding="utf-8", errors="ignore")
        looks_like_gui = (
            lowered_name.endswith(".py")
            and (
                "tkinter" in file_text.lower()
                or "customtkinter" in file_text.lower()
                or "pyqt" in file_text.lower()
                or "root.mainloop" in file_text
                or "app.mainloop" in file_text
                or "tk.tk()" in file_text.lower()
            )
        )

        if looks_like_gui:
            return (
                f"⚠️ Skipped automatic run for GUI app: {target_path.name}. "
                f"Run it manually to interact with the window."
            )

        try:
            if target_path.suffix.lower() == ".py":
                cmd = [sys.executable, str(target_path)]
            elif target_path.suffix.lower() == ".js":
                cmd = ["node", str(target_path)]
            else:
                return f"❌ Error: Unsupported file type: {target_path.suffix}"

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self._base_dir()),
            )

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()

            if result.returncode == 0:
                return stdout if stdout else f"✅ {target_path.name} executed successfully."
            return f"❌ Runtime Error:\n{stderr or 'Unknown runtime error.'}"

        except subprocess.TimeoutExpired:
            return "❌ Error: Execution timed out (30s limit)."
        except FileNotFoundError as exc:
            return f"❌ System Error: Required runtime not found: {exc}"
        except Exception as exc:
            return f"❌ System Error: {exc}"

    @tool_registry.register(
        name="detect_code_language",
        description="Detect the likely programming language of a code snippet.",
        args_description="code",
    )
    def detect_code_language(self, code: str = None, **kwargs) -> str:
        text = self._clean_text(self._extract_value(code, kwargs, "code", "content", "text"))
        if not text:
            return "❌ Error: No code provided."

        checks = [
            ("python", ["def ", "import ", "if __name__ ==", "print(", "tkinter", "class "]),
            ("javascript", ["function ", "const ", "let ", "console.log", "=>", "require("]),
            ("html", ["<!doctype html", "<html", "<body", "<div", "<head"]),
            ("css", ["{", "}", "color:", "display:", "margin:"]),
            ("sql", ["select ", "insert into", "update ", "delete from", "create table"]),
        ]

        lowered = text.lower()
        scores = {}
        for language, markers in checks:
            scores[language] = sum(1 for marker in markers if marker in lowered)

        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return "unknown"
        return best

    @tool_registry.register(
        name="auto_correct_code",
        description="Apply common automatic corrections to code using code text plus optional error details.",
        args_description="code, language, error_message",
    )
    def auto_correct_code(self, code: str = None, language: str = "python", error_message: str = "", **kwargs) -> str:
        raw_code = self._extract_value(code, kwargs, "code", "content", "text")
        if not raw_code:
            return "❌ Error: No code provided."

        lang = (self._extract_value(language, kwargs, "language") or "python").lower()
        corrected = self._clean_text(raw_code)
        error_text = self._clean_text(error_message or kwargs.get("error") or kwargs.get("message") or "")

        if lang in {"python", "py"}:
            corrected = self._attempt_auto_fix("generated.py", corrected)
            if "expected an indented block" in error_text.lower() and corrected.rstrip().endswith(":"):
                corrected += "\n    pass\n"
            corrected = re.sub(r"\n{3,}", "\n\n", corrected)
            return corrected

        if lang in {"javascript", "js", "node"}:
            corrected = corrected.replace("var ", "let ")
            corrected = re.sub(r"console\.log\(([^)]*)\)\s*$", r"console.log(\1);", corrected, flags=re.MULTILINE)
            return corrected

        return corrected

    @tool_registry.register(
        name="explain_code",
        description="Explain the structure of code by listing important parts and observations.",
        args_description="code, language",
    )
    def explain_code(self, code: str = None, language: str = "python", **kwargs) -> str:
        text = self._clean_text(self._extract_value(code, kwargs, "code", "content", "text"))
        if not text:
            return "❌ Error: No code provided."

        lang = (self._extract_value(language, kwargs, "language") or self.detect_code_language(text)).lower()
        lines = text.splitlines()
        summary = [f"Language: {lang}", f"Total lines: {len(lines)}"]

        if lang == "python":
            try:
                tree = ast.parse(text)
                funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                imports = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports.extend(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom):
                        imports.append(node.module or "")
                summary.append(f"Functions: {', '.join(funcs) if funcs else 'None'}")
                summary.append(f"Classes: {', '.join(classes) if classes else 'None'}")
                summary.append(f"Imports: {', '.join(sorted(set(filter(None, imports)))) if imports else 'None'}")
            except Exception as exc:
                summary.append(f"Could not fully parse code: {exc}")
        else:
            summary.append("This tool currently provides the strongest explanations for Python code.")

        return "\n".join(summary)

    @tool_registry.register(
        name="summarize_code_file",
        description="Read a code file and summarize its likely purpose.",
        args_description="filepath",
    )
    def summarize_code_file(self, filepath: str = None, **kwargs) -> str:
        file_value = self._extract_value(filepath, kwargs, "filepath", "path", "filename")
        if not file_value:
            return "❌ Error: Missing filepath."

        target = self._base_dir() / Path(self._sanitize_filepath(file_value)).name
        if not target.exists():
            return f"❌ Error: File not found: {target.name}"

        text = target.read_text(encoding="utf-8", errors="ignore")
        language = self.detect_code_language(text)
        return f"File: {target.name}\n{self.explain_code(code=text, language=language)}"

    @tool_registry.register(
        name="extract_imports",
        description="Extract imports or dependencies from source code.",
        args_description="code, language",
    )
    def extract_imports(self, code: str = None, language: str = "python", **kwargs) -> str:
        text = self._clean_text(self._extract_value(code, kwargs, "code", "content", "text"))
        if not text:
            return "❌ Error: No code provided."

        lang = (self._extract_value(language, kwargs, "language") or self.detect_code_language(text)).lower()
        imports = []

        if lang == "python":
            try:
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports.extend(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        imports.append(module)
            except Exception as exc:
                return f"❌ Error parsing Python code: {exc}"
        elif lang == "javascript":
            imports.extend(re.findall(r"require\(['\"]([^'\"]+)['\"]\)", text))
            imports.extend(re.findall(r"from\s+['\"]([^'\"]+)['\"]", text))
        else:
            return f"❌ Import extraction not supported for {lang}"

        clean_imports = sorted(set(filter(None, imports)))
        return "\n".join(clean_imports) if clean_imports else "No imports found."

    @tool_registry.register(
        name="list_code_symbols",
        description="List functions, classes, and key symbols in source code.",
        args_description="code, language",
    )
    def list_code_symbols(self, code: str = None, language: str = "python", **kwargs) -> str:
        text = self._clean_text(self._extract_value(code, kwargs, "code", "content", "text"))
        if not text:
            return "❌ Error: No code provided."

        lang = (self._extract_value(language, kwargs, "language") or self.detect_code_language(text)).lower()
        if lang == "python":
            try:
                tree = ast.parse(text)
                funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                assigns = [target.id for node in ast.walk(tree) if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)]
                return "\n".join([
                    f"Functions: {', '.join(funcs) if funcs else 'None'}",
                    f"Classes: {', '.join(classes) if classes else 'None'}",
                    f"Variables: {', '.join(sorted(set(assigns))) if assigns else 'None'}",
                ])
            except Exception as exc:
                return f"❌ Error parsing Python code: {exc}"

        functions = re.findall(r"function\s+([A-Za-z_][A-Za-z0-9_]*)", text)
        classes = re.findall(r"class\s+([A-Za-z_][A-Za-z0-9_]*)", text)
        return "\n".join([
            f"Functions: {', '.join(functions) if functions else 'None'}",
            f"Classes: {', '.join(classes) if classes else 'None'}",
        ])

    @tool_registry.register(
        name="count_lines_of_code",
        description="Count total, blank, comment, and code lines.",
        args_description="code, language",
    )
    def count_lines_of_code(self, code: str = None, language: str = "python", **kwargs) -> str:
        text = self._extract_value(code, kwargs, "code", "content", "text")
        if not text:
            return "❌ Error: No code provided."

        lang = (self._extract_value(language, kwargs, "language") or self.detect_code_language(text)).lower()
        lines = str(text).splitlines()
        total = len(lines)
        blank = sum(1 for line in lines if not line.strip())
        if lang == "python":
            comments = sum(1 for line in lines if line.strip().startswith("#"))
        elif lang in {"javascript", "js"}:
            comments = sum(1 for line in lines if line.strip().startswith("//"))
        else:
            comments = 0
        code_lines = total - blank - comments
        return f"Total: {total}\nCode: {code_lines}\nComments: {comments}\nBlank: {blank}"

    @tool_registry.register(
        name="generate_filename",
        description="Generate a clean filename from a coding task and language.",
        args_description="task, language",
    )
    def generate_filename(self, task: str = None, language: str = "python", **kwargs) -> str:
        task_text = self._extract_value(task, kwargs, "task", "description", "prompt") or "generated app"
        lang = self._extract_value(language, kwargs, "language") or "python"
        return self._guess_filename_from_task(task_text, lang, "")

    @tool_registry.register(
        name="create_test_stub",
        description="Generate a starter unit test file for Python or JavaScript code.",
        args_description="filepath, language",
    )
    def create_test_stub(self, filepath: str = None, language: str = "python", **kwargs) -> str:
        file_value = self._extract_value(filepath, kwargs, "filepath", "path", "filename")
        lang = (self._extract_value(language, kwargs, "language") or "python").lower()
        if not file_value:
            return "❌ Error: Missing filepath."

        source_name = Path(self._sanitize_filepath(file_value)).name
        stem = Path(source_name).stem
        if lang in {"python", "py"}:
            content = dedent(
                f'''
                import unittest
                import {stem}


                class Test{stem.title().replace('_', '')}(unittest.TestCase):
                    def test_placeholder(self):
                        self.assertTrue(True)


                if __name__ == "__main__":
                    unittest.main()
                '''
            ).strip()
            test_name = f"test_{stem}.py"
        else:
            content = dedent(
                f'''
                const assert = require("assert");
                const subject = require("./{stem}");

                assert.ok(subject);
                console.log("Test placeholder passed.");
                '''
            ).strip()
            test_name = f"test_{stem}.js"

        return self.create_code_file(filepath=test_name, content=content, language=lang)

    @tool_registry.register(
        name="generate_requirements_from_code",
        description="Generate a simple requirements list from Python imports.",
        args_description="code",
    )
    def generate_requirements_from_code(self, code: str = None, **kwargs) -> str:
        imports = self.extract_imports(code=code, language="python", **kwargs)
        if imports.startswith("❌"):
            return imports

        stdlib_hints = {
            "os", "sys", "re", "json", "math", "time", "datetime", "pathlib", "tempfile", "subprocess", "threading", "unittest", "sqlite3", "http", "socketserver", "ast"
        }
        packages = []
        for item in imports.splitlines():
            root = item.split(".")[0].strip()
            if root and root not in stdlib_hints:
                packages.append(root)
        packages = sorted(set(packages))
        return "\n".join(packages) if packages else "No third-party requirements detected."

    @tool_registry.register(
        name="format_python_code",
        description="Apply simple formatting cleanup to Python code.",
        args_description="code",
    )
    def format_python_code(self, code: str = None, **kwargs) -> str:
        text = self._clean_text(self._extract_value(code, kwargs, "code", "content", "text"))
        if not text:
            return "❌ Error: No code provided."
        lines = [line.rstrip() for line in text.splitlines()]
        formatted = "\n".join(lines)
        formatted = re.sub(r"\n{3,}", "\n\n", formatted)
        return formatted.strip() + "\n"

    @tool_registry.register(
        name="convert_indentation",
        description="Convert indentation in code to a given number of spaces.",
        args_description="code, spaces",
    )
    def convert_indentation(self, code: str = None, spaces: int = 4, **kwargs) -> str:
        text = self._extract_value(code, kwargs, "code", "content", "text")
        if not text:
            return "❌ Error: No code provided."
        spaces = max(1, min(8, int(spaces)))
        converted = str(text).replace("\t", " " * spaces)
        return converted

    @tool_registry.register(
        name="strip_comments",
        description="Remove simple single-line comments from code.",
        args_description="code, language",
    )
    def strip_comments(self, code: str = None, language: str = "python", **kwargs) -> str:
        text = self._extract_value(code, kwargs, "code", "content", "text")
        if not text:
            return "❌ Error: No code provided."
        lang = (self._extract_value(language, kwargs, "language") or self.detect_code_language(text)).lower()
        output = []
        for line in str(text).splitlines():
            stripped = line.lstrip()
            if lang == "python" and stripped.startswith("#"):
                continue
            if lang in {"javascript", "js"} and stripped.startswith("//"):
                continue
            output.append(line)
        return "\n".join(output)

    @tool_registry.register(
        name="search_in_code",
        description="Search for a text pattern inside source code.",
        args_description="code, pattern",
    )
    def search_in_code(self, code: str = None, pattern: str = "", **kwargs) -> str:
        text = self._extract_value(code, kwargs, "code", "content", "text")
        search_pattern = self._extract_value(pattern, kwargs, "pattern", "query") or ""
        if not text or not search_pattern:
            return "❌ Error: Both code and pattern are required."

        matches = []
        for index, line in enumerate(str(text).splitlines(), 1):
            if search_pattern in line:
                matches.append(f"{index}: {line}")
        return "\n".join(matches) if matches else "No matches found."

    @tool_registry.register(
        name="diff_code_versions",
        description="Show a unified diff between old code and new code.",
        args_description="old_code, new_code",
    )
    def diff_code_versions(self, old_code: str = None, new_code: str = None, **kwargs) -> str:
        before = self._extract_value(old_code, kwargs, "old_code", "before", "source")
        after = self._extract_value(new_code, kwargs, "new_code", "after", "target")
        if before is None or after is None:
            return "❌ Error: Both old_code and new_code are required."

        diff = difflib.unified_diff(
            str(before).splitlines(),
            str(after).splitlines(),
            fromfile="old_code",
            tofile="new_code",
            lineterm="",
        )
        result = "\n".join(diff)
        return result if result else "No differences found."

    @tool_registry.register(
        name="create_readme_stub",
        description="Create a simple README markdown file for a project.",
        args_description="project_name, description, filename",
    )
    def create_readme_stub(self, project_name: str = "Project", description: str = "", filename: str = "README.md", **kwargs) -> str:
        project = self._extract_value(project_name, kwargs, "project_name", "name") or "Project"
        desc = self._extract_value(description, kwargs, "description", "content") or "Project description."
        file_value = self._extract_value(filename, kwargs, "filename", "filepath") or "README.md"
        content = dedent(
            f'''
            # {project}

            {desc}

            ## Features
            - Starter documentation
            - Add your usage instructions here

            ## Run
            Describe how to install and run this project.
            '''
        ).strip() + "\n"
        return self.create_code_file(filepath=file_value, content=content, language="markdown")

    @tool_registry.register(
        name="create_json_stub",
        description="Create a starter JSON structure from a short description.",
        args_description="description",
    )
    def create_json_stub(self, description: str = "", **kwargs) -> str:
        desc = self._extract_value(description, kwargs, "description", "task", "prompt") or "data"
        key = self._slugify(desc).split("_")[0] or "item"
        return json.dumps({key: {"example": True, "description": desc}}, indent=2)

    @tool_registry.register(
        name="create_html_boilerplate",
        description="Create a starter HTML page.",
        args_description="title",
    )
    def create_html_boilerplate(self, title: str = "Web Page", **kwargs) -> str:
        page_title = self._extract_value(title, kwargs, "title", "name") or "Web Page"
        return self._generate_html_template(page_title)

    @tool_registry.register(
        name="create_css_boilerplate",
        description="Create a starter CSS stylesheet.",
        args_description="description",
    )
    def create_css_boilerplate(self, description: str = "", **kwargs) -> str:
        return self._generate_css_template(self._extract_value(description, kwargs, "description", "task") or "styles")

    @tool_registry.register(
        name="create_markdown_doc",
        description="Create a markdown document from a title and body text.",
        args_description="title, content",
    )
    def create_markdown_doc(self, title: str = "Document", content: str = "", **kwargs) -> str:
        doc_title = self._extract_value(title, kwargs, "title", "name") or "Document"
        body = self._extract_value(content, kwargs, "content", "text", "description") or ""
        return f"# {doc_title}\n\n{body}\n"
