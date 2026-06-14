/* ============================================================
   User Management Demo - Seed Data (PostgreSQL)
   權限、部門、示範使用者(密碼以 bcrypt 雜湊儲存)
   ============================================================ */

/* ---------- 權限 ---------- */
INSERT INTO roles (code, description) VALUES
    ('admin', '系統管理員:可讀、可寫、可管理使用者'),
    ('write', '編輯者:可讀、可寫'),
    ('read',  '檢視者:僅可讀')
ON CONFLICT (code) DO NOTHING;

/* ---------- 部門 ---------- */
INSERT INTO departments (name) VALUES
    ('IT'), ('Sales'), ('HR'), ('Finance')
ON CONFLICT (name) DO NOTHING;

/* ---------- 使用者 ----------
   明碼僅用於 demo 種子,插入時即以 crypt(pwd, gen_salt('bf')) 轉成 bcrypt,
   資料庫中不存明碼。所有示範帳號的預設密碼見下方 pwd 欄位。
*/
INSERT INTO users (user_name, email, password_hash, role_id, department_id)
SELECT  s.user_name,
        s.email,
        crypt(s.pwd, gen_salt('bf')),
        r.role_id,
        d.department_id
FROM (
    VALUES
        ('Alice Chen', 'alice@demo.local', 'Admin@123', 'admin', 'IT'),
        ('Bob Wang',   'bob@demo.local',   'Write@123', 'write', 'Sales'),
        ('Carol Lin',  'carol@demo.local', 'Read@123',  'read',  'HR'),
        ('David Wu',   'david@demo.local', 'Write@123', 'write', 'Finance'),
        ('Eve Huang',  'eve@demo.local',   'Read@123',  'read',  'Sales')
) AS s(user_name, email, pwd, role_code, dept)
JOIN roles r       ON r.code = s.role_code
JOIN departments d ON d.name = s.dept
ON CONFLICT (email) DO NOTHING;
