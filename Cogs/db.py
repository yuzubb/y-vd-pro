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
            row[field_name] = [] if "items" in field_name or "products" in field_name else {}
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

def get_all_paypay_accounts() -> list:
    return _request("GET", "paypay_accounts")

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

def get_all_vending_machines() -> dict:
    """全自販機を {vm_id: vm_dict} 形式で返す"""
    res = _request("GET", "vending_machines")
    result = {}
    for row in res:
        row = _parse_json_field(row, "products")
        result[row["id"]] = {
            "name": row["name"],
            "owner_id": row["owner_id"],
            "paypay_id": row.get("paypay_id"),
            "log_channel_id": int(row["log_channel_id"]) if row.get("log_channel_id") else None,
            "private_log_channel_id": int(row["private_log_channel_id"]) if row.get("private_log_channel_id") else None,
            "products": row.get("products") or []
        }
    return result

def get_vending_machine(vm_id: str) -> dict | None:
    """単一自販機を辞書形式で返す"""
    res = _request("GET", "vending_machines", params={"id": f"eq.{vm_id}"})
    if not res:
        return None
    row = _parse_json_field(res[0], "products")
    return {
        "name": row["name"],
        "owner_id": row["owner_id"],
        "paypay_id": row.get("paypay_id"),
        "log_channel_id": int(row["log_channel_id"]) if row.get("log_channel_id") else None,
        "private_log_channel_id": int(row["private_log_channel_id"]) if row.get("private_log_channel_id") else None,
        "products": row.get("products") or []
    }

def create_vending_machine(vm_id: str, name: str, owner_id: int, paypay_id: str = None) -> dict:
    data = {
        "id": vm_id,
        "name": name,
        "owner_id": str(owner_id),
        "paypay_id": paypay_id,
        "log_channel_id": None,
        "private_log_channel_id": None,
        "products": json.dumps([]),
        "custom_items": json.dumps([])
    }
    res = _request("POST", "vending_machines", json_data=data)
    return res[0] if res else {}

def update_vending_machine(vm_id: str, **kwargs):
    """任意カラムを更新。productsリストを渡すと自動でJSON化する"""
    if "products" in kwargs and isinstance(kwargs["products"], list):
        kwargs["products"] = json.dumps(kwargs["products"], ensure_ascii=False)
    _request("PATCH", "vending_machines", params={"id": f"eq.{vm_id}"}, json_data=kwargs)

def delete_vending_machine(vm_id: str):
    _request("DELETE", "vending_machines", params={"id": f"eq.{vm_id}"})

# ────────────── 在庫アイテム ──────────────

def add_stock_lines(product_id: str, lines: list[str]):
    """複数行をstock_itemsにまとめてINSERT"""
    headers = _get_headers()
    data = [{"product_id": product_id, "content": line, "sold": False} for line in lines if line.strip()]
    if not data:
        return
    res = requests.post(f"{URL}/rest/v1/stock_items", headers=headers, json=data)
    res.raise_for_status()

def count_stock(product_id: str) -> int:
    res = _request("GET", "stock_items", params={
        "product_id": f"eq.{product_id}",
        "sold": "eq.false",
        "select": "id"
    })
    return len(res)

def pop_stock_items(product_id: str, quantity: int) -> list[str]:
    """在庫からquantity個取り出し（soldをtrueに）して内容リストを返す"""
    res = _request("GET", "stock_items", params={
        "product_id": f"eq.{product_id}",
        "sold": "eq.false",
        "order": "id.asc",
        "limit": str(quantity)
    })
    if len(res) < quantity:
        return []
    ids = [str(row["id"]) for row in res]
    _request("PATCH", "stock_items",
             params={"id": f"in.({','.join(ids)})"},
             json_data={"sold": True})
    return [row["content"] for row in res]

def list_stock_contents(product_id: str) -> list[str]:
    """在庫内容を全件取得"""
    res = _request("GET", "stock_items", params={
        "product_id": f"eq.{product_id}",
        "sold": "eq.false",
        "order": "id.asc"
    })
    return [row["content"] for row in res]

def delete_product_stock(product_id: str):
    """商品の在庫を全件削除"""
    _request("DELETE", "stock_items", params={"product_id": f"eq.{product_id}"})

# ────────────── 在庫通知設定 ──────────────

def get_stock_notification(vending_machine_id: str) -> dict | None:
    res = _request("GET", "stock_notifications", params={"vending_machine_id": f"eq.{vending_machine_id}"})
    return res[0] if res else None

def set_stock_notification(vending_machine_id: str, channel_id: int, role_id: int, guild_id: int):
    data = {
        "vending_machine_id": vending_machine_id,
        "channel_id": str(channel_id),
        "role_id": str(role_id),
        "guild_id": str(guild_id)
    }
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    res = requests.post(f"{URL}/rest/v1/stock_notifications", headers=headers, json=data)
    res.raise_for_status()

def delete_stock_notification(vending_machine_id: str):
    _request("DELETE", "stock_notifications", params={"vending_machine_id": f"eq.{vending_machine_id}"})

# ────────────── クーポン ──────────────

def get_coupon(coupon_code: str) -> dict | None:
    res = _request("GET", "coupons", params={"coupon_code": f"eq.{coupon_code}"})
    return res[0] if res else None

def get_coupons_by_owner(owner_id: int) -> dict:
    """オーナーのクーポンを {code: info} 形式で返す"""
    res = _request("GET", "coupons", params={"owner_id": f"eq.{owner_id}"})
    return {row["coupon_code"]: {
        "discount": row["discount"],
        "owner_id": row["owner_id"],
        "vending_machine_id": row["vending_machine_id"],
        "created_at": row.get("created_at", "")
    } for row in res}

def create_coupon(coupon_code: str, discount: int, owner_id: int, vending_machine_id: str):
    data = {
        "coupon_code": coupon_code,
        "discount": discount,
        "owner_id": str(owner_id),
        "vending_machine_id": vending_machine_id
    }
    _request("POST", "coupons", json_data=data)

def delete_coupon(coupon_code: str):
    _request("DELETE", "coupons", params={"coupon_code": f"eq.{coupon_code}"})

# ────────────── ロール付与設定 ──────────────

def get_role_assignment(vending_machine_id: str) -> dict | None:
    res = _request("GET", "role_assignments", params={"vending_machine_id": f"eq.{vending_machine_id}"})
    return res[0] if res else None

def set_role_assignment(vending_machine_id: str, role_id: int, guild_id: int):
    data = {
        "vending_machine_id": vending_machine_id,
        "role_id": str(role_id),
        "guild_id": str(guild_id)
    }
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    res = requests.post(f"{URL}/rest/v1/role_assignments", headers=headers, json=data)
    res.raise_for_status()

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

# ────────────── ストック型自販機 (旧API 互換) ──────────────

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

def list_stock_items(shop_id: str, sold: bool = False) -> list:
    return _request("GET", "stock_items", params={
        "shop_id": f"eq.{shop_id}",
        "sold": f"eq.{str(sold).lower()}"
    })

def delete_stock_item(item_id: int):
    _request("DELETE", "stock_items", params={"id": f"eq.{item_id}"})
