from tool_registry import tool_registry

import json
import os
import re
import socket
import subprocess
import urllib.request

import psutil


class NetworkToolsMixin:
    def _clean_text(self, value):
        if value is None:
            return ""

        text = str(value)
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
        text = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", text)
        text = text.replace("```", "")
        return text.strip()

    def _run_command(self, command, timeout=30):
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="ignore",
        )
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if stdout and stderr:
            return f"{stdout}\n\nSTDERR:\n{stderr}"
        return stdout or stderr or "Command executed successfully (no output)."

    @tool_registry.register(
        name="ping_host",
        description="Ping a host to check connectivity.",
        args_description="host, count",
    )
    def ping_host(self, host: str, count: int = 4) -> str:
        try:
            target = self._clean_text(host)
            if not target:
                return "Error: No host provided."

            count = max(1, min(10, int(count)))
            param = "-n" if os.name == "nt" else "-c"
            return self._run_command(["ping", param, str(count), target], timeout=30)
        except subprocess.TimeoutExpired:
            return "Error: Ping timed out"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_network_info",
        description="Get network connection information.",
        args_description="",
    )
    def get_network_info(self) -> str:
        try:
            info = []
            interfaces = psutil.net_if_addrs()
            for iface, addrs in interfaces.items():
                info.append(f"{iface}:")
                for addr in addrs:
                    family = getattr(addr.family, "name", str(addr.family))
                    info.append(f"  {family}: {addr.address}")
            return "\n".join(info) if info else "No network interfaces found."
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_clipboard",
        description="Get current clipboard content.",
        args_description="",
    )
    def get_clipboard(self) -> str:
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            content = root.clipboard_get()
            root.destroy()
            return content[:1000] if len(content) > 1000 else content
        except Exception:
            return "Clipboard is empty or contains non-text data"

    @tool_registry.register(
        name="set_clipboard",
        description="Set clipboard content.",
        args_description="text",
    )
    def set_clipboard(self, text: str) -> str:
        try:
            import tkinter as tk

            value = self._clean_text(text)
            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(value)
            root.update()
            root.destroy()
            return f"Copied {len(value)} characters to clipboard"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_ip_info",
        description="Get public IP address information.",
        args_description="",
    )
    def get_ip_info(self) -> str:
        try:
            request = urllib.request.Request(
                "https://ipapi.co/json/",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8", errors="ignore"))

            return (
                f"Public IP: {data.get('ip', 'Unknown')}\n"
                f"City: {data.get('city', 'Unknown')}\n"
                f"Region: {data.get('region', 'Unknown')}\n"
                f"Country: {data.get('country_name', 'Unknown')}\n"
                f"ISP: {data.get('org', 'Unknown')}\n"
                f"ASN: {data.get('asn', 'Unknown')}"
            )
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="check_port",
        description="Check if a port is open on a host.",
        args_description="host, port, timeout",
    )
    def check_port(self, host: str, port: int, timeout: int = 3) -> str:
        try:
            target = self._clean_text(host)
            port = int(port)
            timeout = max(1, int(timeout))

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((target, port))
            sock.close()

            if result == 0:
                return f"Port {port} on {target} is OPEN"
            return f"Port {port} on {target} is CLOSED"
        except socket.gaierror:
            return f"Error: Could not resolve host {host}"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="dns_lookup",
        description="Perform DNS lookup for a hostname.",
        args_description="hostname",
    )
    def dns_lookup(self, hostname: str) -> str:
        try:
            target = self._clean_text(hostname)
            if not target:
                return "Error: No hostname provided."
            return socket.gethostbyname(target)
        except socket.gaierror:
            return f"Error: Could not resolve {hostname}"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_network_adapters",
        description="Get Windows Network Adapter information.",
        args_description="",
    )
    def ps_get_network_adapters(self) -> str:
        if os.name != "nt":
            return "Error: This tool is available only on Windows."
        try:
            cmd = (
                "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | "
                "Select-Object Name, InterfaceDescription, Status, LinkSpeed, MacAddress | "
                "Format-Table -AutoSize | Out-String"
            )
            return self._run_command(["powershell", "-Command", cmd], timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_wifi_networks",
        description="Get available WiFi networks.",
        args_description="",
    )
    def ps_get_wifi_networks(self) -> str:
        if os.name != "nt":
            return "Error: This tool is available only on Windows."
        try:
            return self._run_command(["netsh", "wlan", "show", "networks", "mode=bssid"], timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_code_snippet_info",
        description="Get helpful information and common patterns for a language.",
        args_description="language",
    )
    def get_code_snippet_info(self, language: str) -> str:
        language_info = {
            "python": (
                "Python Information:\n\n"
                "- Extensions: .py\n"
                "- Comments: # single line, triple quotes for docstrings\n"
                "- Variables: x = 10\n"
                "- Lists: [1, 2, 3]\n"
                "- Dicts: {'key': 'value'}\n"
                "- Functions: def func(args):\n"
                "- Classes: class MyClass:\n"
                "- Imports: import module_name"
            ),
            "javascript": (
                "JavaScript Information:\n\n"
                "- Extensions: .js, .mjs\n"
                "- Comments: // single line, /* multi-line */\n"
                "- Variables: let x = 10, const y = 20\n"
                "- Arrays: [1, 2, 3]\n"
                "- Objects: { key: 'value' }\n"
                "- Functions: function name() {}\n"
                "- Classes: class Name { constructor() {} }"
            ),
            "html": (
                "HTML Information:\n\n"
                "- Extensions: .html, .htm\n"
                "- Basic structure: html, head, body\n"
                "- Common elements: div, span, p, a, img, ul, li, table\n"
                "- Forms: form, input, button, select"
            ),
            "css": (
                "CSS Information:\n\n"
                "- Extension: .css\n"
                "- Selectors: element, .class, #id\n"
                "- Common properties: color, margin, padding, display\n"
                "- Layout: flexbox and grid\n"
                "- Responsive design: media queries"
            ),
            "sql": (
                "SQL Information:\n\n"
                "- Extension: .sql\n"
                "- SELECT, INSERT, UPDATE, DELETE\n"
                "- CREATE TABLE for schema creation\n"
                "- WHERE, ORDER BY, GROUP BY for filtering and grouping"
            ),
        }

        lang_key = self._clean_text(language).lower()
        if lang_key in language_info:
            return language_info[lang_key]

        supported = "\n".join(f"- {name}" for name in sorted(language_info.keys()))
        return f"Language not recognized: {language}\n\nSupported languages:\n{supported}"
