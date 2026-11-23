"""RabbitMQ queue names. One RabbitMQ instance, separate queues."""

# Respondent service -> background worker: a submitted answer to save.
ANSWERS = "survey.answers"

# Worker and survey-manager -> Liana connector (the report's integration queue):
# "Contact me" requests and their "You said, we did" replies for other Liana
# products, and "new responses" emails for survey owners.
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

# survey.liana-events is declared by the connector (reads) and the worker and
# survey-manager (publish), so all use these arguments.
LIANA_EVENTS_ARGUMENTS = ANSWERS_ARGUMENTS
