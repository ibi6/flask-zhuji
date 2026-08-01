from __future__ import annotations

from typing import Any

from .extensions import db
from .models import (
    Alert,
    AlertTransition,
    DetectionRule,
    Host,
    ListeningPortSnapshot,
    MetricSample,
    ProcessSnapshot,
    SecurityEvent,
    utcnow,
)
from .notifications import create_deliveries_for_alert

SEVERITY_LEVELS = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def run_rule_evaluation(
    host_id: str | None = None, batch_id: str | None = None
) -> list[str]:
    """Match persisted telemetry against enabled rules and create/refresh alerts.

    Returns the ids of newly created alerts. Deduplication suppresses new alerts
    when the same ``host + rule`` already has an open/investigating alert.
    """
    rules = DetectionRule.query.filter_by(enabled=True).all()
    if not rules:
        return []

    created: list[str] = []
    if batch_id is not None:
        if host_id is not None and db.session.get(Host, host_id) is None:
            return created
        created = _evaluate_batch(host_id, batch_id, rules)
        db.session.commit()
        return created

    batch_query = db.session.query(
        MetricSample.host_id, MetricSample.batch_id
    )
    if host_id is not None:
        if db.session.get(Host, host_id) is None:
            return created
        batch_query = batch_query.filter_by(host_id=host_id)
    batch_query = batch_query.distinct()

    for row_host_id, row_batch_id in batch_query.all():
        created += _evaluate_batch(row_host_id, row_batch_id, rules)
    db.session.commit()
    return created


def _evaluate_batch(
    host_id: str | None, batch_id: str, rules: list[DetectionRule]
) -> list[str]:
    host = db.session.get(Host, host_id) if host_id is not None else None
    if host is None:
        return []

    metrics = MetricSample.query.filter_by(host_id=host.id, batch_id=batch_id).all()
    processes = ProcessSnapshot.query.filter_by(host_id=host.id, batch_id=batch_id).all()
    ports = ListeningPortSnapshot.query.filter_by(
        host_id=host.id, batch_id=batch_id
    ).all()
    events = SecurityEvent.query.filter_by(host_id=host.id, batch_id=batch_id).all()

    historical_names = {
        row[0]
        for row in db.session.query(ProcessSnapshot.name)
        .filter(ProcessSnapshot.host_id == host.id, ProcessSnapshot.batch_id != batch_id)
        .distinct()
        .all()
    }
    historical_ports = {
        (row[0], row[1])
        for row in db.session.query(
            ListeningPortSnapshot.protocol, ListeningPortSnapshot.local_port
        )
        .filter(
            ListeningPortSnapshot.host_id == host.id,
            ListeningPortSnapshot.batch_id != batch_id,
        )
        .distinct()
        .all()
    }

    created: list[str] = []
    for rule in rules:
        description = _match_rule(
            rule,
            host,
            metrics,
            processes,
            ports,
            events,
            historical_names,
            historical_ports,
        )
        if description is None:
            continue
        alert_id = _upsert_alert(rule, host, description)
        if alert_id is not None:
            created.append(alert_id)
    return created


def _match_rule(
    rule: DetectionRule,
    host: Host,
    metrics: list[MetricSample],
    processes: list[ProcessSnapshot],
    ports: list[ListeningPortSnapshot],
    events: list[SecurityEvent],
    historical_names: set[str],
    historical_ports: set[tuple[str, int]],
) -> str | None:
    """Return a description string when the rule matches, else ``None``."""
    criteria: dict[str, Any] = rule.criteria or {}
    rule_type = rule.rule_type

    if rule_type == "cpu_usage":
        threshold = float(criteria.get("threshold", 90.0))
        for metric in metrics:
            if metric.cpu_percent >= threshold:
                return (
                    f"CPU usage {metric.cpu_percent:.1f}% exceeds threshold "
                    f"{threshold:g}% on {host.hostname}"
                )

    elif rule_type == "memory_usage":
        threshold = float(criteria.get("threshold", 90.0))
        for metric in metrics:
            if metric.memory_percent >= threshold:
                return (
                    f"Memory usage {metric.memory_percent:.1f}% exceeds threshold "
                    f"{threshold:g}% on {host.hostname}"
                )

    elif rule_type == "new_process":
        watched = criteria.get("names")
        watched_set = set(watched) if isinstance(watched, list) else None
        for process in processes:
            if watched_set is not None and process.name not in watched_set:
                continue
            if process.name not in historical_names:
                return (
                    f"New process detected: {process.name} (pid {process.pid}) "
                    f"on {host.hostname}"
                )

    elif rule_type == "new_port":
        watched = criteria.get("ports")
        watched_set = set(watched) if isinstance(watched, list) else None
        for port in ports:
            if watched_set is not None and port.local_port not in watched_set:
                continue
            key = (port.protocol, port.local_port)
            if key not in historical_ports:
                return (
                    f"New listening port detected: {port.protocol}/{port.local_port} "
                    f"on {host.hostname}"
                )

    elif rule_type == "high_severity_event":
        min_severity = criteria.get("min_severity", "high")
        level = SEVERITY_LEVELS.get(min_severity, SEVERITY_LEVELS["high"])
        for event in events:
            if SEVERITY_LEVELS.get(event.severity, 0) >= level:
                return (
                    f"High severity event ({event.event_type}) on {host.hostname}: "
                    f"{event.summary}"
                )

    return None


def _upsert_alert(rule: DetectionRule, host: Host, description: str) -> str | None:
    """Create a new alert or refresh an existing open one. Returns new alert id."""
    existing = (
        Alert.query.filter_by(rule_id=rule.id, host_id=host.id)
        .filter(Alert.status.in_(["open", "investigating"]))
        .first()
    )
    if existing is not None:
        existing.last_seen_at = utcnow()
        existing.event_count += 1
        db.session.add(existing)
        return None

    alert = Alert(
        rule_id=rule.id,
        host_id=host.id,
        severity=rule.severity,
        status="open",
        title=rule.name,
        description=description,
        first_seen_at=utcnow(),
        last_seen_at=utcnow(),
        event_count=1,
    )
    db.session.add(alert)
    db.session.flush()
    db.session.add(
        AlertTransition(
            alert_id=alert.id,
            from_status="new",
            to_status="open",
            reason=f"triggered by rule '{rule.name}'",
        )
    )
    create_deliveries_for_alert(alert.id)
    return alert.id
