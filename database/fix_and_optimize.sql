-- ============================================================
-- FIX & OPTIMIZE: Security and Performance Improvements
-- ============================================================
-- Instruções:
-- Execute este script no SQL Editor do Supabase Dashboard para:
-- 1. Corrigir vulnerabilidades de 'Search Path' nas funções.
-- 2. Otimizar a performance das políticas de segurança (RLS).
-- ============================================================

-- [SECURITY] 1. Fix 'update_updated_at_column'
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- [SECURITY] 2. Fix 'handle_new_user'
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
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

-- [PERFORMANCE] 3. Otimizar RLS Policies (Wrap auth.uid() in select)
-- Isso evita que a função auth.uid() seja reavaliada para cada linha.

-- -- Profiles
DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
CREATE POLICY "Users can view own profile" ON public.profiles FOR SELECT USING ((select auth.uid()) = id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile" ON public.profiles FOR UPDATE USING ((select auth.uid()) = id);

-- -- Projects
DROP POLICY IF EXISTS "Users can view own projects" ON public.projects;
CREATE POLICY "Users can view own projects" ON public.projects FOR SELECT USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can insert own projects" ON public.projects;
CREATE POLICY "Users can insert own projects" ON public.projects FOR INSERT WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update own projects" ON public.projects;
CREATE POLICY "Users can update own projects" ON public.projects FOR UPDATE USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can delete own projects" ON public.projects;
CREATE POLICY "Users can delete own projects" ON public.projects FOR DELETE USING ((select auth.uid()) = user_id);

-- -- Analysis History
DROP POLICY IF EXISTS "Users can view own analysis history" ON public.analysis_history;
CREATE POLICY "Users can view own analysis history" ON public.analysis_history FOR SELECT USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can insert own analysis history" ON public.analysis_history;
CREATE POLICY "Users can insert own analysis history" ON public.analysis_history FOR INSERT WITH CHECK ((select auth.uid()) = user_id);

-- -- Saved Queries
DROP POLICY IF EXISTS "Users can view own saved queries" ON public.saved_queries;
CREATE POLICY "Users can view own saved queries" ON public.saved_queries FOR SELECT USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can insert own saved queries" ON public.saved_queries;
CREATE POLICY "Users can insert own saved queries" ON public.saved_queries FOR INSERT WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update own saved queries" ON public.saved_queries;
CREATE POLICY "Users can update own saved queries" ON public.saved_queries FOR UPDATE USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can delete own saved queries" ON public.saved_queries;
CREATE POLICY "Users can delete own saved queries" ON public.saved_queries FOR DELETE USING ((select auth.uid()) = user_id);

-- -- Custom Rules
DROP POLICY IF EXISTS "Users can view own custom rules" ON public.custom_rules;
CREATE POLICY "Users can view own custom rules" ON public.custom_rules FOR SELECT USING ((select auth.uid()) = user_id OR is_global = true);

DROP POLICY IF EXISTS "Users can insert own custom rules" ON public.custom_rules;
CREATE POLICY "Users can insert own custom rules" ON public.custom_rules FOR INSERT WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update own custom rules" ON public.custom_rules;
CREATE POLICY "Users can update own custom rules" ON public.custom_rules FOR UPDATE USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can delete own custom rules" ON public.custom_rules;
CREATE POLICY "Users can delete own custom rules" ON public.custom_rules FOR DELETE USING ((select auth.uid()) = user_id);

-- -- Audit Log
DROP POLICY IF EXISTS "Users can view own audit log" ON public.audit_log;
CREATE POLICY "Users can view own audit log" ON public.audit_log FOR SELECT USING ((select auth.uid()) = user_id);

-- [REMINDER]
-- Lembre-se de ativar "Enable Leaked Password Protection" em Auth -> Security no Dashboard.
