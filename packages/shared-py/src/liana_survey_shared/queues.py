"""RabbitMQ queue names. One RabbitMQ instance, separate queues."""

# Respondent endpoint -> worker: a submitted answer to save.
ANSWERS = "survey.answers"

# Worker -> Liana connector: events for other Liana products.
LIANA_EVENTS = "survey.liana-events"

# Messages that failed too many times end up here for manual checking.
DEAD_LETTER = "survey.dead-letter"
