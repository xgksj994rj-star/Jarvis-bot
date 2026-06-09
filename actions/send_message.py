import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.06
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException
    _TWILIO_AVAILABLE = True
except ImportError:
    Client = None
    TwilioRestException = Exception
    _TWILIO_AVAILABLE = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_os() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg.get("os_system", "windows").lower()
    except Exception:
        return "windows"


def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")


def _paste_text(text: str) -> None:
    _require_pyautogui()

    os_name = _get_os()
    paste_hotkey = ("command", "v") if os_name == "mac" else ("ctrl", "v")

    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.15)
        pyautogui.hotkey(*paste_hotkey)
        time.sleep(0.1)
    else:
        pyautogui.write(text, interval=0.03)


def _clear_and_paste(text: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    select_all = ("command", "a") if os_name == "mac" else ("ctrl", "a")
    pyautogui.hotkey(*select_all)
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    _paste_text(text)

def _open_app(app_name: str) -> bool:
    _require_pyautogui()
    os_name = _get_os()

    try:
        if os_name == "windows":
            pyautogui.press("win")
            time.sleep(0.5)
            _paste_text(app_name)
            time.sleep(0.6)
            pyautogui.press("enter")
            time.sleep(2.5)
            return True

        elif os_name == "mac":
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["open", "-a", f"{app_name}.app"],
                    capture_output=True, text=True, timeout=10,
                )
            time.sleep(2.5)
            return result.returncode == 0

        else: 
            launched = False
            for launcher in [
                ["gtk-launch", app_name.lower()],
                [app_name.lower()],
            ]:
                try:
                    subprocess.Popen(
                        launcher,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            time.sleep(2.5)
            return launched

    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open {app_name}: {e}")
        return False


def _open_browser_url(url: str) -> bool:
    import webbrowser
    try:
        webbrowser.open(url)
        time.sleep(4.0) 
        return True
    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open browser: {e}")
        return False

def _search_in_app(query: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    search_hotkey = ("command", "f") if os_name == "mac" else ("ctrl", "f")

    pyautogui.hotkey(*search_hotkey)
    time.sleep(0.5)
    _clear_and_paste(query)
    time.sleep(1.0)

def _desktop_send(app_name: str, receiver: str, message: str) -> str:
    if not _open_app(app_name):
        return f"Could not open {app_name}."

    time.sleep(1.0)
    _search_in_app(receiver)
    pyautogui.press("enter")
    time.sleep(0.8)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)
    return f"Message sent to {receiver} via {app_name}."

def _send_whatsapp(receiver: str, message: str) -> str:
    return _desktop_send("WhatsApp", receiver, message)

def _send_telegram(receiver: str, message: str) -> str:
    return _desktop_send("Telegram", receiver, message)

def _send_signal(receiver: str, message: str) -> str:
    return _desktop_send("Signal", receiver, message)


def _send_discord(receiver: str, message: str) -> str:
    return _desktop_send("Discord", receiver, message)


def _send_instagram(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.instagram.com/direct/new/"):
        return "Could not open Instagram in browser."

    _paste_text(receiver)
    time.sleep(1.5)

    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")   
    time.sleep(0.4)

    for _ in range(4):
        pyautogui.press("tab")
        time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(2.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Instagram."


def _send_messenger(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.messenger.com/"):
        return "Could not open Messenger in browser."


    _search_in_app(receiver)
    time.sleep(0.5)
    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(1.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Messenger."


def _get_twilio_credentials() -> dict[str, str] | None:
    try:
        cfg = json.loads((_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8"))
        account_sid = cfg.get("twilio_account_sid", "").strip()
        auth_token = cfg.get("twilio_auth_token", "").strip()
        api_key = cfg.get("twilio_api_key", "").strip()
        api_secret = cfg.get("twilio_api_secret", "").strip()
        from_number = cfg.get("twilio_phone_number", "").strip()
        if from_number and ((account_sid and auth_token) or (api_key and api_secret and account_sid)):
            return {
                "account_sid": account_sid,
                "auth_token": auth_token,
                "api_key": api_key,
                "api_secret": api_secret,
                "from_number": from_number,
            }
    except Exception:
        pass
    return None


def _get_twilio_client() -> Client | None:
    if not _TWILIO_AVAILABLE:
        return None
    creds = _get_twilio_credentials()
    if not creds:
        return None
    account_sid = creds.get("account_sid", "")
    auth_token = creds.get("auth_token", "")
    api_key = creds.get("api_key", "")
    api_secret = creds.get("api_secret", "")

    if api_key and api_secret and account_sid:
        return Client(api_key, api_secret, account_sid)
    if account_sid and auth_token:
        return Client(account_sid, auth_token)
    return None


def check_twilio_configuration() -> str:
    if not _TWILIO_AVAILABLE:
        return "Twilio package is not installed. Install it with: pip install twilio"
    creds = _get_twilio_credentials()
    if not creds:
        return (
            "Twilio credentials are not configured in config/api_keys.json. "
            "Add twilio_account_sid, twilio_auth_token, and twilio_phone_number, "
            "or twilio_api_key, twilio_api_secret, twilio_account_sid, and twilio_phone_number."
        )

    account_sid = creds.get("account_sid", "")
    auth_token = creds.get("auth_token", "")
    from_number = creds.get("from_number", "")

    if account_sid and not account_sid.startswith("AC"):
        return "Twilio account SID looks invalid. It should start with 'AC'."
    if auth_token and len(auth_token) < 20:
        return "Twilio auth token looks invalid. Please verify your auth token."
    if not from_number.startswith("+"):
        return "Twilio phone number must use the E.164 format with a '+' prefix, e.g. +12019085049."

    client = _get_twilio_client()
    if not client:
        return "Twilio credentials could not be used to create a client. Check your account SID, auth token, and API keys."

    try:
        account = client.api.accounts(account_sid).fetch()
        return f"Twilio configuration is valid for account '{account.friendly_name or account_sid}' and sender {from_number}."
    except TwilioRestException as e:
        return f"Twilio config check failed: status={e.status}, code={e.code}, message={e.msg}."
    except Exception as e:
        return f"Twilio config check failed: {e}"


def _normalize_e164_number(number: str, from_number: str) -> str:
    normalized = number.strip()
    digits = "".join(ch for ch in normalized if ch.isdigit())

    if normalized.startswith("+"):
        return normalized
    if normalized.startswith("00") and len(digits) > 2:
        return "+" + digits[2:]
    if len(digits) == 10 and from_number.startswith("+1"):
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return normalized


def _send_sms_via_twilio(receiver: str, message: str) -> str:
    if not _TWILIO_AVAILABLE:
        return "Twilio package is not installed. Install it with: pip install twilio"
    creds = _get_twilio_credentials()
    if not creds:
        return "Twilio credentials are not configured in config/api_keys.json. Add twilio_account_sid, twilio_auth_token, and twilio_phone_number, or use twilio_api_key, twilio_api_secret, twilio_account_sid, and twilio_phone_number."

    account_sid = creds.get("account_sid", "")
    auth_token = creds.get("auth_token", "")
    from_number = creds.get("from_number", "")

    if account_sid and not account_sid.startswith("AC"):
        return "Twilio account SID looks invalid. It should start with 'AC' and be your Twilio Account SID."
    if auth_token and len(auth_token) < 20:
        return "Twilio auth token looks invalid. Please verify the auth token in config/api_keys.json."
    if not from_number.startswith("+"):
        return "Twilio phone number must use the E.164 format with a '+' prefix, e.g. +12019085049."

    normalized_receiver = _normalize_e164_number(receiver, from_number)
    if not normalized_receiver.startswith("+"):
        return "Receiver phone number could not be normalized to E.164 format. Use a number like +17854625375."

    client = _get_twilio_client()
    if not client:
        return "Twilio credentials could not be used to create a client. Check api_keys.json for valid Twilio SID and token or API key/secret."

    try:
        msg = client.messages.create(
            body=message,
            from_=from_number,
            to=normalized_receiver,
        )
        return f"SMS sent to {normalized_receiver}. Message SID: {msg.sid}."
    except TwilioRestException as e:
        details = f"status={e.status}, code={e.code}, message={e.msg}"
        auth_hint = " Authentication failed. Verify your Account SID and Auth Token in config/api_keys.json." if e.code == 20003 else ""
        return f"Could not send SMS via Twilio: {details}.{auth_hint}"
    except Exception as e:
        return f"Could not send SMS via Twilio: {e}"


def _make_call_via_twilio(receiver: str, message: str) -> str:
    if not _TWILIO_AVAILABLE:
        return "Twilio package is not installed. Install it with: pip install twilio"
    creds = _get_twilio_credentials()
    if not creds:
        return "Twilio credentials are not configured in config/api_keys.json. Add twilio_account_sid, twilio_auth_token, and twilio_phone_number, or use twilio_api_key, twilio_api_secret, twilio_account_sid, and twilio_phone_number."

    account_sid = creds.get("account_sid", "")
    auth_token = creds.get("auth_token", "")
    from_number = creds.get("from_number", "")

    if account_sid and not account_sid.startswith("AC"):
        return "Twilio account SID looks invalid. It should start with 'AC' and be your Twilio Account SID."
    if auth_token and len(auth_token) < 20:
        return "Twilio auth token looks invalid. Please verify the auth token in config/api_keys.json."
    if not from_number.startswith("+"):
        return "Twilio phone number must use the E.164 format with a '+' prefix, e.g. +12019085049."

    normalized_receiver = _normalize_e164_number(receiver, from_number)
    if not normalized_receiver.startswith("+"):
        return "Receiver phone number could not be normalized to E.164 format. Use a number like +17854625375."

    client = _get_twilio_client()
    if not client:
        return "Twilio credentials could not be used to create a client. Check api_keys.json for valid Twilio SID and token or API key/secret."

    try:
        twiml = f'<Response><Say voice="alice">{message}</Say></Response>'
        call = client.calls.create(
            twiml=twiml,
            from_=from_number,
            to=normalized_receiver,
        )
        return f"Phone call initiated to {normalized_receiver}. Call SID: {call.sid}."
    except TwilioRestException as e:
        details = f"status={e.status}, code={e.code}, message={e.msg}"
        auth_hint = " Authentication failed. Verify your Account SID and Auth Token in config/api_keys.json." if e.code == 20003 else ""
        return f"Could not initiate call via Twilio: {details}.{auth_hint}"
    except Exception as e:
        return f"Could not initiate call via Twilio: {e}"


_PLATFORM_MAP = [
    ({"whatsapp", "wp", "wapp"},              _send_whatsapp),
    ({"telegram", "tg"},                      _send_telegram),
    ({"instagram", "ig", "insta"},            _send_instagram),
    ({"signal"},                               _send_signal),
    ({"discord"},                              _send_discord),
    ({"messenger", "facebook", "fb"},         _send_messenger),
    ({"sms", "text", "sms_text", "sms_message"}, _send_sms_via_twilio),
    ({"call", "voice", "phone", "phone_call"}, _make_call_via_twilio),
]


def _resolve_platform(platform_str: str):
    key = platform_str.lower().strip()
    for keywords, handler in _PLATFORM_MAP:
        if any(k in key for k in keywords):
            return handler
    return lambda r, m: _desktop_send(platform_str.strip().title(), r, m)


def send_message(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params       = parameters or {}
    receiver     = params.get("receiver", "").strip()
    message_text = params.get("message_text", "").strip()
    platform     = params.get("platform", "whatsapp").strip()

    if not receiver:
        return "Please specify a recipient."
    if not message_text:
        return "Please specify the message content."
    if not _PYAUTOGUI:
        return "PyAutoGUI is not installed — cannot control the desktop."

    preview = message_text[:50] + ("…" if len(message_text) > 50 else "")
    print(f"[SendMessage] 📨 {platform} → {receiver}: {preview}")
    if player:
        player.write_log(f"[msg] {platform} → {receiver}")

    try:
        handler = _resolve_platform(platform)
        result  = handler(receiver, message_text)
    except Exception as e:
        result = f"Could not send message: {e}"

    print(f"[SendMessage] {'✅' if 'sent' in result.lower() else '❌'} {result}")
    if player:
        player.write_log(f"[msg] {result}")

    return result