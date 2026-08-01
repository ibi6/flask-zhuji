from __future__ import annotations

from datetime import datetime

from .extensions import db
from .models import Host, utcnow

# A host is "online" while heartbeats arrive inside the online window, "degraded"
# once heartbeats fall into the degraded window, and "offline" afterwards.
ONLINE_WINDOW_SECONDS = 300
DEGRADED_WINDOW_SECONDS = 900


def infer_status(host: Host, now: datetime | None = None) -> str:
    """Infer ``online``/``degraded``/``offline`` from the last heartbeat.

    Hosts that never reported a heartbeat keep their stored status so seeding a
    host with an explicit status remains meaningful.
    """
    if host.last_seen_at is None:
        return host.status
    now = now or utcnow()
    age_seconds = (now - host.last_seen_at).total_seconds()
    if age_seconds <= ONLINE_WINDOW_SECONDS:
        return "online"
    if age_seconds <= DEGRADED_WINDOW_SECONDS:
        return "degraded"
    return "offline"


def refresh_host_statuses(now: datetime | None = None) -> int:
    """Recalculate and persist host status from heartbeat age.

    Returns the number of hosts whose status changed.
    """
    now = now or utcnow()
    changed = 0
    for host in Host.query.all():
        inferred = infer_status(host, now)
        if host.status != inferred:
            host.status = inferred
            changed += 1
    if changed:
        db.session.commit()
    return changed
