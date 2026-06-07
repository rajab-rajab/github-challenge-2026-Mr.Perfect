from tool_registry import tool_registry

import datetime
import hashlib
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


class FileToolsMixin:
    def _base_dir(self) -> Path:
        return Path(getattr(self, "BASE_DIR", Path.cwd()))

    def _clean_text(self, value):
        if value is None:
            return ""

        text = str(value)
        text = text.replace("&lt;", "<").replace("&gt;", ">")
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

        return text.strip()

    def _extract_value(self, direct_value=None, kwargs=None, *names):
        if direct_value not in (None, ""):
            return direct_value

        kwargs = kwargs or {}
        for name in names:
            if name in kwargs and kwargs[name] not in (None, ""):
                return kwargs[name]
        return None

    def _sanitize_path(self, raw_path) -> Path:
        text = self._clean_text(raw_path)

        if text.startswith("{") and text.endswith("}"):
            try:
                data = json.loads(text)
                text = data.get("filepath") or data.get("path") or data.get("filename") or text
            except Exception:
                pass

        text = text.replace('"', "").replace("'", "").strip()
        text = re.sub(r"\s+", "_", text)
        text = re.sub(r"[^A-Za-z0-9_./\\ -]", "", text)
        text = text.replace("\\", "/")
        text = re.sub(r"/+", "/", text)
        text = text.strip()

        if not text:
            text = "generated_file.txt"

        path = Path(text)
        if path.is_absolute():
            return path
        return self._base_dir() / path.name

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
            return suggested, f"Warning: File already existed. Saved as {suggested.name} instead."

        message = (
            f"Error: File already exists: {target_path.name}\n"
            f"Suggested available filename: {suggested.name}\n"
            f"Use overwrite=True to replace it or auto_rename=True to save as the suggested filename."
        )
        return None, message

    def _protected_paths(self):
        return {
            "C:\\",
            "D:\\",
            "E:\\",
            "F:\\",
            "/",
            "/bin",
            "/boot",
            "/dev",
            "/etc",
            "/lib",
            "/lib64",
            "/proc",
            "/root",
            "/run",
            "/sbin",
            "/sys",
            "/usr",
            "/var",
            "/Windows",
        }

    def _is_protected_delete_target(self, path: Path):
        resolved = path.resolve()
        resolved_str = str(resolved)
        lowered = resolved_str.lower()
        name_lower = resolved.name.lower()

        if resolved_str in self._protected_paths():
            return f"Error: CANNOT DELETE protected path: {resolved}"

        protected_names = {
            "agent.py",
            "main.py",
            "requirements.txt",
            "readme.md",
            "license",
            "python.exe",
            "pythonw.exe",
            "py.exe",
        }
        if name_lower in protected_names:
            return f"Error: CANNOT DELETE protected file: {resolved.name}"

        for token in ("windows", "system32", "syswow64", "program files", "venv", ".venv"):
            if token in lowered:
                return f"Error: CANNOT DELETE protected location: {resolved}"

        for pattern in (".sys", ".dll", "bootmgr", "boot.ini", "config.sys", "autoexec.bat"):
            if pattern in name_lower:
                return f"Error: CANNOT DELETE system file: {resolved.name}"

        return None

    @tool_registry.register(
        name="list_files",
        description="List files in a directory.",
        args_description="path, pattern, include_hidden",
    )
    def list_files(self, path: str = ".", pattern: str = "*", include_hidden: bool = False) -> str:
        try:
            directory = self._sanitize_path(path)
            if not directory.exists():
                return f"Error: Path does not exist: {directory}"
            if not directory.is_dir():
                return f"Error: Not a directory: {directory}"

            regex = None
            if pattern and pattern != "*":
                regex = re.compile("^" + re.escape(pattern).replace(r"\*", ".*") + "$")

            files = []
            for item in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if not include_hidden and item.name.startswith("."):
                    continue
                if regex and not regex.match(item.name):
                    continue
                size = item.stat().st_size if item.is_file() else 0
                kind = "[D]" if item.is_dir() else "[F]"
                files.append(f"{kind} {item.name} ({size:,} bytes)")

            return "\n".join(files) if files else "Directory is empty"
        except PermissionError:
            return "Error: Permission denied"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="read_file",
        description="Read contents of a file.",
        args_description="filepath, max_lines, encoding",
    )
    def read_file(self, filepath: str, max_lines: int = 100, encoding: str = "utf-8") -> str:
        try:
            path = self._sanitize_path(filepath)
            if not path.exists():
                return f"Error: File does not exist: {path.name}"
            if path.stat().st_size > 5 * 1024 * 1024:
                return "Error: File too large (>5MB). Use read_file_lines for large files."

            lines = []
            with open(path, "r", encoding=encoding, errors="ignore") as file:
                for _ in range(max_lines):
                    line = file.readline()
                    if not line:
                        break
                    lines.append(line)

            file_info = f"File: {path.name} | Size: {path.stat().st_size:,} bytes | Lines read: {len(lines)}"
            return file_info + "\n" + ("-" * 50) + "\n" + "".join(lines)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="read_file_lines",
        description="Read specific lines from a file.",
        args_description="filepath, start_line, count",
    )
    def read_file_lines(self, filepath: str, start_line: int = 1, count: int = 50) -> str:
        try:
            path = self._sanitize_path(filepath)
            if not path.exists():
                return f"Error: File does not exist: {path.name}"

            lines = []
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                for i, line in enumerate(file, 1):
                    if i >= start_line:
                        lines.append(line.rstrip("\n"))
                    if len(lines) >= count:
                        break

            end_line = start_line + len(lines) - 1 if lines else start_line
            return f"Lines {start_line}-{end_line}:\n" + ("-" * 50) + "\n" + "\n".join(lines)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="write_file",
        description="Write content to a file.",
        args_description="filepath, content, append, overwrite(optional), auto_rename(optional)",
    )
    def write_file(
        self,
        filepath: str,
        content: str,
        append: bool = False,
        overwrite: bool = False,
        auto_rename: bool = False,
    ) -> str:
        try:
            path = self._sanitize_path(filepath)
            text = self._clean_text(content)
            path.parent.mkdir(parents=True, exist_ok=True)

            conflict_message = ""
            if not append:
                path, conflict_message = self._handle_existing_file_conflict(
                    path,
                    overwrite=bool(overwrite),
                    auto_rename=bool(auto_rename),
                )
                if path is None:
                    return conflict_message

            mode = "a" if append else "w"
            with open(path, mode, encoding="utf-8") as file:
                file.write(text)

            result = f"Successfully {'appended to' if append else 'wrote'} file: {path.name}"
            if conflict_message:
                result += f"\n{conflict_message}"
            return result
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_current_directory",
        description="Get current working directory.",
        args_description="",
    )
    def get_current_directory(self) -> str:
        return str(self._base_dir())

    @tool_registry.register(
        name="change_directory",
        description="Change current working directory.",
        args_description="path",
    )
    def change_directory(self, path: str) -> str:
        try:
            new_path = self._sanitize_path(path)
            if not new_path.exists():
                return f"Error: Directory does not exist: {new_path}"
            if not new_path.is_dir():
                return f"Error: Not a directory: {new_path}"
            os.chdir(new_path)
            self.BASE_DIR = new_path
            return f"Changed directory to: {new_path}"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_file_info",
        description="Get detailed file information.",
        args_description="filepath",
    )
    def get_file_info(self, filepath: str) -> str:
        try:
            path = self._sanitize_path(filepath)
            if not path.exists():
                return f"Error: File does not exist: {path.name}"

            stat = path.stat()
            created = datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            return (
                f"Path: {path.resolve()}\n"
                f"Size: {stat.st_size:,} bytes ({stat.st_size / (2 ** 20):.2f} MB)\n"
                f"Created: {created}\n"
                f"Modified: {modified}\n"
                f"Type: {'Directory' if path.is_dir() else 'File'}\n"
                f"Permissions: {oct(stat.st_mode)[-3:]}"
            )
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="search_files",
        description="Search for files matching a pattern.",
        args_description="pattern, path, max_results",
    )
    def search_files(self, pattern: str, path: str = ".", max_results: int = 20) -> str:
        try:
            base = self._sanitize_path(path)
            if not base.exists() or not base.is_dir():
                return f"Error: Invalid directory: {base}"

            results = []
            needle = self._clean_text(pattern).lower()
            for item in base.rglob("*"):
                if needle in item.name.lower():
                    results.append(item)
                if len(results) >= max_results:
                    break

            if not results:
                return f"No files found matching '{needle}' in {base}"

            output = [f"Found {len(results)} matching files:", "-" * 50]
            for item in results:
                size = item.stat().st_size if item.is_file() else 0
                kind = "[D]" if item.is_dir() else "[F]"
                output.append(f"{kind} {item} ({size:,} bytes)")
            return "\n".join(output)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="delete_file",
        description="Delete a file or empty folder with security restrictions.",
        args_description="filepath",
    )
    def delete_file(self, filepath: str) -> str:
        try:
            path = self._sanitize_path(filepath).resolve()
            if not path.exists():
                return f"Error: Path does not exist: {filepath}"

            protected = self._is_protected_delete_target(path)
            if protected:
                return protected

            if path.is_dir():
                try:
                    contents = list(path.iterdir())
                except PermissionError:
                    return f"Error: Permission denied accessing: {path.name}"

                if contents:
                    return (
                        f"Error: Cannot delete non-empty folder: {path.name}\n"
                        f"Folder contains {len(contents)} items."
                    )
                return f"CONFIRM_DELETE:{path}|FOLDER:{path.name}"

            return f"CONFIRM_DELETE:{path}|FILE:{path.name}|SIZE:{path.stat().st_size}"
        except PermissionError:
            return f"Error: Permission denied: {filepath}"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="confirm_delete",
        description="Actually perform the deletion after user confirmation.",
        args_description="filepath",
    )
    def confirm_delete(self, filepath: str) -> str:
        try:
            path = self._sanitize_path(filepath)
            if not path.exists():
                return f"Error: Path no longer exists: {filepath}"

            if path.is_dir():
                if any(path.iterdir()):
                    return "Error: Folder is no longer empty. Aborted."
                path.rmdir()
                return f"✅ Deleted empty folder: {path.name}"

            path.unlink()
            return f"✅ Deleted file: {path.name}"
        except PermissionError:
            return "Error: Permission denied"
        except FileNotFoundError:
            return "Error: File not found"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="create_folder",
        description="Create a new folder/directory.",
        args_description="folderpath",
    )
    def create_folder(self, folderpath: str) -> str:
        try:
            path = self._sanitize_path(folderpath)
            if path.exists():
                return f"Error: Folder already exists: {path.name}"
            path.mkdir(parents=True, exist_ok=False)
            return f"✅ Created folder: {path.name}\nPath: {path.resolve()}"
        except FileExistsError:
            return f"Error: Folder already exists: {folderpath}"
        except PermissionError:
            return f"Error: Permission denied: {folderpath}"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="copy_file",
        description="Copy a file or folder to destination.",
        args_description="source, destination",
    )
    def copy_file(self, source: str, destination: str) -> str:
        try:
            src = self._sanitize_path(source)
            dst = self._sanitize_path(destination)
            if not src.exists():
                return f"Error: Source does not exist: {source}"

            if dst.exists() and dst.is_dir():
                dst = dst / src.name

            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=False)
                return f"✅ Copied folder: {src.name}\nTo: {dst.resolve()}"

            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return f"✅ Copied file: {src.name}\nTo: {dst.resolve()}"
        except FileExistsError:
            return f"Error: Destination already exists: {destination}"
        except PermissionError:
            return "Error: Permission denied"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="move_file",
        description="Move a file or folder to destination.",
        args_description="source, destination",
    )
    def move_file(self, source: str, destination: str) -> str:
        try:
            src = self._sanitize_path(source)
            dst = self._sanitize_path(destination)
            if not src.exists():
                return f"Error: Source does not exist: {source}"

            if dst.exists() and dst.is_dir():
                dst = dst / src.name

            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return f"✅ Moved {'folder' if src.is_dir() else 'file'}: {src.name}\nTo: {dst.resolve()}"
        except FileExistsError:
            return f"Error: Destination already exists: {destination}"
        except PermissionError:
            return "Error: Permission denied"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="rename_file",
        description="Rename a file or folder.",
        args_description="oldpath, newname",
    )
    def rename_file(self, oldpath: str, newname: str) -> str:
        try:
            src = self._sanitize_path(oldpath)
            if not src.exists():
                return f"Error: Path does not exist: {oldpath}"

            clean_newname = Path(self._clean_text(newname)).name
            dst = src.parent / clean_newname
            if dst.exists():
                return f"Error: Name already exists: {clean_newname}"

            src.rename(dst)
            return f"✅ Renamed: {src.name} -> {clean_newname}\nNew path: {dst.resolve()}"
        except PermissionError:
            return "Error: Permission denied"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_file_hash",
        description="Calculate hash of a file.",
        args_description="filepath, algorithm",
    )
    def get_file_hash(self, filepath: str, algorithm: str = "md5") -> str:
        try:
            path = self._sanitize_path(filepath)
            if not path.exists() or not path.is_file():
                return f"Error: File does not exist: {filepath}"

            hash_funcs = {
                "md5": hashlib.md5,
                "sha1": hashlib.sha1,
                "sha256": hashlib.sha256,
            }
            algo = algorithm.lower()
            if algo not in hash_funcs:
                return f"Error: Unknown algorithm. Use: {', '.join(hash_funcs.keys())}"

            hash_obj = hash_funcs[algo]()
            with open(path, "rb") as file:
                for chunk in iter(lambda: file.read(8192), b""):
                    hash_obj.update(chunk)
            return f"{algo.upper()}={hash_obj.hexdigest()}"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="run_file",
        description="Run code files safely and open HTML files.",
        args_description="filepath",
    )
    def run_file(self, filepath: str = None, **kwargs) -> str:
        try:
            raw_path = self._extract_value(filepath, kwargs, "filepath", "path", "filename")
            if not raw_path:
                return "❌ Error: No filepath provided."

            path = self._sanitize_path(raw_path)
            if not path.exists():
                return f"❌ Error: File not found: {path.name}"

            ext = path.suffix.lower()
            cwd = str(path.parent)

            if ext in {".html", ".htm"}:
                file_uri = path.resolve().as_uri()
                webbrowser.open(file_uri)
                return f"✅ HTML file opened in browser: {file_uri}"

            if ext == ".py":
                file_text = path.read_text(encoding="utf-8", errors="ignore")
                if any(token in file_text for token in ("tkinter", "customtkinter", "mainloop()", "Tk()")):
                    return f"⚠️ Skipped automatic run for GUI app: {path.name}. Run it manually to interact with the window."
                cmd = [sys.executable, str(path)]
            elif ext == ".js":
                cmd = ["node", str(path)]
            elif ext == ".php":
                cmd = ["php", str(path)]
            elif ext == ".java":
                cmd = ["java", str(path)]
            elif ext == ".c":
                exe_path = path.with_suffix(".exe")
                compile_result = subprocess.run(["gcc", str(path), "-o", str(exe_path)], capture_output=True, text=True, cwd=cwd)
                if compile_result.returncode != 0:
                    return f"❌ Compilation Failed:\n{compile_result.stderr.strip()}"
                cmd = [str(exe_path)]
            elif ext == ".cpp":
                exe_path = path.with_suffix(".exe")
                compile_result = subprocess.run(["g++", str(path), "-o", str(exe_path)], capture_output=True, text=True, cwd=cwd)
                if compile_result.returncode != 0:
                    return f"❌ Compilation Failed:\n{compile_result.stderr.strip()}"
                cmd = [str(exe_path)]
            else:
                try:
                    os.startfile(str(path))
                    return f"✅ Opened {path.name} with default application."
                except AttributeError:
                    return f"❌ Unsupported file type for this platform: {path.name}"

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=cwd)
            if result.returncode == 0:
                return f"✅ Execution Successful: {path.name}\n📤 Output:\n{result.stdout.strip() or '(No output)'}"
            return f"❌ Execution Failed: {path.name}\n⚠️ Error:\n{result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return "❌ Error: Execution timed out (30s limit)."
        except Exception as exc:
            return f"❌ System Error: {exc}"

    @tool_registry.register(
        name="create_code_file",
        description="Save source code to a clean file path.",
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
        try:
            raw_path = self._extract_value(filepath, kwargs, "filepath", "path", "filename")
            raw_content = self._extract_value(content, kwargs, "content", "code", "text")
            if not raw_path or raw_content in (None, ""):
                return "❌ Error: Missing filepath or content."

            path = self._sanitize_path(raw_path)
            code = self._clean_text(raw_content)
            path.parent.mkdir(parents=True, exist_ok=True)

            path, conflict_message = self._handle_existing_file_conflict(
                path,
                overwrite=bool(overwrite),
                auto_rename=bool(auto_rename),
            )
            if path is None:
                return f"❌ {conflict_message}"

            path.write_text(code, encoding="utf-8")

            if hasattr(self, "gui") and getattr(self, "gui", None) is not None:
                try:
                    self.gui.display_code(code)
                except Exception:
                    pass

            result = f"✅ File saved successfully at: {path.resolve()}"
            if conflict_message:
                result += f"\n{conflict_message}"
            return result
        except Exception as exc:
            return f"❌ System File Error: {exc}"

    @tool_registry.register(
        name="local_html_file",
        description="Start a local HTTP server and open an HTML file.",
        args_description="filepath",
    )
    def local_html_file(self, filepath: str = None, **kwargs) -> str:
        try:
            raw_path = self._extract_value(filepath, kwargs, "filepath", "path", "filename")
            if not raw_path:
                return "❌ Error: No filename provided."

            target_file = self._sanitize_path(raw_path)
            if not target_file.exists():
                return f"❌ Error: {target_file.name} does not exist."

            port = 8000
            base_dir = target_file.parent

            def start_background_server():
                class LocalHandler(http.server.SimpleHTTPRequestHandler):
                    def __init__(self, *args, **handler_kwargs):
                        super().__init__(*args, directory=str(base_dir), **handler_kwargs)

                    def log_message(self, format, *args):
                        return

                socketserver.TCPServer.allow_reuse_address = True
                try:
                    with socketserver.TCPServer(("", port), LocalHandler) as httpd:
                        httpd.serve_forever()
                except Exception:
                    pass

            server_thread = threading.Thread(target=start_background_server, daemon=True)
            server_thread.start()
            time.sleep(0.2)

            url = f"http://localhost:{port}/{target_file.name}"
            webbrowser.open(url)
            return f"✅ Success! File is now serving at: {url}"
        except Exception as exc:
            return f"❌ Failed to open browser: {exc}"
