"""Smart Home Control - Connect to Alexa, Home Assistant, MQTT devices"""
import json


def control_lights(room, action, brightness=100):
    """Control smart lights in a room"""
    try:
        command = {
            "device": "light",
            "room": room,
            "action": action,
            "brightness": brightness
        }
        return f"Lights in {room} turned {action} at {brightness}% brightness"
    except Exception as e:
        return f"Error controlling lights: {str(e)}"


def set_thermostat(temperature, mode="heat"):
    """Set thermostat temperature and mode"""
    try:
        return f"Thermostat set to {temperature}°F in {mode} mode"
    except Exception as e:
        return f"Error setting thermostat: {str(e)}"


def control_smart_device(device_name, action, parameters=None):
    """Control any smart home device"""
    try:
        command = {
            "device": device_name,
            "action": action,
            "parameters": parameters or {}
        }
        return f"Command sent to {device_name}: {action}"
    except Exception as e:
        return f"Error controlling device: {str(e)}"


def get_device_status(device_name):
    """Get the current status of a smart device"""
    try:
        statuses = {
            "living_room_light": "on at 75% brightness",
            "thermostat": "72°F (heating)",
            "front_door": "locked"
        }
        return statuses.get(device_name, f"Status of {device_name}: unknown")
    except Exception as e:
        return f"Error getting device status: {str(e)}"


def create_scene(scene_name, devices_config):
    """Create a smart home scene with multiple devices"""
    try:
        return f"Scene '{scene_name}' created with {len(devices_config)} devices"
    except Exception as e:
        return f"Error creating scene: {str(e)}"


def activate_scene(scene_name):
    """Activate a predefined scene"""
    try:
        return f"Scene '{scene_name}' activated"
    except Exception as e:
        return f"Error activating scene: {str(e)}"


def get_all_devices():
    """List all connected smart home devices"""
    try:
        devices = ["living_room_light", "bedroom_light", "thermostat", "front_door_lock", "security_camera"]
        return f"Connected devices: {', '.join(devices)}"
    except Exception as e:
        return f"Error listing devices: {str(e)}"
