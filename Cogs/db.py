import os
import json
import requests
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL が設定されていません")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY が設定されていません")

TIMEOUT = 15


# =========================================================
# Base
# =========================================================


def _headers(extra: dict = None):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    if extra:
        headers.update(extra)

    return headers



def _request(method: str, endpoint: str, **kwargs):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"

    try:
        response = requests.request(
            method=method,
            url=url,
            timeout=TIMEOUT,
            **kwargs
        )

        print("=" * 50)
        print(f"[{method}] {endpoint}")
        print("STATUS:", response.status_code)

        try:
            print("RESPONSE:", response.json())
        except:
            print("RESPONSE TEXT:", response.text)

        print("=" * 50)

        response.raise_for_status()

        if response.text:
            try:
                return response.json()
            except:
                return response.text

        return None

    except requests.exceptions.Timeout:
        print(f"TIMEOUT ERROR: {endpoint}")
        return None

    except requests.exceptions.HTTPError as e:
        print(f"HTTP ERROR: {e}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"REQUEST ERROR: {e}")
        return None

    except Exception as e:
        print(f"UNKNOWN ERROR: {e}")
        return None


# =========================================================
# Allowed Users
# =========================================================


def add_allowed_user(discord_id: int, granted_by=None, memo=None) -> bool:
    payload = {
        "discord_id": str(discord_id),
        "granted_by": str(granted_by) if granted_by else None,
        "memo": memo
    }

    result = _request(
        "POST",
        "allowed_users",
        headers=_headers({
            "Prefer": "resolution=merge-duplicates"
        }),
        json=payload
    )

    return result is not None



def remove_allowed_user(discord_id: int) -> bool:
    result = _request(
        "DELETE",
        f"allowed_users?discord_id=eq.{discord_id}",
        headers=_headers()
    )

    return result is not None



def is_allowed_user(discord_id: int) -> bool:
    result = _request(
        "GET",
        f"allowed_users?discord_id=eq.{discord_id}&select=*",
        headers=_headers()
    )

    if not result:
        return False

    return len(result) > 0



def get_allowed_users() -> List[dict]:
    result = _request(
        "GET",
        "allowed_users?select=*",
        headers=_headers()
    )

    return result if result else []


# =========================================================
# Admins
# =========================================================


def add_admin(discord_id: int) -> bool:
    payload = {
        "discord_id": str(discord_id)
    }

    result = _request(
        "POST",
        "admins",
        headers=_headers({
            "Prefer": "resolution=merge-duplicates"
        }),
        json=payload
    )

    return result is not None



def remove_admin(discord_id: int) -> bool:
    result = _request(
        "DELETE",
        f"admins?discord_id=eq.{discord_id}",
        headers=_headers()
    )

    return result is not None



def is_admin(discord_id: int) -> bool:
    result = _request(
        "GET",
        f"admins?discord_id=eq.{discord_id}&select=*",
        headers=_headers()
    )

    if not result:
        return False

    return len(result) > 0


# =========================================================
# PayPay Accounts
# =========================================================


def save_paypay_account(
    discord_user_id: int,
    phone: str,
    password: str,
    uuid: str,
    access_token: Optional[str] = None
) -> bool:

    payload = {
        "discord_id": str(discord_user_id),
        "phone": phone,
        "password": password,
        "uuid": uuid,
        "access_token": access_token
    }

    result = _request(
        "POST",
        "paypay_accounts",
        headers=_headers({
            "Prefer": "resolution=merge-duplicates"
        }),
        json=payload
    )

    return result is not None



def get_paypay_account(discord_user_id: int) -> Optional[dict]:
    result = _request(
        "GET",
        f"paypay_accounts?discord_id=eq.{discord_user_id}&select=*",
        headers=_headers()
    )

    if not result:
        return None

    return result[0]



def delete_paypay_account(discord_user_id: int) -> bool:
    result = _request(
        "DELETE",
        f"paypay_accounts?discord_id=eq.{discord_user_id}",
        headers=_headers()
    )

    return result is not None


# =========================================================
# Vending Machines
# =========================================================


def save_vending_machine(data: Dict[str, Any]) -> bool:
    result = _request(
        "POST",
        "vending_machines",
        headers=_headers({
            "Prefer": "resolution=merge-duplicates"
        }),
        json=data
    )

    return result is not None



def get_vending_machine(vending_id: str) -> Optional[dict]:
    result = _request(
        "GET",
        f"vending_machines?id=eq.{vending_id}&select=*",
        headers=_headers()
    )

    if not result:
        return None

    return result[0]



def delete_vending_machine(vending_id: str) -> bool:
    result = _request(
        "DELETE",
        f"vending_machines?id=eq.{vending_id}",
        headers=_headers()
    )

    return result is not None



def get_all_vending_machines() -> Dict[str, dict]:
    result = _request(
        "GET",
        "vending_machines?select=*",
        headers=_headers()
    )

    if not result:
        return {}

    vending_dict = {}

    for vm in result:
        vm_id = vm.get("id")

        if vm_id:
            vending_dict[vm_id] = vm

    return vending_dict


# =========================================================
# Sales History
# =========================================================


def add_sales_history(data: Dict[str, Any]) -> bool:
    result = _request(
        "POST",
        "sales_history",
        headers=_headers(),
        json=data
    )

    return result is not None



def get_sales_history(limit: int = 100) -> List[dict]:
    result = _request(
        "GET",
        f"sales_history?select=*&limit={limit}&order=id.desc",
        headers=_headers()
    )

    return result if result else []


# =========================================================
# Settings
# =========================================================


def set_setting(key: str, value: str) -> bool:
    payload = {
        "key": key,
        "value": value
    }

    result = _request(
        "POST",
        "settings",
        headers=_headers({
            "Prefer": "resolution=merge-duplicates"
        }),
        json=payload
    )

    return result is not None



def get_setting(key: str):
    result = _request(
        "GET",
        f"settings?key=eq.{key}&select=*",
        headers=_headers()
    )

    if not result:
        return None

    return result[0].get("value")


# =========================================================
# Stock
# =========================================================


def add_stock_item(product_id: str, content: str) -> bool:
    payload = {
        "product_id": product_id,
        "content": content,
        "sold": False
    }

    result = _request(
        "POST",
        "stock_items",
        headers=_headers(),
        json=payload
    )

    return result is not None



def get_unsold_stock(product_id: str) -> List[dict]:
    result = _request(
        "GET",
        f"stock_items?product_id=eq.{product_id}&sold=eq.false&select=*",
        headers=_headers()
    )

    return result if result else []



def mark_stock_sold(stock_id: int) -> bool:
    payload = {
        "sold": True
    }

    result = _request(
        "PATCH",
        f"stock_items?id=eq.{stock_id}",
        headers=_headers(),
        json=payload
    )

    return result is not None


# =========================================================
# Debug
# =========================================================


def health_check():
    result = _request(
        "GET",
        "settings?select=*",
        headers=_headers()
    )

    return result is not None


if __name__ == "__main__":
    print("DB HEALTH:", health_check())
