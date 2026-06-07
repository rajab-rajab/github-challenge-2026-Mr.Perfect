from tool_registry import tool_registry

import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from urllib.parse import urlparse


class WingetToolsMixin:
    def _clean_text(self, value):
        if value is None:
            return ""
        text = str(value)
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
        text = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", text)
        text = text.replace("```", "")
        return text.strip()

    def _extract_payload_value(self, raw_value, *keys):
        text = self._clean_text(raw_value)
        if text.startswith("{") and text.endswith("}"):
            try:
                data = json.loads(text)
                for key in keys:
                    if data.get(key):
                        return self._clean_text(data[key])
            except Exception:
                pass
        return text

    def _run_command(self, command, timeout=60):
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="ignore",
        )

    def _winget_available(self) -> bool:
        try:
            result = self._run_command(["winget", "--version"], timeout=15)
            return result.returncode == 0
        except Exception:
            return False

    def _protected_programs(self):
        default_programs = {
            "windows",
            "microsoft edge",
            "microsoft store",
            "defender",
            "security health",
            "visual c++",
            "webview2",
            "powershell",
            "onedrive",
        }
        return set(getattr(self, "PROTECTED_PROGRAMS", default_programs))

    def _clean_winget_output(self, text: str) -> str:
        text = text or ""
        text = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", text)
        text = re.sub(r"[█▒░━─]+", "", text)
        lines = []
        for line in text.splitlines():
            clean_line = line.strip()
            if clean_line in {"", "-", "\\", "|", "/", "·"}:
                continue
            lines.append(clean_line)
        return "\n".join(lines)

    def _run_powershell(self, command: str, timeout: int = 60) -> str:
        if os.name != "nt":
            return "Error: This tool is available only on Windows."
        result = self._run_command(["powershell", "-Command", command], timeout=timeout)
        output = (result.stdout or result.stderr or "").strip()
        return output or "No output"

    @tool_registry.register(
        name="winget_install",
        description="Installs a program with a 10-minute timeout and aggressive log cleaning.",
        args_description="package_id",
    )
    def winget_install(self, package_id: str) -> str:
        try:
            if not self._winget_available():
                return "Error: winget is not available on this system."

            clean_id = self._extract_payload_value(
                package_id,
                "package_id",
                "id",
                "query",
                "package_name",
                "program_name",
                "name",
            ).strip("'\"")
            if not clean_id:
                return "Error: No package_id provided."

            cmd = ["winget", "install"]
            if "." in clean_id:
                cmd.extend(["--id", clean_id, "--exact"])
            else:
                cmd.append(clean_id)
            cmd.extend(
                [
                    "--silent",
                    "--disable-interactivity",
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ]
            )

            result = self._run_command(cmd, timeout=600)
            output = self._clean_winget_output(result.stdout or result.stderr)

            if result.returncode == 0:
                return f"Successfully installed: {clean_id}\n{output[:500]}"
            if result.returncode == 2316632086:
                return f"Error: Multiple matches for '{clean_id}'. Use the exact package ID from search results."
            return f"Install failed (Code: {result.returncode})\nOutput: {output[:500]}"
        except subprocess.TimeoutExpired:
            return f"Timeout: The installation of {package_id} took longer than 10 minutes."
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_installed_programs_list",
        description="Get list of installed programs for uninstallation selection.",
        args_description="*args, **kwargs",
    )
    def get_installed_programs_list(self, *args, **kwargs) -> str:
        try:
            search_term = "*"
            if args and isinstance(args[0], str):
                search_term = f"*{self._clean_text(args[0])}*"
            elif "program_name" in kwargs:
                search_term = f"*{self._clean_text(kwargs['program_name'])}*"
            elif "program_display_name" in kwargs:
                search_term = f"*{self._clean_text(kwargs['program_display_name'])}*"

            output = ""
            if os.name == "nt":
                cmd = f"""
$programs = @()
$paths = @(
    'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'
)
foreach ($path in $paths) {{
    $prog = Get-ItemProperty -Path $path -ErrorAction SilentlyContinue |
        Where-Object {{ $_.DisplayName -like '{search_term}' -or $_.PsChildName -like '{search_term}' }}
    if ($prog) {{ $programs += $prog }}
}}
if ($programs.Count -gt 0) {{
    $programs | Select-Object DisplayName, UninstallString, Publisher | Format-List | Out-String
}} else {{
    Write-Output 'NOT_FOUND'
}}
"""
                output = self._run_powershell(cmd, timeout=60).strip()

            if "NOT_FOUND" in output or not output:
                if self._winget_available():
                    clean_search = search_term.strip("*")
                    winget_cmd = ["winget", "list", "--accept-source-agreements"]
                    if clean_search:
                        winget_cmd.insert(2, clean_search)
                    winget_res = self._run_command(winget_cmd, timeout=30)
                    if winget_res.returncode == 0 and winget_res.stdout.strip():
                        output = winget_res.stdout.strip()
                    else:
                        output = "NOT_FOUND"

            if output == "NOT_FOUND":
                return "No installed programs found for the requested filter."

            lines = output.splitlines()
            marked_lines = []
            for line in lines:
                marked = line
                for protected in self._protected_programs():
                    if protected in line.lower():
                        marked = line + "  SYSTEM"
                        break
                marked_lines.append(marked)
            return "\n".join(marked_lines)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="winget_upgrade",
        description="Upgrades an existing installed software application to its latest version.",
        args_description="package_id, *args, **kwargs",
    )
    def winget_upgrade(self, package_id: str = "all", *args, **kwargs) -> str:
        try:
            if not self._winget_available():
                return "Error: winget is not available on this system."

            clean_id = self._extract_payload_value(
                package_id,
                "package_id",
                "id",
                "query",
                "package_name",
                "program_name",
                "name",
            )
            if (clean_id.lower() == "all" or not clean_id) and args and isinstance(args[0], str):
                clean_id = self._clean_text(args[0])
            if (clean_id.lower() == "all" or not clean_id) and kwargs:
                clean_id = self._clean_text(
                    kwargs.get("package_id")
                    or kwargs.get("id")
                    or kwargs.get("program_name")
                    or kwargs.get("name")
                    or "all"
                )
            clean_id = clean_id.strip("'\" ") or "all"

            if clean_id.lower() == "all":
                cmd = [
                    "winget",
                    "upgrade",
                    "--all",
                    "--silent",
                    "--disable-interactivity",
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ]
                result = self._run_command(cmd, timeout=600)
            else:
                cmd = [
                    "winget",
                    "upgrade",
                    "--id",
                    clean_id,
                    "--silent",
                    "--disable-interactivity",
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ]
                result = self._run_command(cmd, timeout=300)

            output = self._clean_winget_output(result.stdout or result.stderr)
            if result.returncode == 0:
                return f"Successfully upgraded: {clean_id}"
            return f"Upgrade execution completed for {clean_id}.\nLog: {output[:500]}"
        except Exception as exc:
            return f"Error executing winget upgrade: {exc}"

    @tool_registry.register(
        name="validate_program_safety",
        description="Validate if a program is safe to install (basic checks).",
        args_description="program_name, url",
    )
    def validate_program_safety(self, program_name: str, url: str = "") -> str:
        name_lower = self._clean_text(program_name).lower()
        url_lower = self._clean_text(url).lower()

        for protected in self._protected_programs():
            if protected in name_lower:
                return f"UNSAFE: '{program_name}' appears to be a system program that should not be removed"

        suspicious_domains = ["torrent", "crack", "keygen", "serial", "patch", "activator"]
        for suspicious in suspicious_domains:
            if suspicious in url_lower:
                return "UNSAFE: Download source appears to be pirated software"

        malware_keywords = ["malware", "trojan", "virus", "keylogger", "ransomware", "spyware"]
        for keyword in malware_keywords:
            if keyword in name_lower or keyword in url_lower:
                return f"UNSAFE: Program name or URL contains suspicious keyword: {keyword}"

        if url and not url_lower.startswith("https://"):
            return "WARNING: Download URL is not using HTTPS (insecure connection)"

        safe_domains = [
            "microsoft.com",
            "google.com",
            "adobe.com",
            "github.com",
            "python.org",
            "nodejs.org",
            "git-scm.com",
            "visualstudio.com",
            "sourceforge.net",
            "npmjs.com",
            "pypi.org",
            "rubygems.org",
        ]

        if url:
            try:
                domain = urlparse(url).netloc.lower()
                if any(safe in domain for safe in safe_domains):
                    return "SAFE"
                if domain:
                    return f"WARNING: Download from third-party site ({domain}). Verify before installing."
            except Exception:
                pass

        return "VERIFY_NEEDED"

    @tool_registry.register(
        name="winget_uninstall",
        description="Uninstalls a program cleanly.",
        args_description="package_id",
    )
    def winget_uninstall(self, package_id: str) -> str:
        try:
            if not self._winget_available():
                return "Error: winget is not available on this system."

            clean_id = self._extract_payload_value(
                package_id,
                "package_id",
                "id",
                "query",
                "package_name",
                "program_name",
                "name",
            ).strip("'\" ")
            if not clean_id:
                return "Error: No package_id provided."

            result = self._run_command(
                [
                    "winget",
                    "uninstall",
                    "--id",
                    clean_id,
                    "--silent",
                    "--disable-interactivity",
                    "--accept-source-agreements",
                ],
                timeout=180,
            )

            if result.returncode != 0:
                stdout_err = ((result.stdout or "") + " " + (result.stderr or "")).lower()
                if "no installed package found" in stdout_err or "no package found" in stdout_err:
                    fallback_name = clean_id.split(".")[-1] if "." in clean_id else clean_id
                    result = self._run_command(
                        [
                            "winget",
                            "uninstall",
                            fallback_name,
                            "--silent",
                            "--disable-interactivity",
                            "--accept-source-agreements",
                        ],
                        timeout=180,
                    )

            if result.returncode != 0:
                stdout_err = ((result.stdout or "") + " " + (result.stderr or "")).lower()
                if ("no installed package found" in stdout_err or "no package found" in stdout_err) and os.name == "nt":
                    choco_check = self._run_command(["where", "choco"], timeout=15)
                    if choco_check.returncode == 0:
                        choco_name = clean_id.split(".")[-1].lower() if "." in clean_id else clean_id.lower()
                        result = self._run_command(["choco", "uninstall", choco_name, "-y"], timeout=120)

            output = self._clean_winget_output((result.stdout or "") + "\n" + (result.stderr or ""))
            if result.returncode == 0:
                return f"Successfully uninstalled: {clean_id}"
            return f"Uninstall failed for {clean_id}.\nOutput: {output[:500]}"
        except Exception as exc:
            return f"Error executing winget uninstall: {exc}"

    @tool_registry.register(
        name="check_program_removable",
        description="Check if a program can be safely uninstalled.",
        args_description="program_display_name",
    )
    def check_program_removable(self, program_display_name: str) -> str:
        try:
            clean_name = self._clean_text(program_display_name)
            name_lower = clean_name.lower()
            for protected in self._protected_programs():
                if protected in name_lower:
                    return (
                        f"UNSAFE: '{program_display_name}' is a SYSTEM program and should NOT be uninstalled. "
                        f"Uninstalling this may damage your operating system."
                    )

            if os.name != "nt":
                return f"CHECK_PASSED: '{program_display_name}' appears safe for uninstallation."

            cmd = f"""
$paths = @(
    'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'
)
$found = $false
foreach ($path in $paths) {{
    $prog = Get-ItemProperty -Path $path -ErrorAction SilentlyContinue |
        Where-Object {{ $_.DisplayName -eq '{clean_name.replace("'", "''")}' }}
    if ($prog -and $prog.UninstallString) {{
        Write-Output $prog.UninstallString
        $found = $true
        break
    }}
}}
if (-not $found) {{ Write-Output 'NOT_FOUND' }}
"""
            output = self._run_powershell(cmd, timeout=30).strip()
            if "NOT_FOUND" in output:
                return f"Program '{program_display_name}' not found in installed programs list."
            return f"CHECK_PASSED: '{program_display_name}' appears to be safe for uninstallation.\n\n{output}"
        except Exception as exc:
            return f"Error checking program: {exc}"

    @tool_registry.register(
        name="execute_install",
        description="Execute program installation after user confirmation.",
        args_description="program_name, download_url",
    )
    def execute_install(self, program_name: str, download_url: str) -> str:
        try:
            temp_dir = tempfile.mkdtemp(prefix="mrperfect_install_")
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", self._clean_text(program_name) or "installer")
            file_path = os.path.join(temp_dir, f"{safe_name}_installer.exe")

            request = urllib.request.Request(
                download_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                with open(file_path, "wb") as out_file:
                    shutil.copyfileobj(response, out_file)

            result = self._run_command([file_path], timeout=300)
            try:
                os.remove(file_path)
            except Exception:
                pass

            if result.returncode == 0:
                return f"Installation of '{program_name}' completed successfully!"
            return f"Installation completed with issues:\n{(result.stderr or result.stdout).strip()}"
        except Exception as exc:
            return (
                f"Installation error: {exc}\n\n"
                f"Please download manually from:\n{download_url}\n\n"
                f"Then run the installer manually."
            )

    @tool_registry.register(
        name="execute_uninstall",
        description="Execute program uninstallation after user confirmation.",
        args_description="program_name, uninstall_string",
    )
    def execute_uninstall(self, program_name: str, uninstall_string: str) -> str:
        try:
            clean_cmd = self._clean_text(uninstall_string)
            if not clean_cmd:
                return f"Uninstallation error: Missing uninstall command for {program_name}"

            if "msiexec" in clean_cmd.lower() and "/qn" not in clean_cmd.lower():
                clean_cmd += " /qn /norestart"

            result = self._run_command(["powershell", "-Command", clean_cmd], timeout=300)
            if result.returncode == 0:
                return f"Uninstallation of '{program_name}' completed successfully!"
            return f"Uninstallation completed with issues:\n{(result.stderr or result.stdout).strip()}"
        except subprocess.TimeoutExpired:
            return "Uninstallation timed out. The program may still be removing. Please wait and check manually."
        except Exception as exc:
            return f"Uninstallation error: {exc}"

    @tool_registry.register(
        name="check_program_updates",
        description="Check for program updates online (REQUIRES USER REQUEST).",
        args_description="program_name",
    )
    def check_program_updates(self, program_name: str) -> str:
        if not hasattr(self, "tavily") or not self.tavily:
            return "Error: Tavily API not configured. Set TAVILY_API_KEY for update checks."

        try:
            current_year = datetime.datetime.now().year
            search_results = self.tavily.search(
                query=f"{program_name} latest version {current_year} official download update",
                search_depth="advanced",
                max_results=5,
            )
            if isinstance(search_results, dict) and "results" in search_results:
                formatted = [f"Checking for updates: {program_name}", "=" * 50]
                for item in search_results["results"][:5]:
                    title = self._clean_text(item.get("title", "No title"))
                    url = self._clean_text(item.get("url", ""))
                    snippet = self._clean_text(item.get("content", ""))[:300]
                    formatted.append(f"Package: {title}")
                    formatted.append(f"Link: {url}")
                    formatted.append(f"Notes: {snippet}\n")
                formatted.append("=" * 50)
                formatted.append(f"To update, request: update {program_name}")
                return "\n".join(formatted)
            return "Error: Could not fetch update information. Please try again."
        except Exception as exc:
            return f"Update check error: {exc}"
