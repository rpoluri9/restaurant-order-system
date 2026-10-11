"""Polite customer-care message templates for delayed orders."""

DEFAULT_DELAY_MESSAGE = (
    "We're sorry for the wait! Your order will take 10 to 15 more minutes. "
    "Thank you for your patience."
)

CUSTOMER_RESPONSES = {"WAITING", "CANCELLED_ORDER", "ESCALATED", "NO_RESPONSE"}


def build_delay_message(custom: str | None = None) -> str:
    """Return the message customer care sends for a delayed order.

    Always polite, always honest about the wait: 10 to 15 more minutes.
    """
    if custom and custom.strip():
        return custom.strip()
    return DEFAULT_DELAY_MESSAGE
