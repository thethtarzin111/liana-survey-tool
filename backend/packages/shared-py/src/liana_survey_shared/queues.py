"""RabbitMQ queue names. One RabbitMQ instance, separate queues."""

# Respondent service -> background worker: a submitted answer to save.
ANSWERS = "survey.answers"

# Data analyzer -> Liana connector (the report's integration queue):
# identified answers and "Contact me" requests for other Liana products.
LIANA_EVENTS = "survey.liana-events"

# Messages that failed too many times end up here for manual checking.
DEAD_LETTER = "survey.dead-letter"

# survey.answers must be declared with the same arguments everywhere (the
# respondent service publishes to it, the worker reads it): failed messages
# go to the dead-letter queue.
ANSWERS_ARGUMENTS = {
    "x-dead-letter-exchange": "",
    "x-dead-letter-routing-key": DEAD_LETTER,
}
