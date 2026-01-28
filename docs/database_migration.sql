-- ==============================================================================
-- MIGRATION SCRIPT: AuditPRO V2 Features
-- ==============================================================================
-- Run this script in the Supabase SQL Editor to prepare the backend.

-- 1. Enable UUID Extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. ENHANCE SAVED QUERIES (Workflow Management)
-- Adds support for assigning users and tracking resolution status/history
ALTER TABLE saved_queries 
ADD COLUMN IF NOT EXISTS assigned_to UUID REFERENCES auth.users(id),
ADD COLUMN IF NOT EXISTS resolution_notes TEXT,
ADD COLUMN IF NOT EXISTS history JSONB DEFAULT '[]'::jsonb;

-- Create an index for performance
CREATE INDEX IF NOT EXISTS idx_saved_queries_status ON saved_queries(project_id, status);

-- 3. SCHEDULED JOBS (Automation)
-- Stores configuration for automated analysis runs
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    created_by UUID REFERENCES auth.users(id),
    schedule_frequency TEXT CHECK (schedule_frequency IN ('daily', 'weekly', 'monthly')),
    next_run_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    notification_emails JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. PROJECT MEMBERS (RBAC / Multi-user)
-- Links users to projects with specific roles
CREATE TABLE IF NOT EXISTS project_members (
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT CHECK (role IN ('owner', 'editor', 'viewer', 'auditor')),
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (project_id, user_id)
);

-- RLS Policies (Example)
ALTER TABLE project_members ENABLE ROW LEVEL SECURITY;

-- 5. ML MODELS (Anomaly Detection)
-- Stores trained Isolation Forest models serialized as binary
CREATE TABLE IF NOT EXISTS ml_models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    model_type TEXT DEFAULT 'isolation_forest',
    training_metrics JSONB, -- {'accuracy': 0.95, 'outliers_found': 12}
    serialized_model BYTEA, -- Pickle bytes
    trained_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. AUDIT LOG ENHANCEMENTS (21 CFR Part 11)
-- Ensure checksums or immutable flags if strictly required
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS ip_address INET;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_agent TEXT;
