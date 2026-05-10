"""
Supabase DB操作モジュール (REST API版)
supabaseライブラリを使わず、requestsで直接PostgREST APIを叩く
"""
import os
import json
import time
import requests

# 接続設定
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
    """共通リクエスト関数"""
    headers = _get_headers()
    base_url = f"{URL.rstrip('/')}/rest/v1/{table}"
    
    response = requests.request(method, base_url, headers=headers, params=params, json=json_data)
    response.raise_for_status()
    return response.json()

def _parse_json_field(row, field_name):
    """特定のカラムが文字列だった場合に辞書/リストへ変換する"""
    if not row: return row
    val = row.get(field_name)
    if isinstance(val, str):
        try:
            row[field_name] = json.loads(val)
        except:
            row[field_name] = [] if "items" in field_name else {}
    return row

# ────────────── PayPayアカウント ──────────────

def get_paypay_account(discord_user_id: int) -> dict | None:
    res = _request("GET", "paypay_accounts", params={"discord_id": f"eq.{discord_user_id}"})
    return res[0] if res else None

def save_paypay_account(discord_user_id: int, phone: str, password: str, uuid: str, access_token: str = None):
    data = {
        "discord_id": str(discord_user_id),
        "phone": phone,
        "password": password,
        "uuid": uuid
    }
    if access_token:
        data["access_token"] = access_token
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    print(f"--- save_paypay_account ---")
    print(f"data: { {k: v[:10]+'...' if k in ('password','access_token','uuid') and v else v for k, v in data.items()} }")
    res = requests.post(f"{URL}/rest/v1/paypay_accounts", headers=headers, json=data)
    print(f"status: {res.status_code}")
    print(f"response: {res.text[:200]}")
    print(f"--------------------------")

def update_paypay_token(discord_user_id: int, access_token: str):
    """access_tokenだけ更新する"""
    headers = _get_headers()
    headers["Prefer"] = "return=representation"
    requests.patch(
        f"{URL}/rest/v1/paypay_accounts",
        headers=headers,
        params={"discord_id": f"eq.{discord_user_id}"},
        json={"access_token": access_token}
    )

# ────────────── 権限管理 ──────────────

def is_user_allowed(discord_user_id: int) -> bool:
    res = _request("GET", "allowed_users", params={"discord_id": f"eq.{discord_user_id}", "select": "discord_id"})
    return len(res) > 0

def grant_permission(discord_user_id: int, granted_by: int = None, memo: str = None):
    data = {
        "discord_id": str(discord_user_id),
        "granted_by": str(granted_by) if granted_by else None,
        "memo": memo
    }
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    requests.post(f"{URL}/rest/v1/allowed_users", headers=headers, json=data)

def revoke_permission(discord_user_id: int):
    _request("DELETE", "allowed_users", params={"discord_id": f"eq.{discord_user_id}"})

def list_allowed_users() -> list:
    return _request("GET", "allowed_users")

# ────────────── 管理者管理 ──────────────

def is_admin(discord_user_id: int) -> bool:
    res = _request("GET", "admins", params={"discord_id": f"eq.{discord_user_id}", "select": "discord_id"})
    return len(res) > 0

def add_admin(discord_user_id: int):
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    requests.post(f"{URL}/rest/v1/admins", headers=headers, json={"discord_id": str(discord_user_id)})

def remove_admin(discord_user_id: int):
    _request("DELETE", "admins", params={"discord_id": f"eq.{discord_user_id}"})

# ────────────── 販売履歴 ──────────────

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
    return [_parse_json_field(row, "items") for row in res]

# ────────────── 自販機データ ──────────────

def get_vending_machines(owner_id: int = None) -> list:
    params = {}
    if owner_id:
        params["owner_id"] = f"eq.{owner_id}"
    res = _request("GET", "vending_machines", params=params)
    return [_parse_json_field(row, "custom_items") for row in res]

def get_vending_machine(vm_id: str) -> dict | None:
    res = _request("GET", "vending_machines", params={"id": f"eq.{vm_id}"})
    if not res: return None
    return _parse_json_field(res[0], "custom_items")

def create_vending_machine(vm_id: str, name: str, owner_id: int) -> dict:
    data = {
        "id": vm_id,
        "name": name,
        "owner_id": str(owner_id),
        "role_id": None,
        "custom_items": []
    }
    res = _request("POST", "vending_machines", json_data=data)
    return _parse_json_field(res[0], "custom_items") if res else {}

def update_vending_machine(vm_id: str, **kwargs):
    _request("PATCH", "vending_machines", params={"id": f"eq.{vm_id}"}, json_data=kwargs)

# ────────────── ログチャンネル ──────────────

def get_log_channels(guild_id: int) -> dict:
    res = _request("GET", "log_channels", params={"guild_id": f"eq.{guild_id}"})
    return {row["channel_type"]: int(row["channel_id"]) for row in res}

def set_log_channel(guild_id: int, channel_type: str, channel_id: int):
    data = {
        "guild_id": str(guild_id),
        "channel_type": channel_type,
        "channel_id": str(channel_id)
    }
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    requests.post(f"{URL}/rest/v1/log_channels", headers=headers, json=data)

# ────────────── 権限購入設定 ──────────────

def get_permission_price() -> int:
    res = _request("GET", "settings", params={"key": "eq.permission_price"})
    return int(res[0]["value"]) if res else 500

def set_permission_price(price: int):
    data = {"key": "permission_price", "value": str(price)}
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    requests.post(f"{URL}/rest/v1/settings", headers=headers, json=data)

# ────────────── ストック型自販機 ──────────────

def create_stock_shop(shop_id: str, name: str, owner_id: int, price: int) -> dict:
    data = {
        "id": shop_id,
        "name": name,
        "owner_id": str(owner_id),
        "price": price,
    }
    res = _request("POST", "stock_shops", json_data=data)
    return res[0] if res else {}

def get_stock_shops(owner_id: int = None) -> list:
    params = {}
    if owner_id:
        params["owner_id"] = f"eq.{owner_id}"
    return _request("GET", "stock_shops", params=params)

def get_stock_shop(shop_id: str) -> dict | None:
    res = _request("GET", "stock_shops", params={"id": f"eq.{shop_id}"})
    return res[0] if res else None

def update_stock_shop(shop_id: str, **kwargs):
    _request("PATCH", "stock_shops", params={"id": f"eq.{shop_id}"}, json_data=kwargs)

def add_stock_item(shop_id: str, email: str, password: str, note: str = "") -> dict:
    data = {
        "shop_id": shop_id,
        "email": email,
        "password": password,
        "note": note,
        "sold": False,
    }
    res = _request("POST", "stock_items", json_data=data)
    return res[0] if res else {}

def pop_stock_item(shop_id: str) -> dict | None:
    res = _request("GET", "stock_items", params={
        "shop_id": f"eq.{shop_id}",
        "sold": "eq.false",
        "limit": "1"
    })
    if not res:
        return None
    item = res[0]
    _request("PATCH", "stock_items", params={"id": f"eq.{item['id']}"}, json_data={"sold": True})
    return item

def count_stock(shop_id: str) -> int:
    res = _request("GET", "stock_items", params={
        "shop_id": f"eq.{shop_id}",
        "sold": "eq.false",
        "select": "id"
    })
    return len(res)

def list_stock_items(shop_id: str, sold: bool = False) -> list:
    return _request("GET", "stock_items", params={
        "shop_id": f"eq.{shop_id}",
        "sold": f"eq.{str(sold).lower()}"
    })

def delete_stock_item(item_id: int):
    _request("DELETE", "stock_items", params={"id": f"eq.{item_id}"})
