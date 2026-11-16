#!/bin/sh
# Runs once, when the Postgres volume is first created.
# Creates the role the services use. It does not own the tables, so
# row-level security always applies to it.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
create role ${APP_DB_USER} login password '${APP_DB_PASSWORD}';
grant connect on database ${POSTGRES_DB} to ${APP_DB_USER};
grant usage on schema public to ${APP_DB_USER};
alter default privileges in schema public
  grant select, insert, update, delete on tables to ${APP_DB_USER};
SQL
