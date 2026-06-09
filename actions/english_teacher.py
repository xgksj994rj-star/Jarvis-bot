import json
import re
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
GEMINI_MODEL = "gemini-2.5-flash"


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _get_gemini(model: str = GEMINI_MODEL):
    import google.generativeai as genai

    genai.configure(api_key=_get_api_key())
    return genai.GenerativeModel(model)


def _clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _resolve_save_path(path: str) -> Path:
    if path:
        p = Path(path)
        return p if p.is_absolute() else Path.home() / "Desktop" / p
    return Path.home() / "Desktop" / "jarvis_english_output.txt"


def _save_file(path: Path, content: str) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Saved to: {path}"
    except Exception as e:
        return f"Could not save: {e}"


def _build_prompt(action: str, description: str, text: str, instruction: str, audience: str, tone: str, length: str) -> str:
    style = []
    if audience:
        style.append(f"Target audience: {audience}.")
    if tone:
        style.append(f"Tone: {tone}.")
    if length:
        style.append(f"Length guideline: {length}.")

    style_line = " " .join(style).strip()
    if style_line:
        style_line = f" {style_line}"

    if action in {"proofread", "grammar_check"}:
        return f"""You are an expert English teacher and proofreader.
Correct the following text for grammar, punctuation, spelling, clarity, and flow.
Keep the meaning intact, polish sentence structure, and preserve academic tone when appropriate.

Text:
{text}

Corrected version:"""

    if action == "summarize":
        return f"""You are an expert English teacher and summarizer.
Summarize the following text clearly and concisely while preserving the main ideas.

Text:
{text}

Summary:"""

    if action == "edit":
        return f"""You are an expert English teacher and editor.
Edit the following text according to this instruction: {instruction}
Preserve the original meaning, improve readability, grammar, and flow, and keep the output natural.

Original text:
{text}

Edited version:"""

    # write and default behavior
    prompt = f"""You are an expert English teacher and academic writer.
Write a well-structured, polished, and original piece based on the user's request.
Use excellent grammar, correct punctuation, smooth transitions, and clear organization.
{style_line}

Instructions:
{description}

Output:"""
    return prompt


def _generate_text(prompt: str) -> str:
    model = _get_gemini()
    response = model.generate_content(prompt)
    return _clean_text(response.text)


def _write_action(description: str, audience: str, tone: str, length: str, output_path: str, player=None) -> str:
    if not description:
        return "Please tell me what you want me to write, sir."

    if player:
        player.write_log("[English] Writing text...")

    prompt = _build_prompt("write", description, "", "", audience, tone, length)
    try:
        result = _generate_text(prompt)
    except Exception as e:
        return f"Could not generate text: {e}"

    path = _resolve_save_path(output_path)
    save_status = _save_file(path, result)
    return f"Text written. {save_status}\n\nPreview:\n{result[:800]}"


def _proofread_action(text: str, output_path: str, player=None) -> str:
    if not text:
        return "Please provide the text you want proofread, sir."
    if player:
        player.write_log("[English] Proofreading text...")
    prompt = _build_prompt("proofread", "", text, "", "", "", "")
    try:
        result = _generate_text(prompt)
    except Exception as e:
        return f"Could not proofread text: {e}"
    path = _resolve_save_path(output_path)
    save_status = _save_file(path, result)
    return f"Proofreading complete. {save_status}\n\nPreview:\n{result[:800]}"


def _summarize_action(text: str, output_path: str, player=None) -> str:
    if not text:
        return "Please provide the text you want summarized, sir."
    if player:
        player.write_log("[English] Summarizing text...")
    prompt = _build_prompt("summarize", "", text, "", "", "", "")
    try:
        result = _generate_text(prompt)
    except Exception as e:
        return f"Could not summarize text: {e}"
    path = _resolve_save_path(output_path)
    save_status = _save_file(path, result)
    return f"Summary complete. {save_status}\n\nPreview:\n{result[:800]}"


def _edit_action(text: str, instruction: str, output_path: str, player=None) -> str:
    if not text:
        return "Please provide the text you want edited, sir."
    if not instruction:
        return "Please provide an instruction for how to edit the text, sir."
    if player:
        player.write_log("[English] Editing text...")
    prompt = _build_prompt("edit", "", text, instruction, "", "", "")
    try:
        result = _generate_text(prompt)
    except Exception as e:
        return f"Could not edit text: {e}"
    path = _resolve_save_path(output_path)
    save_status = _save_file(path, result)
    return f"Edit complete. {save_status}\n\nPreview:\n{result[:800]}"


def english_teacher(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "write").strip().lower()
    description = p.get("description", "").strip()
    text = p.get("text", "").strip()
    instruction = p.get("instruction", "").strip()
    audience = p.get("audience", "").strip()
    tone = p.get("tone", "").strip()
    length = p.get("length", "").strip()
    output_path = p.get("output_path", "").strip()

    if action in {"proofread", "grammar_check", "grammar", "edit_text"}:
        return _proofread_action(text or description, output_path, player)
    if action == "summarize":
        return _summarize_action(text, output_path, player)
    if action == "edit":
        return _edit_action(text, instruction or description, output_path, player)
    if action == "write":
        return _write_action(description or text, audience, tone, length, output_path, player)

    return (
        "Unknown action: '{action}'. Use write, proofread, grammar_check, summarize, or edit."
    )
