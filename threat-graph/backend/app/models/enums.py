from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class IndicatorType(str, Enum):
    IP = "ip"
    DOMAIN = "domain"
    HASH = "hash"
    URL = "url"
    EMAIL = "email"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Provenance(str, Enum):
    OBSERVED = "observed"
    INFERRED = "inferred"


class InvestigationStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class JobStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FeedType(str, Enum):
    STIX = "stix"
    TAXII = "taxii"
    JSON = "json"
    CSV = "csv"
    LOG = "log"


class RelationshipType(str, Enum):
    SOURCE_IP = "source_ip_linked"
    DESTINATION_IP = "destination_ip_linked"
    COMMUNICATED_WITH = "communicated_with"
    DOMAIN_OBSERVED = "domain_observed"
    HASH_OBSERVED = "hash_observed"
    URL_OBSERVED = "url_observed"
    CONTACTED_DOMAIN = "contacted_domain"
    TRANSFERRED_HASH = "transferred_hash"
    SHARED_DOMAIN = "shared_domain"
    SHARED_HASH = "shared_hash"
    SIMILAR_BEHAVIOUR = "similar_behaviour"
    RELATED_TO = "related_to"
