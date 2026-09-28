from datetime import date


def days_to_expiry(lease_end: date, today: date | None = None) -> int | None:
    if lease_end is None:
        return None
    today = today or date.today()
    return (lease_end - today).days


def compute_lease_status(lease_end: date, today: date | None = None) -> str:
    """Business rule (per spec):
    days_to_expiry < 0        -> Expired
    days_to_expiry <= 90      -> Expiring Soon
    otherwise                 -> Active
    """
    d = days_to_expiry(lease_end, today)
    if d is None:
        return "Unknown"
    if d < 0:
        return "Expired"
    if d <= 90:
        return "Expiring Soon"
    return "Active"
