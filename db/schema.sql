-- Circuit.AI Production Database Schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    subscription_plan VARCHAR(50) DEFAULT 'free',
    stripe_customer_id VARCHAR(255),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- API Keys table
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Analysis results table
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    analysis_id VARCHAR(255) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    file_hash VARCHAR(255),
    processing_time FLOAT NOT NULL,
    components_detected INTEGER DEFAULT 0,
    backend_used VARCHAR(50) NOT NULL,
    ocr_enabled BOOLEAN DEFAULT FALSE,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    results JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Components table
CREATE TABLE components (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    value VARCHAR(100),
    package VARCHAR(100),
    description TEXT,
    datasheet_url TEXT,
    specifications JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Usage tracking table
CREATE TABLE usage_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_time FLOAT NOT NULL,
    request_size INTEGER,
    response_size INTEGER,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Billing events table
CREATE TABLE billing_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_event_id VARCHAR(255) UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    amount DECIMAL(10,2),
    currency VARCHAR(3),
    plan VARCHAR(50),
    status VARCHAR(50),
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Projects table (for educational use cases)
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    difficulty_level VARCHAR(50),
    components JSONB DEFAULT '[]'::jsonb,
    instructions JSONB DEFAULT '{}'::jsonb,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_stripe_customer_id ON users(stripe_customer_id);
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
CREATE INDEX idx_analyses_user_id ON analyses(user_id);
CREATE INDEX idx_analyses_analysis_id ON analyses(analysis_id);
CREATE INDEX idx_analyses_created_at ON analyses(created_at);
CREATE INDEX idx_analyses_success ON analyses(success);
CREATE INDEX idx_components_name ON components(name);
CREATE INDEX idx_components_category ON components(category);
CREATE INDEX idx_usage_tracking_user_id ON usage_tracking(user_id);
CREATE INDEX idx_usage_tracking_created_at ON usage_tracking(created_at);
CREATE INDEX idx_usage_tracking_endpoint ON usage_tracking(endpoint);
CREATE INDEX idx_billing_events_user_id ON billing_events(user_id);
CREATE INDEX idx_billing_events_stripe_event_id ON billing_events(stripe_event_id);
CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_category ON projects(category);
CREATE INDEX idx_projects_is_public ON projects(is_public);

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_components_updated_at BEFORE UPDATE ON components
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Views for common queries
CREATE VIEW user_usage_summary AS
SELECT 
    u.id as user_id,
    u.email,
    u.subscription_plan,
    COUNT(DISTINCT a.id) as total_analyses,
    COUNT(DISTINCT CASE WHEN a.success THEN a.id END) as successful_analyses,
    SUM(a.components_detected) as total_components_detected,
    AVG(a.processing_time) as avg_processing_time,
    COUNT(DISTINCT ut.id) as total_api_calls,
    MAX(a.created_at) as last_analysis_at
FROM users u
LEFT JOIN analyses a ON u.id = a.user_id
LEFT JOIN usage_tracking ut ON u.id = ut.user_id
GROUP BY u.id, u.email, u.subscription_plan;

CREATE VIEW api_key_usage AS
SELECT 
    ak.id as api_key_id,
    ak.name,
    ak.user_id,
    u.email,
    ak.usage_count,
    ak.last_used_at,
    COUNT(ut.id) as total_requests,
    COUNT(CASE WHEN ut.status_code >= 200 AND ut.status_code < 300 THEN 1 END) as successful_requests,
    AVG(ut.response_time) as avg_response_time
FROM api_keys ak
JOIN users u ON ak.user_id = u.id
LEFT JOIN usage_tracking ut ON ak.id = ut.api_key_id
WHERE ak.is_active = TRUE
GROUP BY ak.id, ak.name, ak.user_id, u.email, ak.usage_count, ak.last_used_at;

-- Insert default components
INSERT INTO components (name, category, value, package, description) VALUES
('Resistor', 'Passive', '1kΩ', '0805', 'Standard surface mount resistor'),
('Capacitor', 'Passive', '100nF', '0805', 'Ceramic capacitor'),
('LED', 'Optoelectronics', 'Red', '0805', 'Light emitting diode'),
('Transistor', 'Active', '2N3904', 'TO-92', 'NPN bipolar junction transistor'),
('IC', 'Integrated Circuit', 'LM358', 'DIP-8', 'Dual operational amplifier'),
('Crystal', 'Passive', '16MHz', 'HC49', 'Quartz crystal oscillator'),
('Connector', 'Mechanical', 'USB-A', 'Through-hole', 'USB Type-A connector'),
('Switch', 'Mechanical', 'SPST', 'Through-hole', 'Single pole single throw switch');

-- Create admin user (password should be changed in production)
INSERT INTO users (email, name, subscription_plan) VALUES
('admin@circuit.ai', 'Admin User', 'enterprise');