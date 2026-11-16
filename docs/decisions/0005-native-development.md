# 0005: Native development runtime

The supported development setup uses Node.js, Python and native PostgreSQL,
started with `npm run dev` from the repository root. Frontend and backend can
also run independently from their respective directories.

The local gateway dispatches to the existing HTTP service apps in one Python
process. The worker and connector remain optional separate processes and need
a running RabbitMQ instance. Service ownership and database tenant isolation
are unchanged.

Remove the former Dockerfiles, Compose stack and container-specific nginx
configuration. CI uses native PostgreSQL and the same development launcher.
Decisions 0002, 0003 and 0004 retain historical deployment references; current
runtime instructions are in the README and deployment guide.

The local gateway supplies demo identity, not production authentication or
rate limiting. A hosted release needs an explicitly configured production
entry point, persistent database, secrets and process supervision.
