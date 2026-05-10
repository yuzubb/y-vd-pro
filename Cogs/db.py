import os
import json
import time
import requests

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")

def _get_headers():
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
    """AttributeErrorを確実に防ぐための型変換ガード"""
    if not isinstance(row, dict):
        return {}
    
    # 変換対象のカラム
    target_fields = ["custom_items", "items"]
    for field in target_fields:
        val = row.get(field)
        if isinstance(val, str):
            try:
                row[field] = json.loads(val)
            except:
                row[field] = []
        elif val is None:
            row[field] = []
        elif not isinstance(val, (list, dict)):
            row[field] = []
            
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
    res = _request("GET", "allowed_users", params={"discord_id": f"eq.{discord_user_id}"})
    return len(res) > 0

def is_admin(discord_user_id: int) -> bool:
    res = _request("GET", "admins", params={"discord_id": f"eq.{discord_user_id}"})
    return len(res) > 0

def record_sale(vending_id: str, user_id: int, user_name: str, items: list, total_price: int):
    data = {"vending_id": vending_id, "user_id": str(user_id), "user_name": user_name, "items": items, "total_price": total_price, "created_at": int(time.time())}
    _request("POST", "sales_history", json_data=data)

def get_sales(vending_id: str) -> list:
    res = _request("GET", "sales_history", params={"vending_id": f"eq.{vending_id}"})
    return [_parse_fields(row) for row in res if isinstance(row, dict)]

def get_vending_machines(owner_id: int = None) -> list:
    params = {"owner_id": f"eq.{owner_id}"} if owner_id else {}
    res = _request("GET", "vending_machines", params=params)
    return [_parse_fields(row) for row in res if isinstance(row, dict)]

def get_vending_machine(vm_id: str) -> dict | None:
    res = _request("GET", "vending_machines", params={"id": f"eq.{vm_id}"})
    if not res or not isinstance(res, list): return None
    return _parse_fields(res[0])

def update_vending_machine(vm_id: str, **kwargs):
    _request("PATCH", "vending_machines", params={"id": f"eq.{vm_id}"}, json_data=kwargs)

def get_log_channels(guild_id: int) -> dict:
    res = _request("GET", "log_channels", params={"guild_id": f"eq.{guild_id}"})
    return {row["channel_type"]: int(row["channel_id"]) for row in res if isinstance(row, dict)}

def set_log_channel(guild_id: int, channel_type: str, channel_id: int):
    data = {"guild_id": str(guild_id), "channel_type": channel_type, "channel_id": str(channel_id)}
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    requests.post(f"{URL}/rest/v1/log_channels", headers=headers, json=data)
