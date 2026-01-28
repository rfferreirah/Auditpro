# AuditPRO V2 - Technical Roadmap & Specification

## 1. Executive Summary
This document outlines the technical architecture and implementation plan for transforming AuditPRO into a full-featured "Data Quality Assistant". The backend is built on **Python (Flask)** and **Supabase (PostgreSQL)**, providing a solid foundation for the requested features.

## 2. Gap Analysis & Architecture Updates

### 2.1 Dashboard & Visualization
**Current State:**
- `analysis_history` table exists.
- `QualityReport` object contains necessary stats.
**Required Changes:**
- **Backend:** Create endpoint `/api/analytics/dashboard` to aggregate `analysis_history` data (High/Medium/Low trends).
- **Frontend:** Install `Chart.js`. Create `DashboardView` component.

### 2.2 Machine Learning (Anomaly Detection)
**Current State:**
- None.
**Required Changes:**
- **New Module:** `src/ml_engine.py` using `scikit-learn` (`IsolationForest`).
- **Database:** New table `anomaly_models` (store serialized models via pickle/joblib in Storage or bytea).
- **Workflow:** Train model on "Clean" datasets -> Predict on new audits.

### 2.3 Advanced AI (Chat with Data)
**Current State:**
- `src/ai_analyzer.py` exists (LangChain).
**Required Changes:**
- **RAG Implementation:** Ingest REDCap Metadata + Audit Results into a Vector Store (Supabase `pgvector` supported).
- **Feature:** "Chat" endpoint allowing questions like "Which site has most errors?".

### 2.4 Automation & Scheduling
**Current State:**
- Manual execution only.
**Required Changes:**
- **Library:** Integrate `APScheduler` (BackgroundScheduler).
- **Database:** New table `scheduled_jobs` (`project_id`, `cron_expression`, `active`).
- **Worker:** Background thread to check jobs and execute `QueryGenerator`.

### 2.5 Query Management (Workflow)
**Current State:**
- `saved_queries` has basic status.
**Required Changes:**
- **Database:** Add columns to `saved_queries`: `assigned_to` (UUID), `comments` (JSONB), `history` (JSONB).
- **API:** Endpoints for `assign_query`, `resolve_query`, `add_comment`.

### 2.6 Security & Multi-Team (RBAC)
**Current State:**
- Single-owner model (`user_id` on Project).
**Required Changes:**
- **Database:** New table `project_members` (`project_id`, `user_id`, `role` [Admin, Editor, Viewer]).
- **Logic:** Update `auth_manager` and all DB queries to check `project_members` instead of just `projects.user_id`.

## 3. Database Schema Migration (Supabase SQL)

```sql
-- 1. Query Management Enhancements
ALTER TABLE saved_queries 
ADD COLUMN assigned_to UUID REFERENCES auth.users(id),
ADD COLUMN resolution_notes TEXT,
ADD COLUMN history JSONB DEFAULT '[]';

-- 2. Scheduling
CREATE TABLE scheduled_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id),
    schedule_type TEXT CHECK (schedule_type IN ('daily', 'weekly')),
    next_run TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    recipients JSONB -- List of emails
);

-- 3. RBAC
CREATE TABLE project_members (
    project_id UUID REFERENCES projects(id),
    user_id UUID REFERENCES auth.users(id),
    role TEXT CHECK (role IN ('owner', 'editor', 'viewer')),
    PRIMARY KEY (project_id, user_id)
);

-- 4. Anomaly Models
CREATE TABLE ml_models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id),
    model_type TEXT,
    trained_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metrics JSONB, -- Precision/Recall
    serialized_model BYTEA -- Or path to Storage bucket
);
```

## 4. Implementation Phasing

**Phase 1: Visualization & Query Workflow (Value Add)**
- Implement Dashboard endpoints.
- Add Assign/Resolve workflow.

**Phase 2: Automation & Notifications**
- Set up APScheduler.
- Implement Email alerts (SendGrid/SMTP).

**Phase 3: Deep Tech (ML & Advanced AI)**
- Train Isolation Forest models.
- Implement Vector Search for Chat.

**Phase 4: Enterprise Features (RBAC & Audit)**
- Refactor Auth for multi-user projects.
- Finalize 21 CFR Part 11 Compliance (Immutable logs).
