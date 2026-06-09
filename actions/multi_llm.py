"""
Multi-LLM Support for MARK XXXVII
Allows switching between different AI models (Gemini, OpenAI, Anthropic, etc.)
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

# Supported LLM providers and their models
SUPPORTED_LLMS = {
    "gemini": {
        "name": "Google Gemini",
        "models": [
            "models/gemini-2.5-flash-native-audio-preview-12-2025",
            "models/gemini-2.0-flash",
            "models/gemini-1.5-pro",
            "models/gemini-2.5-pro"
        ],
        "requires": ["gemini_api_key"]
    },
    "openai": {
        "name": "OpenAI",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo"
        ],
        "requires": ["openai_api_key"]
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307"
        ],
        "requires": ["anthropic_api_key"]
    },
    "groq": {
        "name": "Groq",
        "models": [
            "llama-3.3-70b-versatile",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ],
        "requires": ["groq_api_key"]
    },
    "ollama": {
        "name": "Ollama (Local)",
        "models": [
            "llama3",
            "mistral",
            "codellama",
            "phi3"
        ],
        "requires": ["ollama_host"],
        "is_local": True
    }
}

# Current active LLM
_current_llm: str = "gemini"
_current_model: str = "models/gemini-2.5-flash-native-audio-preview-12-2025"


def load_config() -> Dict[str, Any]:
    """Load API configuration from config file."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save API configuration to config file."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def get_current_llm() -> tuple[str, str]:
    """Get the currently active LLM and model."""
    return _current_llm, _current_model


def set_current_llm(llm_name: str, model: Optional[str] = None) -> str:
    """
    Set the active LLM provider.
    
    Args:
        llm_name: Name of the LLM provider (gemini, openai, anthropic, groq, ollama)
        model: Specific model to use (optional, uses default if not specified)
    
    Returns:
        Status message
    """
    global _current_llm, _current_model
    
    llm_name = llm_name.lower()
    
    if llm_name not in SUPPORTED_LLMS:
        return f"Error: Unknown LLM provider '{llm_name}'. Available: {', '.join(SUPPORTED_LLMS.keys())}"
    
    config = load_config()
    llm_info = SUPPORTED_LLMS[llm_name]
    
    # Check if required API keys are configured
    for req_key in llm_info["requires"]:
        if req_key not in config or not config[req_key]:
            return f"Error: {llm_info['name']} requires '{req_key}' to be configured in config/api_keys.json"
    
    _current_llm = llm_name
    
    if model:
        if model not in llm_info["models"]:
            return f"Error: Model '{model}' not available for {llm_info['name']}. Available: {', '.join(llm_info['models'])}"
        _current_model = model
    else:
        _current_model = llm_info["models"][0]
    
    return f"Switched to {llm_info['name']} ({_current_model})"


def list_available_llms() -> str:
    """List all available LLM providers and their status."""
    config = load_config()
    result = ["🤖 Available LLM Providers:\n"]
    
    for llm_key, llm_info in SUPPORTED_LLMS.items():
        # Check if configured
        is_configured = all(key in config and config[key] for key in llm_info["requires"])
        status = "✅ Configured" if is_configured else "❌ Not configured"
        
        result.append(f"\n### {llm_info['name']} ({llm_key})")
        result.append(f"Status: {status}")
        result.append(f"Models: {', '.join(llm_info['models'][:3])}")
        
        if llm_key == _current_llm:
            result.append(f"👉 Currently active: {_current_model}")
    
    return "\n".join(result)


def add_api_key(provider: str, api_key: str, ollama_host: Optional[str] = None) -> str:
    """
    Add or update an API key for a provider.
    
    Args:
        provider: LLM provider name (gemini, openai, anthropic, groq)
        api_key: The API key
        ollama_host: For Ollama, the host URL (optional)
    
    Returns:
        Status message
    """
    provider = provider.lower()
    
    if provider not in SUPPORTED_LLMS:
        return f"Error: Unknown provider '{provider}'"
    
    config = load_config()
    key_name = SUPPORTED_LLMS[provider]["requires"][0]
    
    if provider == "ollama":
        config["ollama_host"] = ollama_host or "http://localhost:11434"
    else:
        config[key_name] = api_key
    
    save_config(config)
    return f"✅ API key added for {SUPPORTED_LLMS[provider]['name']}"


def get_llm_response(prompt: str, system_prompt: Optional[str] = None) -> str:
    """
    Get a response from the currently active LLM.
    
    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
    
    Returns:
        LLM response text
    """
    config = load_config()
    
    if _current_llm == "gemini":
        return _get_gemini_response(prompt, system_prompt, config)
    elif _current_llm == "openai":
        return _get_openai_response(prompt, system_prompt, config)
    elif _current_llm == "anthropic":
        return _get_anthropic_response(prompt, system_prompt, config)
    elif _current_llm == "groq":
        return _get_groq_response(prompt, system_prompt, config)
    elif _current_llm == "ollama":
        return _get_ollama_response(prompt, system_prompt, config)
    
    return "Error: No LLM configured"


def _get_gemini_response(prompt: str, system_prompt: Optional[str], config: Dict) -> str:
    """Get response from Gemini."""
    try:
        client = genai.Client(api_key=config["gemini_api_key"])
        
        config_list = [
            types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="text/plain",
            )
        ]
        
        response = client.models.generate_content(
            model=_current_model,
            contents=prompt,
            config=config_list[0]
        )
        
        return response.text if hasattr(response, 'text') else str(response)
    except Exception as e:
        return f"Error with Gemini: {str(e)}"


def _get_openai_response(prompt: str, system_prompt: Optional[str], config: Dict) -> str:
    """Get response from OpenAI."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config["openai_api_key"])
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=_current_model,
            messages=messages
        )
        
        return response.choices[0].message.content
    except ImportError:
        return "Error: OpenAI package not installed. Run: pip install openai"
    except Exception as e:
        return f"Error with OpenAI: {str(e)}"


def _get_anthropic_response(prompt: str, system_prompt: Optional[str], config: Dict) -> str:
    """Get response from Anthropic Claude."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=config["anthropic_api_key"])
        
        response = client.messages.create(
            model=_current_model,
            max_tokens=4096,
            system=system_prompt or "You are a helpful AI assistant.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    except ImportError:
        return "Error: Anthropic package not installed. Run: pip install anthropic"
    except Exception as e:
        return f"Error with Anthropic: {str(e)}"


def _get_groq_response(prompt: str, system_prompt: Optional[str], config: Dict) -> str:
    """Get response from Groq."""
    try:
        from groq import Groq
        client = Groq(api_key=config["groq_api_key"])
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=_current_model,
            messages=messages
        )
        
        return response.choices[0].message.content
    except ImportError:
        return "Error: Groq package not installed. Run: pip install groq"
    except Exception as e:
        return f"Error with Groq: {str(e)}"


def _get_ollama_response(prompt: str, system_prompt: Optional[str], config: Dict) -> str:
    """Get response from Ollama (local)."""
    try:
        import requests
        host = config.get("ollama_host", "http://localhost:11434")
        
        payload = {
            "model": _current_model,
            "prompt": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt,
            "stream": False
        }
        
        response = requests.post(f"{host}/api/generate", json=payload, timeout=120)
        response.raise_for_status()
        
        return response.json().get("response", "No response")
    except ImportError:
        return "Error: Requests package not installed. Run: pip install requests"
    except Exception as e:
        return f"Error with Ollama: {str(e)}"


# ── Action function for JARVIS ─────────────────────────────────────────────────
def multi_llm_action(action: str, provider: str = "", model: str = "", api_key: str = "", ollama_host: str = "") -> str:
    """
    Main action function to be called from JARVIS.
    
    Args:
        action: The action to perform (switch, list, add_key)
        provider: LLM provider name
        model: Model name
        api_key: API key to add
        ollama_host: Ollama host URL
    
    Returns:
        Response message
    """
    action = action.lower()
    
    if action == "switch":
        if not provider:
            return "Please specify a provider to switch to. Example: switch to openai"
        return set_current_llm(provider, model if model else None)
    
    elif action == "list" or action == "available":
        return list_available_llms()
    
    elif action == "add_key" or action == "add":
        if not provider or not api_key:
            return "Please specify provider and api_key. Example: add_key openai sk-..."
        return add_api_key(provider, api_key, ollama_host if ollama_host else None)
    
    elif action == "current":
        current_llm, current_model = get_current_llm()
        return f"Current LLM: {SUPPORTED_LLMS[current_llm]['name']} ({current_model})"
    
    else:
        return f"Unknown action '{action}'. Available: switch, list, add_key, current"