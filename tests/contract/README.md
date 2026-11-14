# Contract tests (planned)

Tests that check the running API over HTTP against `docs/api/openapi.yaml`
(for example with [Schemathesis](https://schemathesis.readthedocs.io/)).

They test the contract, not the Python code, so a PHP version of the backend
can be checked with the same tests. See `docs/handoff.md`.

Later, the Liana connector also gets contract tests here: first against the
mock adapter, then against LianaAutomation staging once the test account works.
