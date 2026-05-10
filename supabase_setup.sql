-- ============================================================
-- Supabase テーブル作成SQL
-- Supabase Dashboard > SQL Editor で実行してください
-- ============================================================

-- PayPayアカウント（再起動後も保持）
CREATE TABLE IF NOT EXISTS paypay_accounts (
    discord_id TEXT PRIMARY KEY,
    phone TEXT NOT NULL,
    password TEXT NOT NULL,
    uuid TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bot使用権限を持つユーザー
CREATE TABLE IF NOT EXISTS allowed_users (
    discord_id TEXT PRIMARY KEY,
    granted_by TEXT,
    memo TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 管理者
CREATE TABLE IF NOT EXISTS admins (
    discord_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 自販機
CREATE TABLE IF NOT EXISTS vending_machines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    role_id TEXT,
    custom_items TEXT DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 販売履歴
CREATE TABLE IF NOT EXISTS sales_history (
    id BIGSERIAL PRIMARY KEY,
    vending_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT,
    items TEXT NOT NULL,
    total_price INTEGER NOT NULL,
    created_at BIGINT NOT NULL
);

-- ログチャンネル
CREATE TABLE IF NOT EXISTS log_channels (
    guild_id TEXT NOT NULL,
    channel_type TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    PRIMARY KEY (guild_id, channel_type)
);

-- 設定（権限価格など）
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- デフォルト設定
INSERT INTO settings (key, value) VALUES ('permission_price', '500')
ON CONFLICT (key) DO NOTHING;

-- ============================================================
-- Row Level Security (RLS) - 必要に応じて有効化
-- ============================================================
-- 全テーブルのRLSを無効化（Botのサービスキーのみ使用するため）
ALTER TABLE paypay_accounts DISABLE ROW LEVEL SECURITY;
ALTER TABLE allowed_users DISABLE ROW LEVEL SECURITY;
ALTER TABLE admins DISABLE ROW LEVEL SECURITY;
ALTER TABLE vending_machines DISABLE ROW LEVEL SECURITY;
ALTER TABLE sales_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE log_channels DISABLE ROW LEVEL SECURITY;
ALTER TABLE settings DISABLE ROW LEVEL SECURITY;
