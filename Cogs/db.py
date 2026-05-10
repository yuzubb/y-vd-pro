import os
import json
import time
import requests

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")

def _get_headers():
    if not URL or not KEY:
        raise RuntimeError("SUPABASE_URL と SUPABASE_KEY を .env に設定してください")
    return {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def _request(method, table, params=None, json_data=None):
    headers = _get_headers()
    base_url = f"{URL.rstrip('/')}/rest/v1/{table}"
    response = requests.request(method, base_url, headers=headers, params=params, json=json_data)
    response.raise_for_status()
    return response.json()

def _parse_fields(row):
    """JSONBフィールドを辞書に変換するヘルパー"""
    if not row: return row
    # custom_itemsフィールドの処理
    if "custom_items" in row and isinstance(row["custom_items"], str):
        try:
            row["custom_items"] = json.loads(row["custom_items"])
        except:
            row["custom_items"] = []
    # itemsフィールド(販売履歴用)の処理
    if "items" in row and isinstance(row["items"], str):
        try:
            row["items"] = json.loads(row["items"])
        except:
            row["items"] = []
    return row

def get_paypay_account(discord_user_id: int) -> dict | None:
    res = _request("GET", "paypay_accounts", params={"discord_id": f"eq.{discord_user_id}"})
    return res[0] if res else None

def save_paypay_account(discord_user_id: int, phone: str, password: str, uuid: str):
    data = {"discord_id": str(discord_user_id), "phone": phone, "password": password, "uuid": uuid}
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    requests.post(f"{URL}/rest/v1/paypay_accounts", headers=headers, json=data)

def is_user_allowed(discord_user_id: int) -> bool:
    res = _request("GET", "allowed_users", params={"discord_id": f"eq.{discord_user_id}", "select": "discord_id"})
    return len(res) > 0

def record_sale(vending_id: str, user_id: int, user_name: str, items: list, total_price: int):
    data = {
        "vending_id": vending_id,
        "user_id": str(user_id),
        "user_name": user_name,
        "items": items,
        "total_price": total_price,
        "created_at": int(time.time())
    }
    _request("POST", "sales_history", json_data=data)

def get_sales(vending_id: str) -> list:
    res = _request("GET", "sales_history", params={"vending_id": f"eq.{vending_id}"})
    return [_parse_fields(row) for row in res]

def get_vending_machines(owner_id: int = None) -> list:
    params = {"owner_id": f"eq.{owner_id}"} if owner_id else {}
    res = _request("GET", "vending_machines", params=params)
    return [_parse_fields(row) for row in res]

def get_vending_machine(vm_id: str) -> dict | None:
    res = _request("GET", "vending_machines", params={"id": f"eq.{vm_id}"})
    return _parse_fields(res[0]) if res else None

def create_vending_machine(vm_id: str, name: str, owner_id: int) -> dict:
    data = {"id": vm_id, "name": name, "owner_id": str(owner_id), "role_id": None, "custom_items": []}
    res = _request("POST", "vending_machines", json_data=data)
    return _parse_fields(res[0]) if res else {}

def update_vending_machine(vm_id: str, **kwargs):
    _request("PATCH", "vending_machines", params={"id": f"eq.{vm_id}"}, json_data=kwargs)

def get_log_channels(guild_id: int) -> dict:
    res = _request("GET", "log_channels", params={"guild_id": f"eq.{guild_id}"})
    return {row["channel_type"]: int(row["channel_id"]) for row in res}

def set_log_channel(guild_id: int, channel_type: str, channel_id: int):
    data = {"guild_id": str(guild_id), "channel_type": channel_type, "channel_id": str(channel_id)}
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    requests.post(f"{URL}/rest/v1/log_channels", headers=headers, json=data)
