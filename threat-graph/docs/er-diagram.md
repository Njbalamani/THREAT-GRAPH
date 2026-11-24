# Entity relationship diagram

```mermaid
erDiagram
  USER ||--o{ INVESTIGATION : owns
  USER ||--o{ INVESTIGATION_NOTE : authors
  USER ||--o{ ML_MODEL_RUN : triggers
  INDICATOR ||--o{ INVESTIGATION_INDICATOR : linked_to
  INVESTIGATION ||--o{ INVESTIGATION_INDICATOR : contains
  INVESTIGATION ||--o{ INVESTIGATION_NOTE : has
  SECURITY_EVENT ||--o{ GRAPH_RELATIONSHIP : produces
  INDICATOR ||--o{ GRAPH_RELATIONSHIP : participates
  INGESTION_JOB ||--o{ SECURITY_EVENT : imports
  INGESTION_JOB ||--o{ INDICATOR : imports
  FEED_CONFIG ||--o{ INGESTION_JOB : polls

  USER {
    uuid id PK
    string email UK
    string username UK
    string full_name
    string hashed_password
    enum role
    boolean is_active
    datetime created_at
  }

  INDICATOR {
    uuid id PK
    enum type
    string value UK
    enum severity
    float confidence
    string source
    string description
    json tags
    string stix_id
    boolean is_confirmed
    datetime first_seen
    datetime last_seen
    json raw
  }

  SECURITY_EVENT {
    uuid id PK
    datetime timestamp
    string event_type
    string source
    string title
    string description
    string source_ip
    string destination_ip
    string domain
    string file_hash
    string url
    string email
    float severity_score
    json raw
    uuid ingestion_job_id FK
  }

  GRAPH_RELATIONSHIP {
    uuid id PK
    string source_key
    string target_key
    string relationship
    enum provenance
    float confidence
    float strength
    json evidence
    datetime created_at
  }

  INGESTION_JOB {
    uuid id PK
    string source
    string file_name
    string format
    enum status
    int total_records
    int imported_indicators
    int imported_events
    int rejected_records
    json errors
    datetime created_at
    datetime completed_at
  }

  FEED_CONFIG {
    uuid id PK
    string name UK
    string description
    enum feed_type
    string url
    string collection_id
    string auth_header_env
    boolean enabled
    int poll_interval_minutes
    datetime last_polled_at
    string last_status
    string last_error
    datetime created_at
  }

  INVESTIGATION {
    uuid id PK
    string title
    string description
    enum status
    enum priority
    uuid owner_id FK
    datetime created_at
    datetime updated_at
  }

  INVESTIGATION_INDICATOR {
    uuid investigation_id FK
    uuid indicator_id FK
    datetime linked_at
  }

  INVESTIGATION_NOTE {
    uuid id PK
    uuid investigation_id FK
    uuid author_id FK
    string content
    datetime created_at
  }

  ML_MODEL_RUN {
    uuid id PK
    string version UK
    string model_type
    json metrics
    json features
    int training_samples
    string label_source
    string artifact_path
    datetime created_at
  }

Graph nodes and edges are additionally persisted in Neo4j or the NetworkX JSON store. PostgreSQL `GRAPH_RELATIONSHIP` rows provide an auditable relational record of the same graph links. Predictions are produced from persisted model artifacts and `ML_MODEL_RUN` metadata; they are advisory responses rather than confirmed database records.

