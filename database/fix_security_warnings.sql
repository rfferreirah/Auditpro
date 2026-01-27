-- ============================================================
-- FIX: Security Warnings (Function Search Path Mutable)
-- ============================================================

-- 1. Fix 'update_updated_at_column'
-- Define search_path seguro para evitar sequestro de objetos
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- 2. Fix 'handle_new_user'
-- Security Definer precisa de search_path explícito
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

-- ============================================================
-- Instruções para 'Leaked Password Protection Disabled':
-- 1. Vá no Supabase Dashboard
-- 2. Authentication -> Security -> Password Protection
-- 3. Habilite "Enable Leaked Password Protection"
-- ============================================================
