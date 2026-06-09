import os
import shutil
import subprocess
import platform
import psutil
from pathlib import Path
import time
import zipfile
import tarfile

_SYSTEM = platform.system()

def batch_file_operations(action: str, source_paths: list, destination: str = None, **kwargs) -> str:
    """
    Perform batch operations on multiple files.
    Actions: copy, move, delete, compress, extract
    """
    action = action.lower().strip()
    results = []

    if not source_paths:
        return "No source paths provided"

    for src in source_paths:
        src_path = Path(src).expanduser().resolve()
        if not src_path.exists():
            results.append(f"Source not found: {src}")
            continue

        try:
            if action == "copy":
                if not destination:
                    results.append("Destination required for copy")
                    continue
                dest_path = Path(destination).expanduser().resolve()
                if src_path.is_file():
                    shutil.copy2(src_path, dest_path)
                    results.append(f"Copied: {src_path.name}")
                else:
                    shutil.copytree(src_path, dest_path / src_path.name, dirs_exist_ok=True)
                    results.append(f"Copied directory: {src_path.name}")

            elif action == "move":
                if not destination:
                    results.append("Destination required for move")
                    continue
                dest_path = Path(destination).expanduser().resolve()
                shutil.move(str(src_path), str(dest_path))
                results.append(f"Moved: {src_path.name}")

            elif action == "delete":
                if src_path.is_file():
                    src_path.unlink()
                    results.append(f"Deleted file: {src_path.name}")
                else:
                    shutil.rmtree(src_path)
                    results.append(f"Deleted directory: {src_path.name}")

            elif action == "compress":
                archive_name = kwargs.get('archive_name', f"{src_path.name}.zip")
                archive_path = Path(destination or src_path.parent) / archive_name

                if src_path.is_file():
                    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        zf.write(src_path, src_path.name)
                else:
                    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for file_path in src_path.rglob('*'):
                            if file_path.is_file():
                                zf.write(file_path, file_path.relative_to(src_path.parent))
                results.append(f"Compressed to: {archive_name}")

        except Exception as e:
            results.append(f"Failed {action} {src_path.name}: {e}")

    return "\n".join(results) if results else f"No {action} operations performed"

def system_monitoring(action: str) -> str:
    """
    Monitor system resources and performance.
    Actions: cpu, memory, disk, network, processes
    """
    action = action.lower().strip()

    try:
        if action == "cpu":
            usage = psutil.cpu_percent(interval=0.2)
            return f"CPU Usage: {usage}%"

        elif action == "memory":
            mem = psutil.virtual_memory()
            return f"Memory: {mem.percent}% used ({mem.used//1024//1024}MB / {mem.total//1024//1024}MB)"

        elif action == "disk":
            disks = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disks.append(f"{partition.mountpoint}: {usage.percent}% ({usage.used//1024//1024//1024}GB / {usage.total//1024//1024//1024}GB)")
                except:
                    continue
            return "\n".join(disks)

        elif action == "network":
            net = psutil.net_io_counters()
            return f"Network: Sent {net.bytes_sent//1024//1024}MB, Received {net.bytes_recv//1024//1024}MB"

        elif action == "processes":
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    if proc.info['cpu_percent'] > 1.0 or proc.info['memory_percent'] > 1.0:
                        processes.append(f"{proc.info['pid']}: {proc.info['name']} (CPU: {proc.info['cpu_percent']}%, MEM: {proc.info['memory_percent']}%)")
                except:
                    continue
            return "\n".join(processes[:10]) if processes else "No high-usage processes found"

        elif action == "all":
            cpu = psutil.cpu_percent(interval=0.2)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            return f"CPU: {cpu}%, Memory: {mem.percent}%, Disk: {disk.percent}%"

    except Exception as e:
        return f"Monitoring failed: {e}"

    return f"Unknown monitoring action: {action}"

def package_management(action: str, package_name: str = None) -> str:
    """
    Manage software packages (basic operations).
    Actions: list, install, remove, update
    Note: Limited cross-platform support
    """
    action = action.lower().strip()

    if _SYSTEM == "Windows":
        # Windows doesn't have a built-in package manager like apt/choco
        return "Package management not supported on Windows (consider Chocolatey)"

    elif _SYSTEM == "Linux":
        try:
            if action == "list":
                if package_name:
                    result = subprocess.run(["apt", "list", "--installed", package_name],
                                          capture_output=True, text=True, timeout=30)
                    return result.stdout or f"Package {package_name} not found"
                else:
                    result = subprocess.run(["apt", "list", "--installed"],
                                          capture_output=True, text=True, timeout=30)
                    lines = result.stdout.strip().split('\n')[:20]
                    return "\n".join(lines)

            elif action == "install" and package_name:
                result = subprocess.run(["sudo", "apt", "install", "-y", package_name],
                                      capture_output=True, text=True, timeout=300)
                return result.stdout or result.stderr

            elif action == "remove" and package_name:
                result = subprocess.run(["sudo", "apt", "remove", "-y", package_name],
                                      capture_output=True, text=True, timeout=300)
                return result.stdout or result.stderr

            elif action == "update":
                result = subprocess.run(["sudo", "apt", "update"],
                                      capture_output=True, text=True, timeout=300)
                return result.stdout or result.stderr

        except subprocess.TimeoutExpired:
            return f"{action} timed out"
        except Exception as e:
            return f"Package operation failed: {e}"

    elif _SYSTEM == "Darwin":  # macOS
        try:
            if action == "list":
                if package_name:
                    result = subprocess.run(["brew", "list", package_name],
                                          capture_output=True, text=True, timeout=30)
                    return result.stdout or f"Package {package_name} not found"
                else:
                    result = subprocess.run(["brew", "list"],
                                          capture_output=True, text=True, timeout=30)
                    lines = result.stdout.strip().split('\n')[:20]
                    return "\n".join(lines)

            elif action == "install" and package_name:
                result = subprocess.run(["brew", "install", package_name],
                                      capture_output=True, text=True, timeout=300)
                return result.stdout or result.stderr

            elif action == "remove" and package_name:
                result = subprocess.run(["brew", "uninstall", package_name],
                                      capture_output=True, text=True, timeout=300)
                return result.stdout or result.stderr

            elif action == "update":
                result = subprocess.run(["brew", "update"],
                                      capture_output=True, text=True, timeout=300)
                return result.stdout or result.stderr

        except subprocess.TimeoutExpired:
            return f"{action} timed out"
        except Exception as e:
            return f"Package operation failed: {e}"

    return f"Package management not supported on {_SYSTEM}"

def scheduled_tasks(action: str, task_name: str = None, command: str = None, schedule: str = None) -> str:
    """
    Basic scheduled task management.
    Actions: list, create, delete
    Note: Very basic implementation - real scheduling would need more infrastructure
    """
    action = action.lower().strip()

    if _SYSTEM == "Windows":
        try:
            if action == "list":
                result = subprocess.run(["schtasks", "/query", "/fo", "LIST"],
                                      capture_output=True, text=True, timeout=30)
                return result.stdout[:2000] or "No scheduled tasks found"

            elif action == "create" and task_name and command:
                # Very basic daily task creation
                result = subprocess.run([
                    "schtasks", "/create", "/tn", task_name, "/tr", command,
                    "/sc", "daily", "/st", "09:00"
                ], capture_output=True, text=True, timeout=30)
                return result.stdout or result.stderr

            elif action == "delete" and task_name:
                result = subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"],
                                      capture_output=True, text=True, timeout=30)
                return result.stdout or result.stderr

        except Exception as e:
            return f"Task scheduling failed: {e}"

    elif _SYSTEM in ["Linux", "Darwin"]:
        # Basic cron job management (very simplified)
        cron_file = Path.home() / ".crontab_jarvis"

        try:
            if action == "list":
                if cron_file.exists():
                    return cron_file.read_text()
                return "No Jarvis scheduled tasks"

            elif action == "create" and task_name and command and schedule:
                # Add to custom cron file (would need to be loaded with crontab)
                entry = f"# {task_name}\n{schedule} {command}\n"
                with open(cron_file, 'a') as f:
                    f.write(entry)
                return f"Added task '{task_name}' to cron file (run 'crontab ~/.crontab_jarvis' to activate)"

            elif action == "delete" and task_name:
                if cron_file.exists():
                    lines = cron_file.read_text().split('\n')
                    filtered = []
                    skip = False
                    for line in lines:
                        if line.startswith(f"# {task_name}"):
                            skip = True
                        elif skip and line.strip():
                            continue
                        elif skip and not line.strip():
                            skip = False
                            continue
                        else:
                            filtered.append(line)
                    cron_file.write_text('\n'.join(filtered))
                    return f"Removed task '{task_name}'"
                return "No tasks to remove"

        except Exception as e:
            return f"Task scheduling failed: {e}"

    return f"Task scheduling not fully supported on {_SYSTEM}"

# ===== WORKFLOW AND CONDITIONAL AUTOMATION =====

import json
import threading
import schedule
import time as time_module
from datetime import datetime, timedelta
from typing import Dict, List, Any, Callable
import re

# Global workflow storage
_WORKFLOWS = {}
_WORKFLOW_SCHEDULER = None
_SCHEDULER_THREAD = None

def _get_workflow_file() -> Path:
    """Get the path to the workflows storage file"""
    base_dir = Path(__file__).resolve().parent.parent
    return base_dir / "config" / "workflows.json"

def _load_workflows():
    """Load workflows from storage file"""
    global _WORKFLOWS
    workflow_file = _get_workflow_file()
    if workflow_file.exists():
        try:
            _WORKFLOWS = json.loads(workflow_file.read_text(encoding="utf-8"))
        except:
            _WORKFLOWS = {}
    else:
        _WORKFLOWS = {}

def _save_workflows():
    """Save workflows to storage file"""
    workflow_file = _get_workflow_file()
    workflow_file.parent.mkdir(exist_ok=True)
    workflow_file.write_text(json.dumps(_WORKFLOWS, indent=2), encoding="utf-8")

def _start_scheduler():
    """Start the background scheduler for workflows"""
    global _WORKFLOW_SCHEDULER, _SCHEDULER_THREAD

    if _WORKFLOW_SCHEDULER is None:
        _WORKFLOW_SCHEDULER = schedule.Scheduler()

        def scheduler_loop():
            while True:
                _WORKFLOW_SCHEDULER.run_pending()
                time_module.sleep(60)  # Check every minute

        _SCHEDULER_THREAD = threading.Thread(target=scheduler_loop, daemon=True)
        _SCHEDULER_THREAD.start()

def _parse_condition(condition: str) -> Dict[str, Any]:
    """Parse a conditional statement into components"""
    # Simple condition parser for basic logic
    # Examples: "weather tomorrow == rainy", "time > 18:00", "cpu > 80"

    condition = condition.lower().strip()

    # Weather conditions
    weather_match = re.match(r'weather\s+(\w+)\s*==\s*(\w+)', condition)
    if weather_match:
        return {
            'type': 'weather',
            'when': weather_match.group(1),
            'condition': weather_match.group(2)
        }

    # Time conditions
    time_match = re.match(r'time\s*([><=]+)\s*(\d{1,2}:\d{2})', condition)
    if time_match:
        return {
            'type': 'time',
            'operator': time_match.group(1),
            'time': time_match.group(2)
        }

    # System conditions
    system_match = re.match(r'(cpu|memory|disk)\s*([><=]+)\s*(\d+)', condition)
    if system_match:
        return {
            'type': 'system',
            'metric': system_match.group(1),
            'operator': system_match.group(2),
            'value': int(system_match.group(3))
        }

    return {'type': 'unknown', 'condition': condition}

def _evaluate_condition(condition_data: Dict[str, Any]) -> bool:
    """Evaluate a parsed condition"""
    try:
        cond_type = condition_data.get('type')

        if cond_type == 'weather':
            # Import weather function dynamically to avoid circular imports
            from actions.weather_report import weather_action
            when = condition_data.get('when', 'today')
            expected = condition_data.get('condition', '')

            # Get weather data
            weather_result = weather_action("New York")  # Default city, could be made configurable
            weather_lower = weather_result.lower()

            # Simple weather condition checking
            if expected in ['rain', 'rainy'] and ('rain' in weather_lower or 'shower' in weather_lower):
                return True
            elif expected in ['sun', 'sunny'] and ('sun' in weather_lower or 'clear' in weather_lower):
                return True
            elif expected in ['cloud', 'cloudy'] and 'cloud' in weather_lower:
                return True

        elif cond_type == 'time':
            operator = condition_data.get('operator', '>')
            target_time = condition_data.get('time', '12:00')

            now = datetime.now()
            current_time = now.strftime('%H:%M')

            if operator == '>':
                return current_time > target_time
            elif operator == '<':
                return current_time < target_time
            elif operator == '>=':
                return current_time >= target_time
            elif operator == '<=':
                return current_time <= target_time

        elif cond_type == 'system':
            metric = condition_data.get('metric', 'cpu')
            operator = condition_data.get('operator', '>')
            value = condition_data.get('value', 50)

            if metric == 'cpu':
                current = psutil.cpu_percent(interval=1)
            elif metric == 'memory':
                current = psutil.virtual_memory().percent
            elif metric == 'disk':
                current = psutil.disk_usage('/').percent
            else:
                return False

            if operator == '>':
                return current > value
            elif operator == '<':
                return current < value
            elif operator == '>=':
                return current >= value
            elif operator == '<=':
                return current <= value

    except Exception as e:
        print(f"Condition evaluation error: {e}")
        return False

    return False

def _execute_workflow_actions(actions: List[Dict[str, Any]]) -> str:
    """Execute a list of workflow actions"""
    results = []

    for action in actions:
        action_type = action.get('type', '')
        params = action.get('params', {})

        try:
            if action_type == 'file_backup':
                source = params.get('source', '')
                destination = params.get('destination', '')
                if source and destination:
                    result = batch_file_operations('copy', [source], destination)
                    results.append(f"Backup: {result}")
                else:
                    results.append("Backup failed: missing source or destination")

            elif action_type == 'send_message':
                # Import dynamically to avoid circular imports
                from actions.send_message import send_message
                receiver = params.get('receiver', '')
                message = params.get('message', '')
                platform = params.get('platform', 'WhatsApp')
                if receiver and message:
                    result = send_message(receiver, message, platform)
                    results.append(f"Message: {result}")
                else:
                    results.append("Message failed: missing receiver or message")

            elif action_type == 'reminder':
                from actions.reminder import reminder
                date = params.get('date', '')
                time = params.get('time', '')
                message = params.get('message', '')
                if date and time and message:
                    result = reminder(date, time, message)
                    results.append(f"Reminder: {result}")
                else:
                    results.append("Reminder failed: missing date, time, or message")

            elif action_type == 'system_control':
                from actions.system_control import system_control
                command = params.get('command', '')
                if command:
                    result = system_control(command)
                    results.append(f"System: {result}")
                else:
                    results.append("System control failed: missing command")

            elif action_type == 'notification':
                # Simple notification using system toast
                try:
                    from win10toast import ToastNotifier
                    toaster = ToastNotifier()
                    title = params.get('title', 'Jarvis Automation')
                    message = params.get('message', 'Automation executed')
                    toaster.show_toast(title, message, duration=5)
                    results.append("Notification sent")
                except:
                    results.append("Notification: Toast not available on this system")

        except Exception as e:
            results.append(f"Action {action_type} failed: {e}")

    return "\n".join(results) if results else "No actions executed"

def create_workflow(name: str, description: str, trigger: str, condition: str = None, actions: List[Dict[str, Any]] = None) -> str:
    """
    Create a new workflow with triggers, conditions, and actions
    """
    _load_workflows()

    if name in _WORKFLOWS:
        return f"Workflow '{name}' already exists. Use update_workflow to modify it."

    workflow = {
        'name': name,
        'description': description,
        'trigger': trigger.lower(),
        'condition': condition,
        'actions': actions or [],
        'enabled': True,
        'created': datetime.now().isoformat(),
        'last_run': None
    }

    _WORKFLOWS[name] = workflow
    _save_workflows()

    # Set up scheduling if needed
    _setup_workflow_schedule(workflow)

    return f"Workflow '{name}' created successfully"

def update_workflow(name: str, **updates) -> str:
    """Update an existing workflow"""
    _load_workflows()

    if name not in _WORKFLOWS:
        return f"Workflow '{name}' not found"

    workflow = _WORKFLOWS[name]

    # Update allowed fields
    for key, value in updates.items():
        if key in ['description', 'trigger', 'condition', 'actions', 'enabled']:
            workflow[key] = value

    workflow['updated'] = datetime.now().isoformat()
    _save_workflows()

    # Update scheduling
    _setup_workflow_schedule(workflow)

    return f"Workflow '{name}' updated successfully"

def delete_workflow(name: str) -> str:
    """Delete a workflow"""
    _load_workflows()

    if name not in _WORKFLOWS:
        return f"Workflow '{name}' not found"

    del _WORKFLOWS[name]
    _save_workflows()

    return f"Workflow '{name}' deleted successfully"

def list_workflows() -> str:
    """List all workflows"""
    _load_workflows()

    if not _WORKFLOWS:
        return "No workflows found"

    result = "Available Workflows:\n\n"
    for name, workflow in _WORKFLOWS.items():
        status = "✅ Enabled" if workflow.get('enabled', True) else "❌ Disabled"
        trigger = workflow.get('trigger', 'unknown')
        condition = workflow.get('condition', 'none')
        actions_count = len(workflow.get('actions', []))
        last_run = workflow.get('last_run', 'never')

        result += f"**{name}**\n"
        result += f"  Status: {status}\n"
        result += f"  Trigger: {trigger}\n"
        result += f"  Condition: {condition}\n"
        result += f"  Actions: {actions_count}\n"
        result += f"  Last Run: {last_run}\n\n"

    return result

def run_workflow(name: str) -> str:
    """Manually run a workflow"""
    _load_workflows()

    if name not in _WORKFLOWS:
        return f"Workflow '{name}' not found"

    workflow = _WORKFLOWS[name]

    if not workflow.get('enabled', True):
        return f"Workflow '{name}' is disabled"

    # Check condition if present
    if workflow.get('condition'):
        condition_data = _parse_condition(workflow['condition'])
        if not _evaluate_condition(condition_data):
            return f"Workflow '{name}' condition not met: {workflow['condition']}"

    # Execute actions
    result = _execute_workflow_actions(workflow.get('actions', []))
    workflow['last_run'] = datetime.now().isoformat()
    _save_workflows()

    return f"Workflow '{name}' executed:\n{result}"

def _setup_workflow_schedule(workflow: Dict[str, Any]):
    """Set up scheduling for a workflow"""
    if not _WORKFLOW_SCHEDULER:
        _start_scheduler()

    trigger = workflow.get('trigger', '').lower()

    # Clear existing schedule for this workflow
    # Note: This is simplified - in production you'd track job IDs

    if 'daily' in trigger:
        # Parse time from trigger like "daily at 10:00"
        time_match = re.search(r'(\d{1,2}):(\d{2})', trigger)
        if time_match:
            hour, minute = time_match.groups()
            _WORKFLOW_SCHEDULER.every().day.at(f"{hour}:{minute}").do(
                lambda: run_workflow(workflow['name'])
            )

    elif 'hourly' in trigger:
        _WORKFLOW_SCHEDULER.every().hour.do(
            lambda: run_workflow(workflow['name'])
        )

    elif 'weekly' in trigger:
        # Parse day from trigger like "weekly on monday"
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in days:
            if day in trigger:
                getattr(_WORKFLOW_SCHEDULER.every(), day).do(
                    lambda: run_workflow(workflow['name'])
                )
                break

def create_conditional_automation(name: str, condition: str, actions: List[Dict[str, Any]], check_interval: int = 60) -> str:
    """
    Create a conditional automation that runs when conditions are met
    """
    _load_workflows()

    if name in _WORKFLOWS:
        return f"Conditional automation '{name}' already exists"

    automation = {
        'name': name,
        'type': 'conditional',
        'condition': condition,
        'actions': actions,
        'check_interval': check_interval,  # seconds
        'enabled': True,
        'created': datetime.now().isoformat(),
        'last_run': None,
        'last_check': None
    }

    _WORKFLOWS[name] = automation
    _save_workflows()

    # Start background checking
    _start_conditional_checking(automation)

    return f"Conditional automation '{name}' created successfully"

def _start_conditional_checking(automation: Dict[str, Any]):
    """Start background checking for conditional automation"""

    def check_loop():
        while automation.get('enabled', True):
            try:
                condition_data = _parse_condition(automation['condition'])
                if _evaluate_condition(condition_data):
                    # Condition met, execute actions
                    result = _execute_workflow_actions(automation['actions'])
                    automation['last_run'] = datetime.now().isoformat()
                    _save_workflows()
                    print(f"Conditional automation '{automation['name']}' triggered: {result}")

                    # For one-time conditions, disable after execution
                    if 'once' in automation.get('condition', '').lower():
                        automation['enabled'] = False
                        _save_workflows()
                        break

                automation['last_check'] = datetime.now().isoformat()
                time_module.sleep(automation.get('check_interval', 60))

            except Exception as e:
                print(f"Conditional automation error: {e}")
                time_module.sleep(60)

    thread = threading.Thread(target=check_loop, daemon=True)
    thread.start()

# Initialize workflows on module load
_load_workflows()
_start_scheduler()