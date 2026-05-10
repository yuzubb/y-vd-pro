"""
Supabase DB操作モジュール
全データをSupabaseに保存し、サーバー再起動後も永続化する
"""
import os
from supabase import create_client, Client

_client: Client = None

def get_db() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL と SUPABASE_KEY を .env に設定してください")
        _client = create_client(url, key)
    return _client

# ────────────── PayPayアカウント ──────────────

def get_paypay_account(discord_user_id: int) -> dict | None:
    """DiscordユーザーIDに紐づくPayPayアカウント情報を取得"""
    db = get_db()
    res = db.table("paypay_accounts").select("*").eq("discord_id", str(discord_user_id)).execute()
    return res.data[0] if res.data else None

def save_paypay_account(discord_user_id: int, phone: str, password: str, uuid: str):
    """PayPayアカウント情報をupsert"""
    db = get_db()
    db.table("paypay_accounts").upsert({
        "discord_id": str(discord_user_id),
        "phone": phone,
        "password": password,
        "uuid": uuid
    }, on_conflict="discord_id").execute()

# ────────────── 権限管理 ──────────────

def is_user_allowed(discord_user_id: int) -> bool:
    """ユーザーがBotの使用権限を持っているか確認"""
    db = get_db()
    res = db.table("allowed_users").select("discord_id").eq("discord_id", str(discord_user_id)).execute()
    return len(res.data) > 0

def grant_permission(discord_user_id: int, granted_by: int = None, memo: str = None):
    """ユーザーに権限を付与"""
    db = get_db()
    db.table("allowed_users").upsert({
        "discord_id": str(discord_user_id),
        "granted_by": str(granted_by) if granted_by else None,
        "memo": memo
    }, on_conflict="discord_id").execute()

def revoke_permission(discord_user_id: int):
    """ユーザーの権限を剥奪"""
    db = get_db()
    db.table("allowed_users").delete().eq("discord_id", str(discord_user_id)).execute()

def list_allowed_users() -> list:
    """権限を持つ全ユーザーのリストを返す"""
    db = get_db()
    res = db.table("allowed_users").select("*").execute()
    return res.data

# ────────────── 管理者管理 ──────────────

def is_admin(discord_user_id: int) -> bool:
    db = get_db()
    res = db.table("admins").select("discord_id").eq("discord_id", str(discord_user_id)).execute()
    return len(res.data) > 0

def add_admin(discord_user_id: int):
    db = get_db()
    db.table("admins").upsert({"discord_id": str(discord_user_id)}, on_conflict="discord_id").execute()

def remove_admin(discord_user_id: int):
    db = get_db()
    db.table("admins").delete().eq("discord_id", str(discord_user_id)).execute()

# ────────────── 販売履歴 ──────────────

def record_sale(vending_id: str, user_id: int, user_name: str, items: list, total_price: int):
    db = get_db()
    import json, time
    db.table("sales_history").insert({
        "vending_id": vending_id,
        "user_id": str(user_id),
        "user_name": user_name,
        "items": json.dumps(items, ensure_ascii=False),
        "total_price": total_price,
        "created_at": int(time.time())
    }).execute()

def get_sales(vending_id: str) -> list:
    import json
    db = get_db()
    res = db.table("sales_history").select("*").eq("vending_id", vending_id).execute()
    result = []
    for row in res.data:
        row["items"] = json.loads(row["items"]) if isinstance(row["items"], str) else row["items"]
        result.append(row)
    return result

# ────────────── 自販機データ ──────────────

def get_vending_machines(owner_id: int = None) -> list:
    import json
    db = get_db()
    query = db.table("vending_machines").select("*")
    if owner_id:
        query = query.eq("owner_id", str(owner_id))
    res = query.execute()
    result = []
    for row in res.data:
        row["custom_items"] = json.loads(row["custom_items"]) if isinstance(row["custom_items"], str) else (row["custom_items"] or [])
        result.append(row)
    return result

def get_vending_machine(vm_id: str) -> dict | None:
    import json
    db = get_db()
    res = db.table("vending_machines").select("*").eq("id", vm_id).execute()
    if not res.data:
        return None
    row = res.data[0]
    row["custom_items"] = json.loads(row["custom_items"]) if isinstance(row["custom_items"], str) else (row["custom_items"] or [])
    return row

def create_vending_machine(vm_id: str, name: str, owner_id: int) -> dict:
    import json
    db = get_db()
    db.table("vending_machines").insert({
        "id": vm_id,
        "name": name,
        "owner_id": str(owner_id),
        "role_id": None,
        "custom_items": "[]"
    }).execute()
    return get_vending_machine(vm_id)

def update_vending_machine(vm_id: str, **kwargs):
    import json
    db = get_db()
    update_data = {}
    for k, v in kwargs.items():
        if k == "custom_items" and isinstance(v, list):
            update_data[k] = json.dumps(v, ensure_ascii=False)
        else:
            update_data[k] = v
    db.table("vending_machines").update(update_data).eq("id", vm_id).execute()

# ────────────── ログチャンネル ──────────────

def get_log_channels(guild_id: int) -> dict:
    db = get_db()
    res = db.table("log_channels").select("*").eq("guild_id", str(guild_id)).execute()
    result = {}
    for row in res.data:
        result[row["channel_type"]] = int(row["channel_id"])
    return result

def set_log_channel(guild_id: int, channel_type: str, channel_id: int):
    db = get_db()
    db.table("log_channels").upsert({
        "guild_id": str(guild_id),
        "channel_type": channel_type,
        "channel_id": str(channel_id)
    }, on_conflict="guild_id,channel_type").execute()

# ────────────── 権限購入設定 ──────────────

def get_permission_price() -> int:
    """権限購入価格を取得（デフォルト500円）"""
    db = get_db()
    res = db.table("settings").select("value").eq("key", "permission_price").execute()
    return int(res.data[0]["value"]) if res.data else 500

def set_permission_price(price: int):
    db = get_db()
    db.table("settings").upsert({"key": "permission_price", "value": str(price)}, on_conflict="key").execute()
