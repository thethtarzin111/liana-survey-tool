# RabbitMQ

One instance, separate queues. Queue names: `backend/packages/shared-py/src/liana_survey_shared/queues.py`.
Queues are declared by the services on start-up (durable, with a dead-letter queue).

Local console: http://localhost:15672 (login from `.env`).
