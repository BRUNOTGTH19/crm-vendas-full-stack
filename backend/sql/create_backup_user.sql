-- Usuário MySQL dedicado ao backup (somente leitura).
--
-- Por que existe: o dump diário roda no GitHub Actions com a credencial
-- guardada no secret DATABASE_URL. Se essa credencial vazar, o dano precisa
-- ser "ler os dados", nunca "apagar ou alterar".
--
-- Como usar:
--   1. gere uma senha forte:
--        python -c "import secrets; print(secrets.token_urlsafe(24))"
--   2. substitua TROQUE-ESTA-SENHA e o nome do banco abaixo
--   3. execute com um usuário administrador do MySQL (Clever Cloud: console/CLI)
--   4. use a URL desse usuário no secret DATABASE_URL do GitHub; o Render
--      continua com o usuário da aplicação
--
-- Privilégios:
--   SELECT        lê as tabelas
--   SHOW VIEW     exporta views
--   TRIGGER       exporta triggers (mysqldump --triggers)
--   EVENT         exporta eventos (mysqldump --events)
--   SHOW_ROUTINE  exporta procedures/functions (mysqldump --routines), 8.0.20+
--   PROCESS não é necessário: o mysqldump roda com --no-tablespaces.

CREATE USER IF NOT EXISTS 'crm_backup'@'%' IDENTIFIED BY 'TROQUE-ESTA-SENHA';

GRANT SELECT, SHOW VIEW, TRIGGER, EVENT ON `crm_pwa`.* TO 'crm_backup'@'%';

-- MySQL 8.0.20+. Em versões anteriores, use:
--   GRANT SELECT ON `mysql`.`proc` TO 'crm_backup'@'%';
GRANT SHOW_ROUTINE ON *.* TO 'crm_backup'@'%';

-- Rotação da senha (o CREATE USER acima não troca a senha se o usuário já existe):
--   ALTER USER 'crm_backup'@'%' IDENTIFIED BY 'nova-senha-forte';
