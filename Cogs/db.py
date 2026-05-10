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

def _parse_json_field(row, field_name):
    if not row: return row
    val = row.get(field_name)
    if isinstance(val, str):
        try:
            row[field_name] = json.loads(val)
        except:
            row[field_name] = []
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

def grant_permission(discord_user_id: int, granted_by: int = None, memo: str = None):
    data = {"discord_id": str(discord_user_id), "granted_by": str(granted_by), "memo": memo}
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    requests.post(f"{URL}/rest/v1/allowed_users", headers=headers, json=data)

def get_vending_machines(owner_id: int = None) -> list:
    params = {"owner_id": f"eq.{owner_id}"} if owner_id else {}
    res = _request("GET", "vending_machines", params=params)
    return [_parse_json_field(row, "custom_items") for row in res]

def get_vending_machine(vm_id: str) -> dict | None:
    res = _request("GET", "vending_machines", params={"id": f"eq.{vm_id}"})
    return _parse_json_field(res[0], "custom_items") if res else None

def update_vending_machine(vm_id: str, **kwargs):
    _request("PATCH", "vending_machines", params={"id": f"eq.{vm_id}"}, json_data=kwargs)
