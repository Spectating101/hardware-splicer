-- Circuit.AI SQLite Database Schema
-- Compatible with current configuration: sqlite:///./data/circuit_ai.db

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    subscription_plan VARCHAR(50) DEFAULT 'free',
    stripe_customer_id VARCHAR(255),
    metadata TEXT DEFAULT '{}',
    CHECK (is_active IN (0, 1))
);

-- API Keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    CHECK (is_active IN (0, 1))
);

-- Analysis results table
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    analysis_id VARCHAR(255) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    file_hash VARCHAR(255),
    processing_time FLOAT NOT NULL,
    components_detected INTEGER DEFAULT 0,
    backend_used VARCHAR(50) NOT NULL,
    ocr_enabled BOOLEAN DEFAULT 0,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    results TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}',
    CHECK (ocr_enabled IN (0, 1)),
    CHECK (success IN (0, 1))
);

-- Components table
CREATE TABLE IF NOT EXISTS components (
    id TEXT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100) NOT NULL,
    value VARCHAR(100),
    package VARCHAR(100),
    description TEXT,
    datasheet_url TEXT,
    specifications TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    CHECK (is_active IN (0, 1))
);

-- Component detections table (for analysis results)
CREATE TABLE IF NOT EXISTS component_detections (
    id TEXT PRIMARY KEY,
    analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    component_type VARCHAR(255) NOT NULL,
    confidence REAL NOT NULL,
    bbox_x1 REAL NOT NULL,
    bbox_y1 REAL NOT NULL,
    bbox_x2 REAL NOT NULL,
    bbox_y2 REAL NOT NULL,
    center_x REAL,
    center_y REAL,
    area REAL,
    aspect_ratio REAL,
    value TEXT,
    package_type VARCHAR(100),
    ocr_text TEXT,
    part_number TEXT,
    market_value REAL,
    educational_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}',
    CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

-- Usage tracking table
CREATE TABLE IF NOT EXISTS usage_tracking (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    api_key_id TEXT REFERENCES api_keys(id) ON DELETE SET NULL,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_time FLOAT NOT NULL,
    request_size INTEGER,
    response_size INTEGER,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}'
);

-- Billing events table
CREATE TABLE IF NOT EXISTS billing_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_event_id VARCHAR(255) UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    amount DECIMAL(10,2),
    currency VARCHAR(3),
    plan VARCHAR(50),
    status VARCHAR(50),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}'
);

-- Projects table (for educational use cases)
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    difficulty_level VARCHAR(50),
    components TEXT DEFAULT '[]',
    instructions TEXT DEFAULT '{}',
    is_public BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}',
    CHECK (is_public IN (0, 1))
);

-- Repair procedures table
CREATE TABLE IF NOT EXISTS repair_procedures (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    device_type VARCHAR(255) NOT NULL,
    symptoms TEXT NOT NULL,
    diagnosis TEXT,
    steps TEXT NOT NULL,
    estimated_difficulty VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata TEXT DEFAULT '{}'
);

-- Audit log table (for security/compliance)
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id TEXT,
    changes TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}'
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer_id ON users(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active);
CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_analyses_analysis_id ON analyses(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at);
CREATE INDEX IF NOT EXISTS idx_analyses_success ON analyses(success);
CREATE INDEX IF NOT EXISTS idx_components_name ON components(name);
CREATE INDEX IF NOT EXISTS idx_components_category ON components(category);
CREATE INDEX IF NOT EXISTS idx_component_detections_analysis_id ON component_detections(analysis_id);
CREATE INDEX IF NOT EXISTS idx_component_detections_confidence ON component_detections(confidence);
CREATE INDEX IF NOT EXISTS idx_usage_tracking_user_id ON usage_tracking(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_tracking_created_at ON usage_tracking(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_tracking_endpoint ON usage_tracking(endpoint);
CREATE INDEX IF NOT EXISTS idx_billing_events_user_id ON billing_events(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_events_stripe_event_id ON billing_events(stripe_event_id);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_category ON projects(category);
CREATE INDEX IF NOT EXISTS idx_projects_is_public ON projects(is_public);
CREATE INDEX IF NOT EXISTS idx_repair_procedures_user_id ON repair_procedures(user_id);
CREATE INDEX IF NOT EXISTS idx_repair_procedures_device_type ON repair_procedures(device_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_type ON audit_logs(resource_type);

-- Insert default components
INSERT OR IGNORE INTO components (id, name, category, value, package, description) VALUES
('comp_resistor', 'Resistor', 'Passive', '1kΩ', '0805', 'Standard surface mount resistor'),
('comp_capacitor', 'Capacitor', 'Passive', '100nF', '0805', 'Ceramic capacitor'),
('comp_led', 'LED', 'Optoelectronics', 'Red', '0805', 'Light emitting diode'),
('comp_transistor', 'Transistor', 'Active', '2N3904', 'TO-92', 'NPN bipolar junction transistor'),
('comp_ic', 'IC', 'Integrated Circuit', 'LM358', 'DIP-8', 'Dual operational amplifier'),
('comp_crystal', 'Crystal', 'Passive', '16MHz', 'HC49', 'Quartz crystal oscillator'),
('comp_connector', 'Connector', 'Mechanical', 'USB-A', 'Through-hole', 'USB Type-A connector'),
('comp_switch', 'Switch', 'Mechanical', 'SPST', 'Through-hole', 'Single pole single throw switch');
