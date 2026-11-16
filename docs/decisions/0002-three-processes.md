# 0002 Three processes instead of five services

> Runtime update: see [0005 Native development](0005-native-development.md).
> Container and nginx references below describe the former deployment.

**Status:** replaced by [0004](0004-services-and-gateway.md) on 2026-11-16, so the code matches the mid-term report

## Context
The report's architecture has five backend components (survey manager,
respondent service, data analyzer, workers, Liana connector). The team has
three people. Each separate service adds its own Docker image, config, CI job,
deployment and network calls, and they all share one database.

## Decision
Run three processes:

| Process | Contains |
|---|---|
| `api` | survey manager, data analyzer and respondent endpoint, as separate modules |
| `worker` | saves answers, updates totals |
| `liana-connector` | all calls to Liana products |

## Why
- The split that matters for load is already there: the respondent endpoint
  only queues answers, and the worker saves them. That absorbs newsletter bursts.
- The connector stays separate so a Liana outage never affects the app; its
  messages wait in RabbitMQ.
- Fewer moving parts for a three-person team and for laptops.

## Consequences
- Modules inside `api` must not import each other's internals. Then any module
  can be moved into its own service later without a rewrite.
