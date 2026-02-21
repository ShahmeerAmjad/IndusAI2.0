# =======================
# Prometheus Metrics
# =======================

from prometheus_client import Counter, Gauge, Histogram, REGISTRY


def safe_get_metric(name, metric_cls, *args, **kwargs):
    """Get or create a Prometheus metric, avoiding duplicate registration."""
    try:
        return metric_cls(name, *args, **kwargs)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


MESSAGES_TOTAL = safe_get_metric(
    'chatbot_messages_total',
    Counter,
    'Total messages processed',
    ['message_type', 'channel']
)

RESPONSE_TIME = safe_get_metric(
    'chatbot_response_time_seconds',
    Histogram,
    'Response time in seconds'
)

ACTIVE_SESSIONS = safe_get_metric(
    'chatbot_active_sessions',
    Gauge,
    'Number of active sessions'
)

ERROR_COUNTER = safe_get_metric(
    'chatbot_errors_total',
    Counter,
    'Total errors',
    ['error_type']
)
