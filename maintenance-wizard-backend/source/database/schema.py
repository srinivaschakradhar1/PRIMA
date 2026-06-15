"""SQL DDL statements for all application tables.

No foreign key constraints are defined, as specified in the technical
design document.
"""

CREATE_PLANT_TABLE = """
CREATE TABLE IF NOT EXISTS plant (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    description TEXT,
    created_at DATETIME,
    updated_at DATETIME
);
"""

CREATE_EQUIPMENT_TABLE = """
CREATE TABLE IF NOT EXISTS equipment (
    id TEXT PRIMARY KEY,
    plant_id TEXT,
    equipment_code TEXT UNIQUE,
    equipment_name TEXT,
    equipment_type TEXT,
    manufacturer TEXT,
    model_number TEXT,
    installation_date DATE,
    expected_life_days INTEGER,
    criticality TEXT,
    location_in_plant TEXT,
    status TEXT,
    created_at DATETIME,
    updated_at DATETIME
);
"""

CREATE_SENSOR_TABLE = """
CREATE TABLE IF NOT EXISTS sensor (
    id TEXT PRIMARY KEY,
    sensor_code TEXT UNIQUE,
    equipment_id TEXT,
    sensor_name TEXT,
    sensor_type TEXT,
    unit TEXT,
    min_threshold REAL,
    max_threshold REAL,
    warning_threshold REAL,
    critical_threshold REAL,
    created_at DATETIME
);
"""

CREATE_SENSOR_READING_TABLE = """
CREATE TABLE IF NOT EXISTS sensor_reading (
    id TEXT PRIMARY KEY,
    equipment_id TEXT,
    sensor_id TEXT,
    sensor_code TEXT,
    value REAL,
    reading_timestamp DATETIME,
    ingestion_timestamp DATETIME
);
"""

CREATE_SENSOR_READING_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_sr_eq ON sensor_reading(equipment_id);
CREATE INDEX IF NOT EXISTS idx_sr_time ON sensor_reading(reading_timestamp);
"""

CREATE_EQUIPMENT_HEALTH_RECORD_TABLE = """
CREATE TABLE IF NOT EXISTS equipment_health_record (
    id TEXT PRIMARY KEY,
    equipment_id TEXT,
    health_score INTEGER,
    risk_level TEXT,
    rul_days INTEGER,
    failure_probability REAL,
    predicted_failure TEXT,
    preventive_actions_json TEXT,
    expected_end_of_life_date DATE,
    is_active BOOLEAN,
    generated_at DATETIME
);
"""

CREATE_KNOWLEDGE_DOCUMENT_TABLE = """
CREATE TABLE IF NOT EXISTS knowledge_document (
    id TEXT PRIMARY KEY,
    equipment_id TEXT,
    document_name TEXT,
    document_type TEXT,
    file_path TEXT,
    file_hash TEXT,
    uploaded_at DATETIME
);
"""

CREATE_KNOWLEDGE_CHUNK_TABLE = """
CREATE TABLE IF NOT EXISTS knowledge_chunk (
    chunk_id TEXT PRIMARY KEY,
    parent_chunk_id TEXT,
    document_id TEXT,
    equipment_id TEXT,
    equipment_type TEXT,
    document_type TEXT,
    concept TEXT,
    semantic_type TEXT,
    page INTEGER,
    start_offset INTEGER,
    end_offset INTEGER,
    text TEXT,
    token_count INTEGER,
    is_parent BOOLEAN,
    created_at DATETIME
);
"""

CREATE_KNOWLEDGE_CHUNK_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON knowledge_chunk(document_id);
CREATE INDEX IF NOT EXISTS idx_chunk_parent ON knowledge_chunk(parent_chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunk_eq ON knowledge_chunk(equipment_id);
"""

CREATE_KNOWLEDGE_CONCEPT_TABLE = """
CREATE TABLE IF NOT EXISTS knowledge_concept (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    equipment_id TEXT,
    concept_name TEXT,
    concept_type TEXT,
    groups_json TEXT
);
"""

CREATE_KNOWLEDGE_RELATIONSHIP_TABLE = """
CREATE TABLE IF NOT EXISTS knowledge_relationship (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    equipment_id TEXT,
    source TEXT,
    relation TEXT,
    target TEXT,
    concept TEXT
);
"""

CREATE_KNOWLEDGE_RELATIONSHIP_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_rel_doc ON knowledge_relationship(document_id);
CREATE INDEX IF NOT EXISTS idx_rel_eq ON knowledge_relationship(equipment_id);
"""

CREATE_INCIDENT_RECORD_TABLE = """
CREATE TABLE IF NOT EXISTS incident_record (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    equipment_id TEXT,
    failure_mode TEXT,
    symptoms_json TEXT,
    root_cause TEXT,
    resolution TEXT,
    outcome TEXT,
    created_at DATETIME
);
"""

CREATE_MAINTENANCE_LOG_RECORD_TABLE = """
CREATE TABLE IF NOT EXISTS maintenance_log_record (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    equipment_id TEXT,
    symptom TEXT,
    action TEXT,
    result TEXT,
    created_at DATETIME
);
"""

CREATE_AGENT_SESSION_TABLE = """
CREATE TABLE IF NOT EXISTS agent_session (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    created_at DATETIME,
    last_updated_at DATETIME
);
"""

CREATE_AGENT_MEMORY_TABLE = """
CREATE TABLE IF NOT EXISTS agent_memory (
    id TEXT PRIMARY KEY,
    equipment_id TEXT,
    interaction_type TEXT,
    user_query TEXT,
    agent_response TEXT,
    outcome TEXT,
    created_at DATETIME
);
"""

# Tables that have a backing CSV in ``data/`` (plant, equipment,
# sensor_reading, equipment_health_record, and the new operational tables) are
# NOT defined here. They are (re)created dynamically at startup by
# ``startup.data_loader``, which infers their schema directly from each CSV's
# header so the table always matches the file. Only tables with no backing CSV
# are declared statically below.
ALL_TABLES_SCRIPT = "\n".join(
    [
        CREATE_SENSOR_TABLE,
        CREATE_KNOWLEDGE_DOCUMENT_TABLE,
        CREATE_KNOWLEDGE_CHUNK_TABLE,
        CREATE_KNOWLEDGE_CHUNK_INDEXES,
        CREATE_KNOWLEDGE_CONCEPT_TABLE,
        CREATE_KNOWLEDGE_RELATIONSHIP_TABLE,
        CREATE_KNOWLEDGE_RELATIONSHIP_INDEXES,
        CREATE_INCIDENT_RECORD_TABLE,
        CREATE_MAINTENANCE_LOG_RECORD_TABLE,
        CREATE_AGENT_SESSION_TABLE,
        CREATE_AGENT_MEMORY_TABLE,
    ]
)
