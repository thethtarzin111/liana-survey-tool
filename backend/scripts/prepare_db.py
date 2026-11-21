"""Prepare a hosted database the same way `npm run dev` prepares the local one:
create the `survey` database and the restricted `survey_app` role if missing,
apply new migrations, grant the app role its rights, and load the demo data.

Used by the demo deployment (backend/infra/deploy/deploy.sh). Reads:
  OWNER_DATABASE_URL  a role that may create databases and roles and bypasses
                      row-level security (it owns the tables and loads the seed),
                      connected to the `postgres` database
  APP_DB_PASSWORD     password for the `survey_app` role the services use

Run from the repository root: python -m backend.scripts.prepare_db
"""

import os
import sys

from backend.scripts.local_dev import prepare_database


def main() -> None:
    try:
        owner_url = os.environ["OWNER_DATABASE_URL"]
        app_password = os.environ["APP_DB_PASSWORD"]
    except KeyError as missing:
        sys.exit(f"Set {missing.args[0]} (see backend/infra/deploy/README.md).")
    prepare_database(owner_url, app_password)
    print("Database ready: migrations applied, demo data loaded.")


if __name__ == "__main__":
    main()
