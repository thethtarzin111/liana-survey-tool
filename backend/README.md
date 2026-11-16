# Backend

Python services, shared Python packages, SQL migrations and infrastructure live here.
Requires Python 3.12+, Node.js and PostgreSQL binaries (see the root README).

From this directory:

```sh
npm install
npm run dev
```

The npm commands prepare the Python environment and start the APIs and a private
PostgreSQL database. The API is at http://localhost:8000 and survey API docs are
at http://localhost:8000/docs. Start the frontend separately from `../frontend`.
Ctrl+C stops the backend and database.

The shared development environment (`../.venv`), database (`../.local`) and
optional `.env` remain at the repository root. Existing local data is preserved.
