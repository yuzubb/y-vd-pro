import os
import requests
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")


def _get_headers():
    return {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json"
    }


# =========================================================
# Allowed Users
# =========================================================

def add_allowed_user(discord_id: int, granted_by=None, memo=None):
    data = {
        "discord_id": str(discord_id),
        "granted_by": str(granted_by) if granted_by else None,
        "memo": memo
    }

    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"

    try:
        res = requests.post(
            f"{URL}/rest/v1/allowed_users",
            headers=headers,
            json=data
        )

        print("===== ADD ALLOWED USER =====")
        print("status:", res.status_code)
        print("response:", res.text)
        print("data:", data)
        print("============================")

        res.raise_for_status()

        return True

    except Exception as e:
        print("ADD ALLOWED USER ERROR:", e)
        return False


def get_allowed_users():
    try:
        res = requests.get(
            f"{URL}/rest/v1/allowed_users?select=*",
            headers=_get_headers()
        )

        res.raise_for_status()

        return res.json()

    except Exception as e:
        print("GET ALLOWED USERS ERROR:", e)
        return []


def is_allowed_user(discord_id: int):
    try:
        res = requests.get(
            f"{URL}/rest/v1/allowed_users?discord_id=eq.{discord_id}&select=*",
            headers=_get_headers()
        )

        res.raise_for_status()

        data = res.json()

        return len(data) > 0

    except Exception as e:
        print("IS ALLOWED USER ERROR:", e)
        return False


# =========================================================
# Admin
# =========================================================

def is_admin(discord_id: int):
    try:
        res = requests.get(
            f"{URL}/rest/v1/admins?discord_id=eq.{discord_id}&select=*",
            headers=_get_headers()
        )

        res.raise_for_status()

        data = res.json()

        return len(data) > 0

    except Exception as e:
        print("IS ADMIN ERROR:", e)
        return False


# =========================================================
# PayPay Accounts
# =========================================================

def save_paypay_account(
    discord_user_id: int,
    phone: str,
    password: str,
    uuid: str,
    access_token: str = None
):
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

    try:
        res = requests.post(
            f"{URL}/rest/v1/paypay_accounts",
            headers=headers,
            json=data
        )

        print("===== SAVE PAYPAY ACCOUNT =====")
        print("status:", res.status_code)
        print("response:", res.text)
        print("data:", data)
        print("================================")

        res.raise_for_status()

        return True

    except Exception as e:
        print("SAVE PAYPAY ACCOUNT ERROR:", e)
        return False


def get_paypay_account(discord_user_id: int):
    try:
        res = requests.get(
            f"{URL}/rest/v1/paypay_accounts?discord_id=eq.{discord_user_id}&select=*",
            headers=_get_headers()
        )

        res.raise_for_status()

        data = res.json()

        if len(data) == 0:
            return None

        return data[0]

    except Exception as e:
        print("GET PAYPAY ACCOUNT ERROR:", e)
        return None


# =========================================================
# Vending Machines
# =========================================================

def get_all_vending_machines():
    try:
        res = requests.get(
            f"{URL}/rest/v1/vending_machines?select=*",
            headers=_get_headers()
        )

        res.raise_for_status()

        return res.json()

    except Exception as e:
        print("GET ALL VENDING MACHINES ERROR:", e)
        return []


def save_vending_machine(data: dict):
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"

    try:
        res = requests.post(
            f"{URL}/rest/v1/vending_machines",
            headers=headers,
            json=data
        )

        print("===== SAVE VENDING MACHINE =====")
        print("status:", res.status_code)
        print("response:", res.text)
        print("data:", data)
        print("================================")

        res.raise_for_status()

        return True

    except Exception as e:
        print("SAVE VENDING MACHINE ERROR:", e)
        return False


def get_vending_machine(vending_id: str):
    try:
        res = requests.get(
            f"{URL}/rest/v1/vending_machines?id=eq.{vending_id}&select=*",
            headers=_get_headers()
        )

        res.raise_for_status()

        data = res.json()

        if len(data) == 0:
            return None

        return data[0]

    except Exception as e:
        print("GET VENDING MACHINE ERROR:", e)
        return None


# =========================================================
# Sales History
# =========================================================

def add_sales_history(data: dict):
    try:
        res = requests.post(
            f"{URL}/rest/v1/sales_history",
            headers=_get_headers(),
            json=data
        )

        print("===== SALES HISTORY =====")
        print("status:", res.status_code)
        print("response:", res.text)
        print("=========================")

        res.raise_for_status()

        return True

    except Exception as e:
        print("ADD SALES HISTORY ERROR:", e)
        return False


# =========================================================
# Settings
# =========================================================

def get_setting(key: str):
    try:
        res = requests.get(
            f"{URL}/rest/v1/settings?key=eq.{key}&select=*",
            headers=_get_headers()
        )

        res.raise_for_status()

        data = res.json()

        if len(data) == 0:
            return None

        return data[0]["value"]

    except Exception as e:
        print("GET SETTING ERROR:", e)
        return None


def set_setting(key: str, value: str):
    headers = _get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"

    data = {
        "key": key,
        "value": value
    }

    try:
        res = requests.post(
            f"{URL}/rest/v1/settings",
            headers=headers,
            json=data
        )

        print("===== SET SETTING =====")
        print("status:", res.status_code)
        print("response:", res.text)
        print("=======================")

        res.raise_for_status()

        return True

    except Exception as e:
        print("SET SETTING ERROR:", e)
        return False
