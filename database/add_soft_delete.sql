-- ============================================================
-- ATUALIZAÇÃO DE SCHEMA: Soft Delete para Custom Rules
-- Adiciona coluna deleted_at para permitir exclusão lógica
-- ============================================================

ALTER TABLE public.custom_rules
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;

COMMENT ON COLUMN public.custom_rules.deleted_at IS 'Data de exclusão lógica. Se preenchido, a regra foi "excluída" da UI.';
