-- ============================================================
-- Supabase テーブル作成SQL
-- Supabase Dashboard > SQL Editor で実行してください
-- ============================================================

-- PayPayアカウント
CREATE TABLE IF NOT EXISTS paypay_accounts (
    discord_id TEXT PRIMARY KEY,
    phone TEXT NOT NULL,
    password TEXT NOT NULL,
    uuid TEXT NOT NULL,
    access_token TEXT,
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
-- products: 商品リスト(JSON配列), log_channel_id / private_log_channel_id: ログチャンネル
-- paypay_id: 紐づくPayPayアカウントのdiscord_id
CREATE TABLE IF NOT EXISTS vending_machines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    paypay_id TEXT,
    log_channel_id TEXT,
    private_log_channel_id TEXT,
    products TEXT DEFAULT '[]',
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

-- 設定
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 在庫アイテム（有限在庫の各行）
-- product_id: 商品UUID, content: 在庫の1行テキスト, sold: 販売済みフラグ
CREATE TABLE IF NOT EXISTS stock_items (
    id BIGSERIAL PRIMARY KEY,
    product_id TEXT NOT NULL,
    content TEXT NOT NULL,
    sold BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stock_items_product_id ON stock_items(product_id, sold);

-- 在庫追加通知設定
CREATE TABLE IF NOT EXISTS stock_notifications (
    vending_machine_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    guild_id TEXT NOT NULL
);

-- クーポン
CREATE TABLE IF NOT EXISTS coupons (
    coupon_code TEXT PRIMARY KEY,
    discount INTEGER NOT NULL,
    owner_id TEXT NOT NULL,
    vending_machine_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ロール付与設定
CREATE TABLE IF NOT EXISTS role_assignments (
    vending_machine_id TEXT PRIMARY KEY,
    role_id TEXT NOT NULL,
    guild_id TEXT NOT NULL
);

-- デフォルト設定
INSERT INTO settings (key, value) VALUES ('permission_price', '500')
ON CONFLICT (key) DO NOTHING;

-- ============================================================
-- Row Level Security (RLS) 無効化
-- ============================================================
ALTER TABLE paypay_accounts DISABLE ROW LEVEL SECURITY;
ALTER TABLE allowed_users DISABLE ROW LEVEL SECURITY;
ALTER TABLE admins DISABLE ROW LEVEL SECURITY;
ALTER TABLE vending_machines DISABLE ROW LEVEL SECURITY;
ALTER TABLE sales_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE log_channels DISABLE ROW LEVEL SECURITY;
ALTER TABLE settings DISABLE ROW LEVEL SECURITY;
ALTER TABLE stock_items DISABLE ROW LEVEL SECURITY;
ALTER TABLE stock_notifications DISABLE ROW LEVEL SECURITY;
ALTER TABLE coupons DISABLE ROW LEVEL SECURITY;
ALTER TABLE role_assignments DISABLE ROW LEVEL SECURITY;
