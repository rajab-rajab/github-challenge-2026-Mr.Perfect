from tool_registry import tool_registry

import datetime
import os
import platform
import shlex
import socket
import subprocess

import psutil


class OsToolsMixin:
    def _clean_text(self, value):
        if value is None:
            return ""
        text = str(value)
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        return text.strip()

    def _run_process(self, command, timeout=30, shell=False):
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=shell,
            timeout=timeout,
            encoding="utf-8",
            errors="ignore",
        )
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if stdout and stderr:
            return f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        return stdout or stderr or "Command executed successfully (no output)"

    def _run_powershell_command(self, command: str, timeout: int = 30) -> str:
        if os.name != "nt":
            return "Error: PowerShell tools are available only on Windows."
        return self._run_process(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            timeout=timeout,
        )

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

    @tool_registry.register(
        name="run_powershell",
        description="Execute a PowerShell command and return output.",
        args_description="command, timeout",
    )
    def run_powershell(self, command: str, timeout: int = 30) -> str:
        try:
            return self._run_powershell_command(self._clean_text(command), timeout=int(timeout))
        except subprocess.TimeoutExpired:
            return "Error: Command timed out"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="run_command",
        description="Execute a system command (cross-platform).",
        args_description="command, shell",
    )
    def run_command(self, command: str, shell: bool = False) -> str:
        try:
            clean_command = self._clean_text(command)
            cmd = clean_command if shell else shlex.split(clean_command, posix=os.name != "nt")
            return self._run_process(cmd, timeout=30, shell=bool(shell))
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_system_info",
        description="Get current system resource usage and hardware information.",
        args_description="*args, **kwargs",
    )
    def get_system_info(self, *args, **kwargs) -> str:
        try:
            hostname = socket.gethostname()
            os_data = f"{platform.system()} {platform.release()} ({platform.architecture()[0]})"
            processor = platform.processor() or "Unknown"
            cpu = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count(logical=True)
            ram = psutil.virtual_memory()
            swap = psutil.swap_memory()

            info = [
                "--- SYSTEM INFORMATION ---",
                f"PC Name      : {hostname}",
                f"OS Version   : {os_data}",
                f"Processor    : {processor}",
                "",
                "--- CURRENT PERFORMANCE ---",
                f"CPU Usage    : {cpu}% ({cpu_count} Threads)",
                f"RAM Usage    : {ram.percent}% ({ram.used // (2 ** 30)}GB / {ram.total // (2 ** 30)}GB)",
                f"Swap Usage   : {swap.percent}% ({swap.used // (2 ** 30)}GB / {swap.total // (2 ** 30)}GB)",
            ]
            return "\n".join(info)
        except Exception as exc:
            return f"Error gathering system info: {exc}"

    @tool_registry.register(
        name="get_disk_usage",
        description="Get disk usage statistics.",
        args_description="path",
    )
    def get_disk_usage(self, path: str = "/") -> str:
        try:
            target = self._clean_text(path) or "/"
            usage = psutil.disk_usage(target)
            return (
                f"Path: {target}\n"
                f"Total: {usage.total // (2 ** 30):,} GB\n"
                f"Used: {usage.used // (2 ** 30):,} GB ({usage.percent}%)\n"
                f"Free: {usage.free // (2 ** 30):,} GB"
            )
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_processes",
        description="Get running processes sorted by CPU or memory usage.",
        args_description="limit",
    )
    def get_processes(self, limit: int = 10) -> str:
        try:
            limit = max(1, min(100, int(limit)))
            processes = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            processes.sort(key=lambda item: item.get("memory_percent") or 0, reverse=True)
            output = [f"Top {min(limit, len(processes))} Processes by Memory:", "-" * 60]
            for proc in processes[:limit]:
                output.append(
                    f"PID: {proc['pid']:>6} | {str(proc.get('name') or '')[:30]:<30} | "
                    f"CPU: {(proc.get('cpu_percent') or 0):>5.1f}% | RAM: {(proc.get('memory_percent') or 0):>5.1f}%"
                )
            return "\n".join(output)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="kill_process",
        description="Terminate a process by PID.",
        args_description="pid",
    )
    def kill_process(self, pid: int) -> str:
        try:
            pid = int(pid)
            process = psutil.Process(pid)
            name = process.name()
            process.terminate()
            process.wait(timeout=5)
            return f"Terminated process: {name} (PID: {pid})"
        except psutil.NoSuchProcess:
            return f"Error: Process with PID {pid} not found"
        except psutil.TimeoutExpired:
            return f"Error: Process {pid} did not exit after terminate request"
        except psutil.AccessDenied:
            return f"Error: Access denied to process {pid}"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_uptime",
        description="Get system uptime.",
        args_description="",
    )
    def get_uptime(self) -> str:
        try:
            boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.datetime.now() - boot_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"System Uptime: {days}d {hours}h {minutes}m {seconds}s"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_battery_status",
        description="Get battery status (if available).",
        args_description="",
    )
    def get_battery_status(self) -> str:
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return "No battery detected"
            status = "Charging" if battery.power_plugged else "On Battery"
            marker = "[CHARGING]" if battery.power_plugged else "[DISCHARGING]"
            return f"Battery: {battery.percent}% {marker}\nStatus: {status}"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_cpu_info",
        description="Get detailed CPU information.",
        args_description="",
    )
    def get_cpu_info(self) -> str:
        try:
            cpu_freq = psutil.cpu_freq()
            current = cpu_freq.current if cpu_freq else 0
            minimum = cpu_freq.min if cpu_freq else 0
            maximum = cpu_freq.max if cpu_freq else 0
            return (
                f"Physical Cores: {psutil.cpu_count(logical=False)}\n"
                f"Logical Cores: {psutil.cpu_count(logical=True)}\n"
                f"Current Frequency: {current:.0f} MHz\n"
                f"Min Frequency: {minimum:.0f} MHz\n"
                f"Max Frequency: {maximum:.0f} MHz"
            )
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="get_memory_info",
        description="Get detailed memory information.",
        args_description="",
    )
    def get_memory_info(self) -> str:
        try:
            vm = psutil.virtual_memory()
            sm = psutil.swap_memory()
            return (
                "Virtual Memory:\n"
                f"  Total: {vm.total // (2 ** 30):,} GB\n"
                f"  Available: {vm.available // (2 ** 30):,} GB\n"
                f"  Used: {vm.used // (2 ** 30):,} GB ({vm.percent}%)\n"
                "Swap Memory:\n"
                f"  Total: {sm.total // (2 ** 30):,} GB\n"
                f"  Used: {sm.used // (2 ** 30):,} GB ({sm.percent}%)\n"
                f"  Free: {sm.free // (2 ** 30):,} GB"
            )
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_services",
        description="Get Windows services using PowerShell.",
        args_description="status",
    )
    def ps_get_services(self, status: str = "all") -> str:
        filters = {
            "all": "Get-Service",
            "running": "Get-Service | Where-Object {$_.Status -eq 'Running'}",
            "stopped": "Get-Service | Where-Object {$_.Status -eq 'Stopped'}",
        }
        command = (
            f"{filters.get(self._clean_text(status).lower(), 'Get-Service')} | "
            "Select-Object Name, DisplayName, Status | Format-Table -AutoSize | Out-String"
        )
        try:
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_service_action",
        description="Start, stop, or restart a Windows service.",
        args_description="service_name, action",
    )
    def ps_service_action(self, service_name: str, action: str) -> str:
        actions = {
            "start": "Start-Service",
            "stop": "Stop-Service",
            "restart": "Restart-Service",
        }
        try:
            action_key = self._clean_text(action).lower()
            if action_key not in actions:
                return "Error: Invalid action. Use: start, stop, restart"
            svc = self._clean_text(service_name).replace("'", "''")
            command = f"{actions[action_key]} -Name '{svc}'; Write-Output 'Service {action_key} completed successfully'"
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_eventlog",
        description="Get Windows Event Log entries.",
        args_description="logname, count",
    )
    def ps_get_eventlog(self, logname: str = "System", count: int = 10) -> str:
        try:
            name = self._clean_text(logname) or "System"
            count = max(1, min(100, int(count)))
            command = (
                f"Get-EventLog -LogName '{name}' -Newest {count} | "
                "Select-Object TimeGenerated, EntryType, Source, Message | "
                "Format-Table -AutoSize -Wrap | Out-String"
            )
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_processes_detailed",
        description="Get detailed process information with PowerShell.",
        args_description="",
    )
    def ps_get_processes_detailed(self) -> str:
        command = (
            "Get-Process | Sort-Object CPU -Descending | "
            "Select-Object Name, Id, CPU, WorkingSet, Path | "
            "Format-Table -AutoSize | Out-String"
        )
        try:
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_registry",
        description="Read Windows Registry keys.",
        args_description="key_path",
    )
    def ps_get_registry(self, key_path: str) -> str:
        try:
            key = self._clean_text(key_path).replace("'", "''")
            command = (
                f"Get-Item -Path '{key}' -ErrorAction SilentlyContinue | Select-Object Name, Property; "
                f"Get-ItemProperty -Path '{key}' -ErrorAction SilentlyContinue | Format-List | Out-String"
            )
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_scheduled_tasks",
        description="Get Windows Scheduled Tasks.",
        args_description="",
    )
    def ps_get_scheduled_tasks(self) -> str:
        command = (
            "Get-ScheduledTask | Select-Object TaskName, State, TaskPath | "
            "Format-Table -AutoSize | Out-String"
        )
        try:
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_installed_programs",
        description="Get list of installed programs (Windows).",
        args_description="",
    )
    def ps_get_installed_programs(self) -> str:
        command = """
$programs = @()
$paths = @(
    'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'
)
foreach ($path in $paths) {
    Get-ItemProperty -Path $path -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName } |
    Select-Object DisplayName, DisplayVersion, Publisher, InstallDate, UninstallString |
    ForEach-Object { $programs += $_ }
}
$programs | Sort-Object DisplayName -Unique | Format-Table -AutoSize | Out-String
"""
        try:
            return self._run_powershell_command(command, timeout=60)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_environment_vars",
        description="Get Windows Environment Variables.",
        args_description="",
    )
    def ps_get_environment_vars(self) -> str:
        command = "Get-ChildItem Env: | Sort-Object Name | Format-Table Name, Value -AutoSize | Out-String"
        try:
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_firewall_rules",
        description="Get Windows Firewall Rules.",
        args_description="enabled_only",
    )
    def ps_get_firewall_rules(self, enabled_only: bool = True) -> str:
        try:
            filter_ps = "| Where-Object { $_.Enabled -eq 'True' }" if enabled_only else ""
            command = (
                f"Get-NetFirewallRule {filter_ps} | "
                "Select-Object Name, DisplayName, Direction, Action, Enabled | "
                "Sort-Object DisplayName | Format-Table -AutoSize | Out-String"
            )
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_disk_partitions",
        description="Get Windows Disk Partition information.",
        args_description="",
    )
    def ps_get_disk_partitions(self) -> str:
        command = """
Get-Disk | Select-Object Number, FriendlyName, Size, PartitionStyle, OperationalStatus |
Format-Table -AutoSize | Out-String
Write-Output "`n=== PARTITIONS ==="
Get-Partition | Select-Object DiskNumber, PartitionNumber, DriveLetter, Size, Type |
Format-Table -AutoSize | Out-String
"""
        try:
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_hotfixes",
        description="Get installed Windows Hotfixes.",
        args_description="",
    )
    def ps_get_hotfixes(self) -> str:
        command = (
            "Get-HotFix | Sort-Object InstalledOn -Descending | "
            "Select-Object HotFixID, Description, InstalledOn, InstalledBy | "
            "Format-Table -AutoSize | Out-String"
        )
        try:
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_running_tasks",
        description="Get running tasks (similar to tasklist).",
        args_description="",
    )
    def ps_get_running_tasks(self) -> str:
        command = (
            "Get-Process | Select-Object Name, Id, CPU, WorkingSet64, "
            "@{N='RAM(MB)';E={[math]::Round($_.WorkingSet64/1MB,2)}}, Path | "
            "Sort-Object CPU -Descending | Format-Table -AutoSize | Out-String"
        )
        try:
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="ps_get_systeminfo",
        description="Get comprehensive Windows System Information.",
        args_description="",
    )
    def ps_get_systeminfo(self) -> str:
        command = """
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor
Write-Output "=== SYSTEM INFO ==="
Write-Output "Computer Name: $($cs.Name)"
Write-Output "Domain: $($cs.Domain)"
Write-Output ""
Write-Output "=== OPERATING SYSTEM ==="
Write-Output "OS: $($os.Caption) $($os.Version)"
Write-Output "Architecture: $($os.OSArchitecture)"
Write-Output "Build: $($os.BuildNumber)"
Write-Output ""
Write-Output "=== HARDWARE ==="
Write-Output "CPU: $($cpu.Name)"
Write-Output "Cores: $($cpu.NumberOfCores)"
Write-Output "Logical Processors: $($cpu.NumberOfLogicalProcessors)"
Write-Output "RAM: $([math]::Round($cs.TotalPhysicalMemory/1GB,2)) GB"
"""
        try:
            return self._run_powershell_command(command, timeout=30)
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="prepare_install_command",
        description="Prepare installation command for user confirmation.",
        args_description="program_name, download_url",
    )
    def prepare_install_command(self, program_name: str, download_url: str) -> str:
        try:
            if hasattr(self, "validate_program_safety"):
                safety = self.validate_program_safety(program_name, download_url)
            else:
                safety = "VERIFY_NEEDED"

            if str(safety).startswith("UNSAFE"):
                return f"ERROR: {safety}"
            if str(safety).startswith("WARNING"):
                return f"CONFIRM_INSTALL:{program_name}|URL:{download_url}|WARNING:{safety}"
            return f"CONFIRM_INSTALL:{program_name}|URL:{download_url}|STATUS:{safety}"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="prepare_uninstall_command",
        description="Prepare uninstallation command for user confirmation.",
        args_description="program_name, uninstall_string",
    )
    def prepare_uninstall_command(self, program_name: str, uninstall_string: str = "") -> str:
        try:
            if hasattr(self, "check_program_removable"):
                safety_check = self.check_program_removable(program_name)
                if "UNSAFE" in safety_check:
                    return f"ERROR: {safety_check}"

            uninstall_value = self._clean_text(uninstall_string)
            if not uninstall_value:
                command = f"""
$paths = @(
    'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'
)
foreach ($path in $paths) {{
    $prog = Get-ItemProperty -Path $path -ErrorAction SilentlyContinue |
        Where-Object {{ $_.DisplayName -eq '{self._clean_text(program_name).replace("'", "''")}' }}
    if ($prog -and $prog.UninstallString) {{
        Write-Output $prog.UninstallString
        break
    }}
}}
"""
                uninstall_value = self._run_powershell_command(command, timeout=30).strip()

            if not uninstall_value or uninstall_value.startswith("Error"):
                return f"ERROR: Could not find uninstall information for '{program_name}'"
            return f"CONFIRM_UNINSTALL:{program_name}|CMD:{uninstall_value}"
        except Exception as exc:
            return f"Error getting uninstall string: {exc}"

    @tool_registry.register(
        name="prepare_update_command",
        description="Prepare update command with user confirmation.",
        args_description="program_name, download_url",
    )
    def prepare_update_command(self, program_name: str, download_url: str) -> str:
        try:
            name_lower = self._clean_text(program_name).lower()
            for protected in self._protected_programs():
                if protected in name_lower:
                    return f"ERROR: '{program_name}' is a system program and should not be updated."

            if hasattr(self, "validate_update_safety"):
                safety = self.validate_update_safety(program_name, download_url)
            elif hasattr(self, "validate_program_safety"):
                safety = self.validate_program_safety(program_name, download_url)
            else:
                safety = "VERIFY_NEEDED"

            if str(safety).startswith("UNSAFE"):
                return f"ERROR: {safety}"
            return f"CONFIRM_UPDATE:{program_name}|URL:{download_url}|STATUS:{safety}"
        except Exception as exc:
            return f"Error: {exc}"

    @tool_registry.register(
        name="shutdown_computer",
        description="Prepare to shutdown the computer. REQUIRES USER CONFIRMATION.",
        args_description="force",
    )
    def shutdown_computer(self, force: bool = False) -> str:
        return f"CONFIRM_SHUTDOWN:{'FORCE' if force else 'NORMAL'}|Close all programs and shutdown this computer?"

    @tool_registry.register(
        name="prepare_shutdown",
        description="Prepare shutdown with user confirmation.",
        args_description="force",
    )
    def prepare_shutdown(self, force: bool = False) -> str:
        return f"CONFIRM_SHUTDOWN:{'FORCE' if force else 'NORMAL'}"

    @tool_registry.register(
        name="execute_shutdown",
        description="Execute system shutdown after user confirmation.",
        args_description="force",
    )
    def execute_shutdown(self, force: bool = False) -> str:
        try:
            if os.name == "nt":
                os.system("shutdown /s /f /t 0" if force else "shutdown /s /t 0")
            else:
                os.system("sudo shutdown -h now")
            return "Computer will shutdown in a moment. Goodbye!"
        except Exception as exc:
            return f"Shutdown error: {exc}"

    @tool_registry.register(
        name="restart_computer",
        description="Prepare to restart the computer. REQUIRES USER CONFIRMATION.",
        args_description="",
    )
    def restart_computer(self) -> str:
        return "CONFIRM_RESTART"

    @tool_registry.register(
        name="execute_restart",
        description="Execute system restart after user confirmation.",
        args_description="",
    )
    def execute_restart(self) -> str:
        try:
            if os.name == "nt":
                os.system("shutdown /r /t 0")
            else:
                os.system("sudo shutdown -r now")
            return "Computer will restart in a moment. See you soon!"
        except Exception as exc:
            return f"Restart error: {exc}"

    @tool_registry.register(
        name="sleep_computer",
        description="Put computer to sleep mode.",
        args_description="",
    )
    def sleep_computer(self) -> str:
        try:
            if os.name == "nt":
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            else:
                os.system("systemctl suspend")
            return "Computer will enter sleep mode."
        except Exception as exc:
            return f"Sleep error: {exc}"
