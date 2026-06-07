# MR. PERFECT OS — Tools Reference

Active registered tools: **106**

This document lists the active tool registry entries after imports are resolved.

## Notes

- Active registry count is lower than raw decorator count because later registrations with the same name override earlier ones.
- `create_code_file`, `write_file`, and `run_file` are active from `agent_tools/code_tools.py` in the final registry state.

## agent_tools.code_tools

### `auto_correct_code`
- **Arguments:** `code, language, error_message`
- **Description:** Apply common automatic corrections to code using code text plus optional error details.

### `check_code_syntax`
- **Arguments:** `code, language`
- **Description:** Verify code syntax without executing it.

### `convert_indentation`
- **Arguments:** `code, spaces`
- **Description:** Convert indentation in code to a given number of spaces.

### `count_lines_of_code`
- **Arguments:** `code, language`
- **Description:** Count total, blank, comment, and code lines.

### `create_code_file`
- **Arguments:** `filepath, content, overwrite(optional), auto_rename(optional)`
- **Description:** Saves code to a file.

### `create_css_boilerplate`
- **Arguments:** `description`
- **Description:** Create a starter CSS stylesheet.

### `create_html_boilerplate`
- **Arguments:** `title`
- **Description:** Create a starter HTML page.

### `create_json_stub`
- **Arguments:** `description`
- **Description:** Create a starter JSON structure from a short description.

### `create_markdown_doc`
- **Arguments:** `title, content`
- **Description:** Create a markdown document from a title and body text.

### `create_readme_stub`
- **Arguments:** `project_name, description, filename`
- **Description:** Create a simple README markdown file for a project.

### `create_test_stub`
- **Arguments:** `filepath, language`
- **Description:** Generate a starter unit test file for Python or JavaScript code.

### `detect_code_language`
- **Arguments:** `code`
- **Description:** Detect the likely programming language of a code snippet.

### `diff_code_versions`
- **Arguments:** `old_code, new_code`
- **Description:** Show a unified diff between old code and new code.

### `execute_code`
- **Arguments:** `code, language (python/javascript)`
- **Description:** Executes code snippets dynamically and returns output.

### `explain_code`
- **Arguments:** `code, language`
- **Description:** Explain the structure of code by listing important parts and observations.

### `extract_imports`
- **Arguments:** `code, language`
- **Description:** Extract imports or dependencies from source code.

### `format_python_code`
- **Arguments:** `code`
- **Description:** Apply simple formatting cleanup to Python code.

### `generate_code_template`
- **Arguments:** `task description, language`
- **Description:** Generate intelligent starter code for many app types including GUI and non-GUI projects.

### `generate_filename`
- **Arguments:** `task, language`
- **Description:** Generate a clean filename from a coding task and language.

### `generate_requirements_from_code`
- **Arguments:** `code`
- **Description:** Generate a simple requirements list from Python imports.

### `list_code_symbols`
- **Arguments:** `code, language`
- **Description:** List functions, classes, and key symbols in source code.

### `run_file`
- **Arguments:** `filepath`
- **Description:** Runs a saved file and returns output.

### `search_in_code`
- **Arguments:** `code, pattern`
- **Description:** Search for a text pattern inside source code.

### `strip_comments`
- **Arguments:** `code, language`
- **Description:** Remove simple single-line comments from code.

### `summarize_code_file`
- **Arguments:** `filepath`
- **Description:** Read a code file and summarize its likely purpose.

### `write_file`
- **Arguments:** `filepath, content`
- **Description:** Writes text or code to a file.

## agent_tools.file_tools

### `change_directory`
- **Arguments:** `path`
- **Description:** Change current working directory.

### `confirm_delete`
- **Arguments:** `filepath`
- **Description:** Actually perform the deletion after user confirmation.

### `copy_file`
- **Arguments:** `source, destination`
- **Description:** Copy a file or folder to destination.

### `create_folder`
- **Arguments:** `folderpath`
- **Description:** Create a new folder/directory.

### `delete_file`
- **Arguments:** `filepath`
- **Description:** Delete a file or empty folder with security restrictions.

### `get_current_directory`
- **Arguments:** `None`
- **Description:** Get current working directory.

### `get_file_hash`
- **Arguments:** `filepath, algorithm`
- **Description:** Calculate hash of a file.

### `get_file_info`
- **Arguments:** `filepath`
- **Description:** Get detailed file information.

### `list_files`
- **Arguments:** `path, pattern, include_hidden`
- **Description:** List files in a directory.

### `local_html_file`
- **Arguments:** `filepath`
- **Description:** Start a local HTTP server and open an HTML file.

### `move_file`
- **Arguments:** `source, destination`
- **Description:** Move a file or folder to destination.

### `read_file`
- **Arguments:** `filepath, max_lines, encoding`
- **Description:** Read contents of a file.

### `read_file_lines`
- **Arguments:** `filepath, start_line, count`
- **Description:** Read specific lines from a file.

### `rename_file`
- **Arguments:** `oldpath, newname`
- **Description:** Rename a file or folder.

### `search_files`
- **Arguments:** `pattern, path, max_results`
- **Description:** Search for files matching a pattern.

## agent_tools.network_tools

### `check_port`
- **Arguments:** `host, port, timeout`
- **Description:** Check if a port is open on a host.

### `dns_lookup`
- **Arguments:** `hostname`
- **Description:** Perform DNS lookup for a hostname.

### `get_clipboard`
- **Arguments:** `None`
- **Description:** Get current clipboard content.

### `get_code_snippet_info`
- **Arguments:** `language`
- **Description:** Get helpful information and common patterns for a language.

### `get_ip_info`
- **Arguments:** `None`
- **Description:** Get public IP address information.

### `get_network_info`
- **Arguments:** `None`
- **Description:** Get network connection information.

### `ping_host`
- **Arguments:** `host, count`
- **Description:** Ping a host to check connectivity.

### `ps_get_network_adapters`
- **Arguments:** `None`
- **Description:** Get Windows Network Adapter information.

### `ps_get_wifi_networks`
- **Arguments:** `None`
- **Description:** Get available WiFi networks.

### `set_clipboard`
- **Arguments:** `text`
- **Description:** Set clipboard content.

## agent_tools.os_tools

### `execute_restart`
- **Arguments:** `None`
- **Description:** Execute system restart after user confirmation.

### `execute_shutdown`
- **Arguments:** `force`
- **Description:** Execute system shutdown after user confirmation.

### `get_battery_status`
- **Arguments:** `None`
- **Description:** Get battery status (if available).

### `get_cpu_info`
- **Arguments:** `None`
- **Description:** Get detailed CPU information.

### `get_disk_usage`
- **Arguments:** `path`
- **Description:** Get disk usage statistics.

### `get_memory_info`
- **Arguments:** `None`
- **Description:** Get detailed memory information.

### `get_processes`
- **Arguments:** `limit`
- **Description:** Get running processes sorted by CPU or memory usage.

### `get_system_info`
- **Arguments:** `*args, **kwargs`
- **Description:** Get current system resource usage and hardware information.

### `get_uptime`
- **Arguments:** `None`
- **Description:** Get system uptime.

### `kill_process`
- **Arguments:** `pid`
- **Description:** Terminate a process by PID.

### `prepare_install_command`
- **Arguments:** `program_name, download_url`
- **Description:** Prepare installation command for user confirmation.

### `prepare_shutdown`
- **Arguments:** `force`
- **Description:** Prepare shutdown with user confirmation.

### `prepare_uninstall_command`
- **Arguments:** `program_name, uninstall_string`
- **Description:** Prepare uninstallation command for user confirmation.

### `prepare_update_command`
- **Arguments:** `program_name, download_url`
- **Description:** Prepare update command with user confirmation.

### `ps_get_disk_partitions`
- **Arguments:** `None`
- **Description:** Get Windows Disk Partition information.

### `ps_get_environment_vars`
- **Arguments:** `None`
- **Description:** Get Windows Environment Variables.

### `ps_get_eventlog`
- **Arguments:** `logname, count`
- **Description:** Get Windows Event Log entries.

### `ps_get_firewall_rules`
- **Arguments:** `enabled_only`
- **Description:** Get Windows Firewall Rules.

### `ps_get_hotfixes`
- **Arguments:** `None`
- **Description:** Get installed Windows Hotfixes.

### `ps_get_installed_programs`
- **Arguments:** `None`
- **Description:** Get list of installed programs (Windows).

### `ps_get_processes_detailed`
- **Arguments:** `None`
- **Description:** Get detailed process information with PowerShell.

### `ps_get_registry`
- **Arguments:** `key_path`
- **Description:** Read Windows Registry keys.

### `ps_get_running_tasks`
- **Arguments:** `None`
- **Description:** Get running tasks (similar to tasklist).

### `ps_get_scheduled_tasks`
- **Arguments:** `None`
- **Description:** Get Windows Scheduled Tasks.

### `ps_get_services`
- **Arguments:** `status`
- **Description:** Get Windows services using PowerShell.

### `ps_get_systeminfo`
- **Arguments:** `None`
- **Description:** Get comprehensive Windows System Information.

### `ps_service_action`
- **Arguments:** `service_name, action`
- **Description:** Start, stop, or restart a Windows service.

### `restart_computer`
- **Arguments:** `None`
- **Description:** Prepare to restart the computer. REQUIRES USER CONFIRMATION.

### `run_command`
- **Arguments:** `command, shell`
- **Description:** Execute a system command (cross-platform).

### `run_powershell`
- **Arguments:** `command, timeout`
- **Description:** Execute a PowerShell command and return output.

### `shutdown_computer`
- **Arguments:** `force`
- **Description:** Prepare to shutdown the computer. REQUIRES USER CONFIRMATION.

### `sleep_computer`
- **Arguments:** `None`
- **Description:** Put computer to sleep mode.

## agent_tools.system_tools

### `calculate`
- **Arguments:** `expression`
- **Description:** Safely evaluate math expressions.

### `execute_update`
- **Arguments:** `program_name, download_url`
- **Description:** Download and run an update.

### `generate_password`
- **Arguments:** `length, include_special`
- **Description:** Generate a secure random password.

### `get_agent_info`
- **Arguments:** `None`
- **Description:** Get agent status and stats.

### `get_datetime`
- **Arguments:** `format_type`
- **Description:** Get current date and time.

### `load_session`
- **Arguments:** `filepath`
- **Description:** Restores chat history from JSON.

### `save_session`
- **Arguments:** `filename`
- **Description:** Saves chat history to JSON.

### `validate_self_protection`
- **Arguments:** `path`
- **Description:** Check if path is critical.

### `validate_update_safety`
- **Arguments:** `program_name, download_url`
- **Description:** Validate update source safety.

## agent_tools.web_tools

### `browser_browse`
- **Arguments:** `url_or_query`
- **Description:** Navigate and read website content via Playwright.

### `get_weather`
- **Arguments:** `location`
- **Description:** Get weather for a location.

### `open_web`
- **Arguments:** `url`
- **Description:** Open a specific URL in the browser.

### `search_program`
- **Arguments:** `program_name`
- **Description:** Search for official program download links.

### `web_search`
- **Arguments:** `query`
- **Description:** Search the web for up-to-date information.

## agent_tools.winget_tools

### `check_program_removable`
- **Arguments:** `program_display_name`
- **Description:** Check if a program can be safely uninstalled.

### `check_program_updates`
- **Arguments:** `program_name`
- **Description:** Check for program updates online (REQUIRES USER REQUEST).

### `execute_install`
- **Arguments:** `program_name, download_url`
- **Description:** Execute program installation after user confirmation.

### `execute_uninstall`
- **Arguments:** `program_name, uninstall_string`
- **Description:** Execute program uninstallation after user confirmation.

### `get_installed_programs_list`
- **Arguments:** `*args, **kwargs`
- **Description:** Get list of installed programs for uninstallation selection.

### `validate_program_safety`
- **Arguments:** `program_name, url`
- **Description:** Validate if a program is safe to install (basic checks).

### `winget_install`
- **Arguments:** `package_id`
- **Description:** Installs a program with a 10-minute timeout and aggressive log cleaning.

### `winget_uninstall`
- **Arguments:** `package_id`
- **Description:** Uninstalls a program cleanly.

### `winget_upgrade`
- **Arguments:** `package_id, *args, **kwargs`
- **Description:** Upgrades an existing installed software application to its latest version.
