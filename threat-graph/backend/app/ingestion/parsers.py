from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.models.enums import IndicatorType, Severity

IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}\b")
HASH_RE = re.compile(r"\b(?:[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64})\b")
URL_RE = re.compile(r"\bhttps?://[^\s\"'<>]+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
STIX_ASSIGNMENT_RE = re.compile(r"([A-Za-z0-9:_\.'-]+)\s*=\s*'([^']+)'")


@dataclass
class ParseResult:
    format: str
    records: list[dict[str, Any]] = field(default_factory=list)
    indicators: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class NormalizedRecord:
    raw: dict[str, Any]
    external_id: str
    timestamp: datetime
    event_type: str
    source_ip: str | None
    destination_ip: str | None
    domain: str | None
    file_hash: str | None
    url: str | None
    severity: Severity
    title: str
    description: str | None
    indicators: list[dict[str, Any]] = field(default_factory=list)


def valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def valid_domain(value: str) -> bool:
    value = value.strip().rstrip(".")
    if not 3 <= len(value) <= 253 or ".." in value:
        return False
    return bool(DOMAIN_RE.fullmatch(value))


def valid_hash(value: str) -> bool:
    return bool(re.fullmatch(r"[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", value))


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def extract_iocs(text: str) -> dict[str, list[str]]:
    urls = dedupe(URL_RE.findall(text))
    without_urls = URL_RE.sub(" ", text)
    ips = dedupe([value for value in IPV4_RE.findall(without_urls) if valid_ip(value)])
    hashes = dedupe(HASH_RE.findall(without_urls))
    without_hashes = HASH_RE.sub(" ", without_urls)
    url_hosts = []
    for url in urls:
        hostname = urlparse(url if "://" in url else f"https://{url}").hostname
        if hostname:
            url_hosts.append(hostname)
    domains = dedupe(
        [value.rstrip(".") for value in [*url_hosts, *DOMAIN_RE.findall(without_hashes)] if valid_domain(value) and not valid_ip(value)]
    )
    emails = dedupe(EMAIL_RE.findall(without_hashes))
    return {
        "ip": ips,
        "domain": domains,
        "hash": hashes,
        "url": urls,
        "email": emails,
    }


def parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is None else value.astimezone(UTC).replace(tzinfo=None)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC).replace(tzinfo=None)
    if isinstance(value, str):
        cleaned = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
            return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            pass
    return datetime.now(UTC).replace(tzinfo=None)


def parse_severity(value: Any) -> Severity:
    if isinstance(value, Severity):
        return value
    normalized = str(value or "").strip().lower()
    aliases = {
        "1": Severity.LOW,
        "2": Severity.MEDIUM,
        "3": Severity.HIGH,
        "4": Severity.CRITICAL,
        "critical": Severity.CRITICAL,
        "high": Severity.HIGH,
        "medium": Severity.MEDIUM,
        "moderate": Severity.MEDIUM,
        "low": Severity.LOW,
        "info": Severity.LOW,
        "informational": Severity.LOW,
    }
    return aliases.get(normalized, Severity.MEDIUM)


def _first(record: dict[str, Any], *keys: str) -> Any:
    lowered = {str(k).lower(): v for k, v in record.items()}
    for key in keys:
        if key.lower() in lowered and lowered[key.lower()] not in (None, ""):
            return lowered[key.lower()]
    return None


def _indicator_dict(indicator_type: IndicatorType, value: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": indicator_type,
        "value": value.strip().lower(),
        "severity": Severity.MEDIUM,
        "confidence": 0.8,
        "source": "import",
        "tags": [],
        "is_confirmed": False,
    }
    payload.update(extra)
    return payload


def clean_candidate(value: Any, indicator_type: IndicatorType) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip()
    if indicator_type == IndicatorType.IP and not valid_ip(normalized):
        return None
    if indicator_type == IndicatorType.DOMAIN and not valid_domain(normalized):
        return None
    if indicator_type == IndicatorType.HASH and not valid_hash(normalized):
        return None
    if indicator_type == IndicatorType.IP:
        return normalized.lower()
    if indicator_type in {IndicatorType.DOMAIN, IndicatorType.HASH}:
        return normalized.lower()
    return normalized


def normalize_record(record: dict[str, Any], source: str) -> NormalizedRecord:
    raw = dict(record)
    text_blob = " ".join(str(value) for value in record.values() if value not in (None, ""))
    extracted = extract_iocs(text_blob)

    source_ip = _first(record, "source_ip", "src_ip", "src", "sourceAddress", "client_ip")
    destination_ip = _first(record, "destination_ip", "dst_ip", "dst", "destinationAddress", "server_ip")
    domain = _first(record, "domain", "dns_domain", "hostname", "host", "query")
    file_hash = _first(record, "file_hash", "hash", "sha256", "md5", "fileHash")
    url = _first(record, "url", "uri", "request_url")
    severity = parse_severity(_first(record, "severity", "priority", "risk", "level"))
    event_type = str(_first(record, "event_type", "type", "category", "action") or "security_event")
    title = str(_first(record, "title", "name", "rule", "event_name") or event_type.replace("_", " ").title())
    description = _first(record, "description", "message", "details", "summary")

    source_ip = clean_candidate(source_ip, IndicatorType.IP)
    destination_ip = clean_candidate(destination_ip, IndicatorType.IP)
    domain = clean_candidate(domain, IndicatorType.DOMAIN)
    file_hash = clean_candidate(file_hash, IndicatorType.HASH)
    url = clean_candidate(url, IndicatorType.URL)

    if not source_ip and extracted["ip"]:
        source_ip = extracted["ip"][0]
    if not domain and extracted["domain"]:
        domain = extracted["domain"][0]
    if not file_hash and extracted["hash"]:
        file_hash = extracted["hash"][0]
    if not url and extracted["url"]:
        url = extracted["url"][0]

    indicators: list[dict[str, Any]] = []
    for indicator_type, value in [
        (IndicatorType.IP, source_ip),
        (IndicatorType.IP, destination_ip),
        (IndicatorType.DOMAIN, domain),
        (IndicatorType.HASH, file_hash),
        (IndicatorType.URL, url),
        *[(IndicatorType.EMAIL, value) for value in extracted["email"]],
    ]:
        if value:
            indicators.append(_indicator_dict(indicator_type, str(value), severity=severity, source=source))

    external_id = str(
        _first(record, "id", "event_id", "external_id", "uuid")
        or hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:32]
    )

    return NormalizedRecord(
        raw=raw,
        external_id=external_id,
        timestamp=parse_timestamp(_first(record, "timestamp", "event_time", "time", "date")),
        event_type=event_type,
        source_ip=str(source_ip).strip().lower() if source_ip else None,
        destination_ip=str(destination_ip).strip().lower() if destination_ip else None,
        domain=str(domain).strip().lower() if domain else None,
        file_hash=str(file_hash).strip().lower() if file_hash else None,
        url=str(url) if url else None,
        severity=severity,
        title=title,
        description=str(description) if description else None,
        indicators=indicators,
    )


def parse_stix_bundle(payload: dict[str, Any]) -> ParseResult:
    result = ParseResult(format="stix")
    objects = payload.get("objects", [])
    if not isinstance(objects, list):
        result.errors.append({"message": "STIX bundle objects must be a list"})
        return result

    for obj in objects:
        if not isinstance(obj, dict):
            result.errors.append({"message": "Skipped non-object STIX entry"})
            continue
        obj_type = obj.get("type")
        source = f"stix:{obj.get('source_name', 'bundle')}"

        if obj_type == "indicator":
            pattern = str(obj.get("pattern", ""))
            labels = obj.get("labels") or []
            severity = Severity.HIGH if any("malicious" in str(label).lower() for label in labels) else Severity.MEDIUM
            confidence = max(0.0, min(1.0, float(obj.get("confidence") or 70) / 100))
            for indicator_type, value in _parse_stix_pattern(pattern):
                result.indicators.append(
                    _indicator_dict(
                        indicator_type,
                        value,
                        severity=severity,
                        confidence=confidence,
                        source=source,
                        stix_id=obj.get("id"),
                        description=obj.get("description"),
                        tags=[str(label) for label in labels],
                        is_confirmed=any(str(label).lower() == "confirmed" for label in labels),
                        raw=obj,
                    )
                )
        elif obj_type == "observed-data":
            observables = obj.get("objects") or {}
            fields: dict[str, Any] = {}
            for observable in observables.values():
                if not isinstance(observable, dict):
                    continue
                observable_type = observable.get("type")
                if observable_type in {"ipv4-addr", "ipv6-addr"}:
                    if "source_ip" not in fields:
                        fields["source_ip"] = observable.get("value")
                    elif "destination_ip" not in fields:
                        fields["destination_ip"] = observable.get("value")
                elif observable_type == "domain-name":
                    fields["domain"] = observable.get("value")
                elif observable_type == "url":
                    fields["url"] = observable.get("value")
                elif observable_type == "file":
                    hashes = observable.get("hashes") or {}
                    fields["file_hash"] = hashes.get("SHA-256") or hashes.get("MD5") or hashes.get("SHA-1")
            record = {
                "id": obj.get("id"),
                "timestamp": obj.get("first_observed") or obj.get("last_observed"),
                "event_type": "stix_observed_data",
                "source": source,
                "title": "STIX observed data",
                "description": obj.get("description"),
                **fields,
            }
            result.records.append(record)

    return result


def _parse_stix_pattern(pattern: str) -> list[tuple[IndicatorType, str]]:
    values: list[tuple[IndicatorType, str]] = []
    cleaned_pattern = pattern.replace("[", " ").replace("]", " ")
    for key, value in STIX_ASSIGNMENT_RE.findall(cleaned_pattern):
        normalized_key = key.strip("'\"").lower().replace("'", "")
        normalized_value = value.strip()
        if "ipv4-addr" in normalized_key or "ipv6-addr" in normalized_key:
            if valid_ip(normalized_value):
                values.append((IndicatorType.IP, normalized_value))
        elif "domain-name" in normalized_key and valid_domain(normalized_value):
            values.append((IndicatorType.DOMAIN, normalized_value))
        elif "sha-256" in normalized_key or "sha-1" in normalized_key or "md5" in normalized_key:
            if valid_hash(normalized_value):
                values.append((IndicatorType.HASH, normalized_value))
        elif normalized_key.endswith("url:value") or normalized_key == "url":
            values.append((IndicatorType.URL, normalized_value))
        elif "email-addr" in normalized_key and EMAIL_RE.fullmatch(normalized_value):
            values.append((IndicatorType.EMAIL, normalized_value))
    return dedupe_indicators(values)


def dedupe_indicators(values: list[tuple[IndicatorType, str]]) -> list[tuple[IndicatorType, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[tuple[IndicatorType, str]] = []
    for indicator_type, value in values:
        key = (indicator_type.value, value.lower())
        if key not in seen:
            seen.add(key)
            result.append((indicator_type, value))
    return result


def parse_content(content: bytes, filename: str | None = None) -> ParseResult:
    suffix = (filename or "").lower().rsplit(".", 1)[-1] if filename else ""
    text = content.decode("utf-8-sig", errors="replace")

    if suffix in {"json", "stix", "stix2", "taxii"} or text.lstrip().startswith(("{", "[")):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return ParseResult(format="json", errors=[{"message": f"Invalid JSON: {exc}"}])
        if isinstance(payload, dict) and payload.get("type") == "bundle":
            return parse_stix_bundle(payload)
        if isinstance(payload, dict):
            records = payload.get("records") or payload.get("events") or [payload]
            return ParseResult(format="json", records=[item for item in records if isinstance(item, dict)])
        return ParseResult(format="json", records=[item for item in payload if isinstance(item, dict)])

    if suffix == "csv":
        try:
            reader = csv.DictReader(io.StringIO(text))
            return ParseResult(format="csv", records=[dict(row) for row in reader])
        except csv.Error as exc:
            return ParseResult(format="csv", errors=[{"message": f"Invalid CSV: {exc}"}])

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return ParseResult(
        format="log",
        records=[{"id": f"line-{index + 1}", "raw": line, "message": line} for index, line in enumerate(lines)],
    )
