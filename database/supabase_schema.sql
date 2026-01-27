-- ============================================================
-- Audit PRO - Supabase Database Schema
-- Execute este arquivo no SQL Editor do Supabase Dashboard
-- ============================================================

-- ============================================================
-- 1. PROFILES (Extensão do auth.users)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT,
    organization TEXT,
    role TEXT DEFAULT 'pesquisador' CHECK (role IN ('pesquisador', 'gestor', 'gestor_dados', 'outro')),
    role_outro TEXT, -- Descrição quando role = 'outro'
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.profiles IS 'Perfis de usuário estendidos do auth.users';

-- Trigger para criar perfil automaticamente ao criar usuário
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, full_name, organization, role, role_outro)
    VALUES (
        new.id, 
        new.raw_user_meta_data->>'full_name',
        new.raw_user_meta_data->>'organization',
        COALESCE(new.raw_user_meta_data->>'role', 'pesquisador'),
        new.raw_user_meta_data->>'role_outro'
    );
    RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Remove trigger se existir e recria
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================
-- 2. PROJECTS (Projetos REDCap conectados)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_title TEXT NOT NULL,
    redcap_project_id INTEGER,
    api_url TEXT NOT NULL,
    is_longitudinal BOOLEAN DEFAULT false,
    total_records INTEGER,
    last_analysis_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.projects IS 'Projetos REDCap conectados pelos usuários';

CREATE INDEX IF NOT EXISTS idx_projects_user ON public.projects(user_id);

-- ============================================================
-- 3. ANALYSIS HISTORY (Histórico de Análises)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.analysis_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES public.projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    total_records INTEGER NOT NULL DEFAULT 0,
    total_queries INTEGER NOT NULL DEFAULT 0,
    high_priority_count INTEGER DEFAULT 0,
    medium_priority_count INTEGER DEFAULT 0,
    low_priority_count INTEGER DEFAULT 0,
    analysis_duration_ms INTEGER,
    ai_analysis_used BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.analysis_history IS 'Log de todas as análises realizadas';

CREATE INDEX IF NOT EXISTS idx_analysis_project ON public.analysis_history(project_id);
CREATE INDEX IF NOT EXISTS idx_analysis_user ON public.analysis_history(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_created ON public.analysis_history(created_at DESC);

-- ============================================================
-- 4. SAVED QUERIES (Queries Salvas/Favoritas)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.saved_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID REFERENCES public.projects(id) ON DELETE SET NULL,
    record_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    field_label TEXT,
    current_value TEXT,
    priority TEXT CHECK (priority IN ('Alta', 'Média', 'Baixa')),
    issue_type TEXT,
    description TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'resolved', 'ignored')),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES auth.users(id),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.saved_queries IS 'Queries marcadas ou salvas pelos usuários para acompanhamento';

CREATE INDEX IF NOT EXISTS idx_saved_queries_user ON public.saved_queries(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_queries_project ON public.saved_queries(project_id);
CREATE INDEX IF NOT EXISTS idx_saved_queries_status ON public.saved_queries(status);

-- ============================================================
-- 5. CUSTOM RULES (Regras de Validação Personalizadas)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.custom_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('required_if', 'range_check', 'date_comparison', 'cross_field', 'regex', 'custom')),
    rule_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority TEXT DEFAULT 'Média' CHECK (priority IN ('Alta', 'Média', 'Baixa')),
    is_active BOOLEAN DEFAULT true,
    is_global BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.custom_rules IS 'Regras de validação personalizadas criadas pelos usuários';

CREATE INDEX IF NOT EXISTS idx_custom_rules_user ON public.custom_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_custom_rules_active ON public.custom_rules(is_active) WHERE is_active = true;

-- ============================================================
-- 6. AUDIT LOG (Log de Ações - Opcional)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.audit_log IS 'Log de auditoria de ações dos usuários';

CREATE INDEX IF NOT EXISTS idx_audit_log_user ON public.audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON public.audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON public.audit_log(action);

-- ============================================================
-- ROW LEVEL SECURITY (RLS) - OBRIGATÓRIO PARA SEGURANÇA
-- ============================================================

-- Habilitar RLS em todas as tabelas
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saved_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.custom_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- POLICIES: profiles
-- ============================================================
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id);

-- ============================================================
-- POLICIES: projects
-- ============================================================
CREATE POLICY "Users can view own projects"
    ON public.projects FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own projects"
    ON public.projects FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own projects"
    ON public.projects FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own projects"
    ON public.projects FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- POLICIES: analysis_history
-- ============================================================
CREATE POLICY "Users can view own analysis history"
    ON public.analysis_history FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own analysis history"
    ON public.analysis_history FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ============================================================
-- POLICIES: saved_queries
-- ============================================================
CREATE POLICY "Users can view own saved queries"
    ON public.saved_queries FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own saved queries"
    ON public.saved_queries FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own saved queries"
    ON public.saved_queries FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own saved queries"
    ON public.saved_queries FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- POLICIES: custom_rules
-- ============================================================
CREATE POLICY "Users can view own custom rules"
    ON public.custom_rules FOR SELECT
    USING (auth.uid() = user_id OR is_global = true);

CREATE POLICY "Users can insert own custom rules"
    ON public.custom_rules FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own custom rules"
    ON public.custom_rules FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own custom rules"
    ON public.custom_rules FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- POLICIES: audit_log (somente leitura para o próprio usuário)
-- ============================================================
CREATE POLICY "Users can view own audit log"
    ON public.audit_log FOR SELECT
    USING (auth.uid() = user_id);

-- ============================================================
-- FUNÇÃO HELPER: Atualizar updated_at automaticamente
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Aplicar trigger de updated_at nas tabelas relevantes
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON public.projects
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_custom_rules_updated_at
    BEFORE UPDATE ON public.custom_rules
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- FIM DO SCHEMA
-- ============================================================
-- Execute este script no SQL Editor do Supabase Dashboard:
-- 1. Vá para o Dashboard do Supabase
-- 2. Clique em "SQL Editor" no menu lateral
-- 3. Cole este script completo
-- 4. Clique em "Run"
-- ============================================================
