-- 更新系统配置表中的名称
-- 请使用MySQL客户端或phpMyAdmin执行此SQL

-- 更新网站名称
UPDATE system_config
SET value = 'CodeSense 酷森思'
WHERE `key` = 'site_name';

-- 更新登录欢迎消息
UPDATE system_config
SET value = '欢迎登录 CodeSense 酷森思'
WHERE `key` = 'login_message';

-- 查看更新结果
SELECT * FROM system_config WHERE `key` IN ('site_name', 'login_message');
