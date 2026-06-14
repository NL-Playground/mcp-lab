/* ============================================================
   User Management Demo - Audit Log + Functions (PostgreSQL)
   稽核紀錄表 + 使用者管理函式(新增/停用/改權限/改密碼/登入)
   ============================================================ */

/* ---------- 操作稽核紀錄 ---------- */
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id     BIGSERIAL PRIMARY KEY,
    action       VARCHAR(30)  NOT NULL,   -- CREATE / DISABLE / ENABLE / CHANGE_ROLE / CHANGE_PASSWORD / LOGIN_SUCCESS / LOGIN_FAIL
    target_email VARCHAR(256),            -- 被操作的使用者
    performed_by VARCHAR(256),            -- 執行此操作的人(demo 可傳 admin 的 email)
    detail       TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

/* ============================================================
   fn_create_user - 新增使用者
   ============================================================ */
CREATE OR REPLACE FUNCTION fn_create_user(
    p_user_name    VARCHAR,
    p_email        VARCHAR,
    p_password     VARCHAR,
    p_role_code    VARCHAR,
    p_department   VARCHAR,
    p_performed_by VARCHAR DEFAULT NULL
) RETURNS SETOF v_users AS $$
DECLARE
    v_role_id INT;
    v_dept_id INT;
BEGIN
    IF EXISTS (SELECT 1 FROM users WHERE email = p_email) THEN
        RAISE EXCEPTION 'Email 已存在: %', p_email;
    END IF;

    SELECT role_id INTO v_role_id FROM roles WHERE code = p_role_code;
    IF v_role_id IS NULL THEN
        RAISE EXCEPTION '權限代碼無效(僅 admin/write/read): %', p_role_code;
    END IF;

    SELECT department_id INTO v_dept_id FROM departments WHERE name = p_department;
    IF v_dept_id IS NULL THEN
        RAISE EXCEPTION '部門不存在: %', p_department;
    END IF;

    INSERT INTO users (user_name, email, password_hash, role_id, department_id)
    VALUES (p_user_name, p_email, crypt(p_password, gen_salt('bf')), v_role_id, v_dept_id);

    INSERT INTO audit_log (action, target_email, performed_by, detail)
    VALUES ('CREATE', p_email, p_performed_by,
            format('role=%s, dept=%s', p_role_code, p_department));

    RETURN QUERY SELECT * FROM v_users WHERE email = p_email;
END;
$$ LANGUAGE plpgsql;

/* ============================================================
   fn_set_user_active - 停用 / 啟用使用者
   p_is_active = false 停用, true 啟用
   ============================================================ */
CREATE OR REPLACE FUNCTION fn_set_user_active(
    p_email        VARCHAR,
    p_is_active    BOOLEAN,
    p_performed_by VARCHAR DEFAULT NULL
) RETURNS void AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE email = p_email) THEN
        RAISE EXCEPTION '使用者不存在: %', p_email;
    END IF;

    UPDATE users SET is_active = p_is_active WHERE email = p_email;

    INSERT INTO audit_log (action, target_email, performed_by)
    VALUES (CASE WHEN p_is_active THEN 'ENABLE' ELSE 'DISABLE' END, p_email, p_performed_by);
END;
$$ LANGUAGE plpgsql;

/* ============================================================
   fn_change_user_role - 變更使用者權限
   ============================================================ */
CREATE OR REPLACE FUNCTION fn_change_user_role(
    p_email        VARCHAR,
    p_role_code    VARCHAR,
    p_performed_by VARCHAR DEFAULT NULL
) RETURNS void AS $$
DECLARE
    v_role_id INT;
BEGIN
    SELECT role_id INTO v_role_id FROM roles WHERE code = p_role_code;
    IF v_role_id IS NULL THEN
        RAISE EXCEPTION '權限代碼無效(僅 admin/write/read): %', p_role_code;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM users WHERE email = p_email) THEN
        RAISE EXCEPTION '使用者不存在: %', p_email;
    END IF;

    UPDATE users SET role_id = v_role_id WHERE email = p_email;

    INSERT INTO audit_log (action, target_email, performed_by, detail)
    VALUES ('CHANGE_ROLE', p_email, p_performed_by, format('new_role=%s', p_role_code));
END;
$$ LANGUAGE plpgsql;

/* ============================================================
   fn_change_password - 變更密碼(重新產生 bcrypt 雜湊)
   ============================================================ */
CREATE OR REPLACE FUNCTION fn_change_password(
    p_email        VARCHAR,
    p_new_password VARCHAR,
    p_performed_by VARCHAR DEFAULT NULL
) RETURNS void AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE email = p_email) THEN
        RAISE EXCEPTION '使用者不存在: %', p_email;
    END IF;

    UPDATE users SET password_hash = crypt(p_new_password, gen_salt('bf')) WHERE email = p_email;

    INSERT INTO audit_log (action, target_email, performed_by)
    VALUES ('CHANGE_PASSWORD', p_email, p_performed_by);
END;
$$ LANGUAGE plpgsql;

/* ============================================================
   fn_verify_login - 登入驗證
   回傳 login_ok(t/f)+ permission + department
   同時寫稽核並更新 last_login_at
   ============================================================ */
CREATE OR REPLACE FUNCTION fn_verify_login(
    p_email    VARCHAR,
    p_password VARCHAR
) RETURNS TABLE(login_ok BOOLEAN, permission TEXT, department TEXT) AS $$
DECLARE
    v_user_id INT;
    v_active  BOOLEAN;
    v_ok      BOOLEAN := FALSE;
    v_detail  TEXT;
BEGIN
    SELECT u.user_id,
           u.is_active,
           (u.is_active AND u.password_hash = crypt(p_password, u.password_hash))
      INTO v_user_id, v_active, v_ok
    FROM users u
    WHERE u.email = p_email;

    IF v_ok THEN
        UPDATE users SET last_login_at = now() WHERE user_id = v_user_id;
    END IF;

    v_detail := CASE WHEN v_user_id IS NULL THEN 'no such user'
                     WHEN NOT v_active     THEN 'account disabled'
                     WHEN NOT v_ok         THEN 'wrong password'
                     ELSE NULL END;

    INSERT INTO audit_log (action, target_email, performed_by, detail)
    VALUES (CASE WHEN v_ok THEN 'LOGIN_SUCCESS' ELSE 'LOGIN_FAIL' END,
            p_email, p_email, v_detail);

    RETURN QUERY
        SELECT COALESCE(v_ok, FALSE),
               (SELECT vu.permission::TEXT FROM v_users vu WHERE vu.user_id = v_user_id),
               (SELECT vu.department::TEXT FROM v_users vu WHERE vu.user_id = v_user_id);
END;
$$ LANGUAGE plpgsql;
