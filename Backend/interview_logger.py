import json
import os
import re
import time
from dataclasses import asdict


WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def _sanitize_folder_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "Unknown"

    # Keep it simple and Windows-safe.
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_\-\.]", "", name)
    name = name.strip("._-")
    if not name:
        name = "Unknown"

    if name.upper() in WINDOWS_RESERVED_NAMES:
        name = f"_{name}"

    # Keep paths short-ish.
    return name[:60]


def _guess_name_from_text(text: str) -> str | None:
    """
    Lightweight heuristic for extracting a candidate name from an intro sentence.
    Examples it handles:
      - "My name is John Doe"
      - "I am John"
      - "I'm John Doe"
      - "This is John"
    """
    if not text:
        return None

    t = " ".join(text.strip().split())

    # Capture 1-3 "words" and then title-case them. Works even if STT returns
    # lower-case text.
    patterns = [
        r"\bmy name is\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){0,2})\b",
        r"\bi am\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){0,2})\b",
        r"\bi'm\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){0,2})\b",
        r"\bthis is\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){0,2})\b",
        r"\bIt's me\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){0,2})\b"
    ]

    for pat in patterns:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            # Preserve original casing by title-casing the match.
            name = m.group(1).strip()
            name = " ".join(w[:1].upper() + w[1:] for w in name.split())
            return name

    return None


async def extract_candidate_name(user_text: str, ask_llama_fn) -> str:
    """
    Uses a tiny LLM prompt (via existing ask_llama()) to extract the person's name.
    Falls back to a regex heuristic when the LLM is unavailable or returns junk.
    """
    # Fast path: heuristic.
    guessed = _guess_name_from_text(user_text)
    if guessed:
        return guessed

    prompt = (
        "Extract the candidate's name from the text.\n"
        "Return ONLY a JSON object like: {\"name\": \"John Doe\"}.\n"
        "If the name is not present, return: {\"name\": \"Unknown\"}.\n\n"
        f"Text: {user_text}"
    )

    try:
        # Keep this fast; name extraction shouldn't block the session.
        try:
            resp = await ask_llama_fn(prompt, timeout_s=6)
        except TypeError:
            resp = await ask_llama_fn(prompt)
    except Exception:
        return "Unknown"

    if not resp:
        return "Unknown"

    # Try strict JSON first.
    try:
        data = json.loads(resp.strip())
        name = (data.get("name") or "").strip()
        return name if name else "Unknown"
    except Exception:
        pass

    # Fallback: try to find a plausible name in the model output.
    m = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", resp)
    if m:
        return m.group(1).strip()
    return "Unknown"


class InterviewLogger:
    """
    Manages per-session interview logs under <repo>/interviews/<person_name>_<session_id>/conversation.json
    """

    def __init__(self, base_dir: str, session_id: str):
        self.base_dir = base_dir
        self.session_id = session_id
        self.candidate_name = "Unknown"
        self.dir_path = None
        self.file_path = None
        self.turns = []

    def init_dir(self):
        os.makedirs(self.base_dir, exist_ok=True)
        # Use a stable temporary name until we extract the person name.
        folder = _sanitize_folder_name(f"Unknown_{self.session_id}")
        self.dir_path = os.path.join(self.base_dir, folder)
        os.makedirs(self.dir_path, exist_ok=True)
        self.file_path = os.path.join(self.dir_path, "conversation.json")
        self._flush()

    def set_candidate_name(self, name: str):
        name = (name or "").strip() or "Unknown"
        self.candidate_name = name

        if not self.dir_path:
            return

        desired_folder = _sanitize_folder_name(f"{name}_{self.session_id}")
        desired_path = os.path.join(self.base_dir, desired_folder)
        if os.path.abspath(desired_path) == os.path.abspath(self.dir_path):
            return

        # Rename folder once we know the name.
        try:
            os.replace(self.dir_path, desired_path)
            self.dir_path = desired_path
            self.file_path = os.path.join(self.dir_path, "conversation.json")
        except Exception:
            # If rename fails (e.g., locked), keep the old folder name.
            pass

        self._flush()

    def add_turn(self, role: str, text: str):
        self.turns.append({
            "ts": time.time(),
            "role": role,
            "text": text or ""
        })
        self._flush()

    def _flush(self):
        if not self.file_path:
            return
        payload = {
            "session_id": self.session_id,
            "candidate_name": self.candidate_name,
            "turns": self.turns,
        }
        tmp = self.file_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2)
        os.replace(tmp, self.file_path)
