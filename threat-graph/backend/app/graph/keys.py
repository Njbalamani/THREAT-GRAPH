import hashlib


def indicator_key(indicator_id: str) -> str:
    return f"indicator:{indicator_id}"


def event_key(event_id: str) -> str:
    return f"event:{event_id}"


def extracted_key(indicator_type: str, value: str) -> str:
    digest = hashlib.sha1(f"{indicator_type}:{value}".encode()).hexdigest()[:16]
    return f"ioc:{indicator_type}:{digest}"


def cluster_key(cluster_id: int) -> str:
    return f"cluster:{cluster_id}"
