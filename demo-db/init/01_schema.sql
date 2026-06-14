/* ============================================================
   User Management Demo - Schema (PostgreSQL)
   權限/部門查找表、使用者主檔。
   此腳本由 Postgres 在 POSTGRES_DB 資料庫中自動執行。
   ============================================================ */

-- 密碼雜湊用(crypt / gen_salt，bcrypt)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

/* ---------- 權限 (admin / write / read) ---------- */
CREATE TABLE IF NOT EXISTS roles (
    role_id     SERIAL PRIMARY KEY,
    code        VARCHAR(10)  NOT NULL UNIQUE,   -- admin / write / read
    description TEXT         NOT NULL
);

/* ---------- 部門 ---------- */
CREATE TABLE IF NOT EXISTS departments (
    department_id SERIAL PRIMARY KEY,
    name          VARCHAR(50) NOT NULL UNIQUE
);

/* ---------- 使用者主檔 ---------- */
CREATE TABLE IF NOT EXISTS users (
    user_id       SERIAL PRIMARY KEY,
    user_name     VARCHAR(50)  NOT NULL,
    email         VARCHAR(256) NOT NULL UNIQUE,           -- 登入帳號
    password_hash TEXT         NOT NULL,                  -- bcrypt 雜湊(已內含 salt)
    role_id       INT NOT NULL REFERENCES roles(role_id),
    department_id INT NOT NULL REFERENCES departments(department_id),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

/* 方便 demo 查詢的檢視:把代碼 join 成易讀文字 */
CREATE OR REPLACE VIEW v_users AS
SELECT  u.user_id,
        u.user_name,
        u.email,
        r.code      AS permission,
        d.name      AS department,
        u.is_active,
        u.created_at,
        u.last_login_at
FROM users u
JOIN roles r       ON r.role_id = u.role_id
JOIN departments d ON d.department_id = u.department_id;
