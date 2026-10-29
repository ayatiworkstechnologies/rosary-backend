-- ============================================================================
-- rosary_portal_test - isolated MySQL test database setup
-- ============================================================================
--
-- PURPOSE
--   One-time setup script for a dedicated, fully isolated MySQL test
--   database used by the Rosary backend automated test suite.
--
--   It must be executed by an authorized database administrator
--   (e.g. MySQL root) on the Cloud2 server (89.167.92.220).
--
-- SAFETY
--   * Touches ONLY the new database `rosary_portal_test`.
--   * Does NOT modify `rosary_portal` (production) in any way.
--   * Does NOT change the existing `rosary_user` account or its grants.
--   * The test user is restricted to @'localhost' so it can never be
--     used for a remote connection.
--
-- BEFORE RUNNING
--   Replace CHANGE_ME_STRONG_PASSWORD with a strong unique password.
--   Do not reuse any existing password and do not commit it anywhere.
--
-- USAGE
--   mysql -u root -p < scripts/sql/rosary_portal_test_setup.sql
--   (or paste the blocks one by one)
--
-- ============================================================================

-- ---------------------------------------------------------------
-- 1. Create the isolated test database (same charset as prod)
-- ---------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS rosary_portal_test
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 2. Dedicated test user, localhost-only
-- ---------------------------------------------------------------
CREATE USER IF NOT EXISTS 'rosary_test_user'@'localhost'
  IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';

-- ---------------------------------------------------------------
-- 3. Minimum required privileges, scoped to the test DB only
--    (schema creation, migrations, and test CRUD - nothing else)
-- ---------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX,
      REFERENCES, CREATE TEMPORARY TABLES, LOCK TABLES
  ON rosary_portal_test.* TO 'rosary_test_user'@'localhost';

FLUSH PRIVILEGES;

-- ---------------------------------------------------------------
-- 4. Verification (run as root and inspect the output)
-- ---------------------------------------------------------------
-- 4a. The only grants must be USAGE on *.* and ALL/limited on
--     rosary_portal_test. `rosary_portal` must NOT appear.
SHOW GRANTS FOR 'rosary_test_user'@'localhost';

-- 4b. Confirm the user cannot see production data:
--     this must return an error (ACCESS DENIED) when run as
--     rosary_test_user:
--       mysql -u rosary_test_user -p -e "USE rosary_portal;"
--     and these must succeed:
--       mysql -u rosary_test_user -p -e "USE rosary_portal_test; SELECT DATABASE();"
--       mysql -u rosary_test_user -p -e "CREATE TABLE rosary_portal_test._probe(id INT); DROP TABLE rosary_portal_test._probe;"

-- ---------------------------------------------------------------
-- 5. Handover note for the test runner
-- ---------------------------------------------------------------
-- After executing this script, create a root-owned env file that the
-- backend test runner can load (password stays private to the DBA):
--
--   sudo install -o devteam -g devteam -m 600 /dev/null \
--        /var/www/rosary-backend-releases/rosary_portal_test.env
--   sudo sh -c 'cat > /var/www/rosary-backend-releases/rosary_portal_test.env <<EOF
-- DATABASE_URL=mysql+pymysql://rosary_test_user:CHANGE_ME_STRONG_PASSWORD@localhost:3306/rosary_portal_test?charset=utf8mb4
-- SECRET_KEY=<64-random-chars-TEST-ONLY>
-- ALGORITHM=HS256
-- EOF'
--   sudo chown devteam:devteam /var/www/rosary-backend-releases/rosary_portal_test.env
--   sudo chmod 600 /var/www/rosary-backend-releases/rosary_portal_test.env
--
-- SECRET_KEY must be freshly generated (openssl rand -base64 48) and
-- must be DIFFERENT from the production SECRET_KEY.
--
-- The test suite refuses to run against any MySQL database other than
-- rosary_portal_test (hard guard in tests/_env.py).
--
-- TEARDOWN (any time, also DBA-run):
--   DROP DATABASE IF EXISTS rosary_portal_test;
--   DROP USER 'rosary_test_user'@'localhost';
