# state_manager.py
import json
import os
from pathlib import Path

def load_state(path):
    if not os.path.exists(path):
        return {"items": {}}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except:
        return {"items": {}}

def save_state(path, state):
    Path(path).write_text(json.dumps(state, indent=2), encoding="utf-8")

def has_changed(state, item):
    sid = str(item["id"])
    prev = state["items"].get(sid)

    current = {
        "next_ep_date": item["next_ep_date"],
        "next_ep_number": item["next_ep_number"],
        "status": item["status"],
    }

    if prev is None:
        return True

    # Compare only the fields that matter
    if prev["next_ep_date"] != current["next_ep_date"]:
        return True
    if prev["next_ep_number"] != current["next_ep_number"]:
        return True
    if prev["status"] != current["status"]:
        return True

    return False

def update_state_entry(state, item, message_id):
    sid = str(item["id"])
    state["items"][sid] = {
        "next_ep_date": item["next_ep_date"],
        "next_ep_number": item["next_ep_number"],
        "status": item["status"],
        "discord_message_id": message_id
    }

def get_message_id(state, item_id):
    entry = state["items"].get(str(item_id))
    if entry:
        return entry.get("discord_message_id")
    return None

def remove_entry(state, item_id):
    state["items"].pop(str(item_id), None)
