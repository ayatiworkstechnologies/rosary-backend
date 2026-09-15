"""Repair the local MySQL database and application account.

The application credentials are read from ``.env``. The MySQL administrator
password is requested interactively and is never written to disk or echoed.
"""

from __future__ import annotations

import argparse
import getpass
import re
import sys
from pathlib import Path

import pymysql
from dotenv import dotenv_values
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
VALID_IDENTIFIER = re.compile(r"^[A-Za-z0-9_$]+$")


def load_database_url():
    database_url = dotenv_values(ENV_FILE).get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(f"DATABASE_URL is missing from {ENV_FILE}")

    url = make_url(database_url)
    if not url.drivername.startswith("mysql"):
        raise RuntimeError("DATABASE_URL must use a MySQL driver")
    if not url.username or url.password is None or not url.database:
        raise RuntimeError("DATABASE_URL must include a user, password, and database")
    if not VALID_IDENTIFIER.fullmatch(url.database):
        raise RuntimeError("The database name contains unsupported characters")
    return url


def repair_database(admin_user: str) -> None:
    url = load_database_url()
    host = url.host or "127.0.0.1"
    port = url.port or 3306
    admin_password = getpass.getpass(
        f"MySQL password for {admin_user}@{host}:{port}: "
    )

    connection = pymysql.connect(
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        autocommit=True,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{url.database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(
                "CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s",
                (url.username, "localhost", url.password),
            )
            cursor.execute(
                "ALTER USER %s@%s IDENTIFIED BY %s",
                (url.username, "localhost", url.password),
            )
            cursor.execute(
                f"GRANT ALL PRIVILEGES ON `{url.database}`.* TO %s@%s",
                (url.username, "localhost"),
            )
    finally:
        connection.close()

    test_connection = pymysql.connect(
        host=host,
        port=port,
        user=url.username,
        password=url.password,
        database=url.database,
    )
    test_connection.close()
    print("Database and application user repaired successfully.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair the local MySQL database and application account."
    )
    parser.add_argument(
        "--admin-user",
        default="root",
        help="MySQL administrator username (default: root)",
    )
    args = parser.parse_args()

    try:
        repair_database(args.admin_user)
    except pymysql.MySQLError as error:
        print(f"MySQL repair failed: {error}", file=sys.stderr)
        return 1
    except (RuntimeError, ValueError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
