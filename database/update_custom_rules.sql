-- ============================================================
-- ATUALIZAÇÃO DE SCHEMA: Custom Rules
-- Adiciona colunas explícitas para campos de regra
-- ============================================================

ALTER TABLE public.custom_rules
ADD COLUMN IF NOT EXISTS field TEXT,
ADD COLUMN IF NOT EXISTS operator TEXT,
ADD COLUMN IF NOT EXISTS value TEXT;

COMMENT ON COLUMN public.custom_rules.field IS 'Campo alvo da regra (extraído de rule_config)';
COMMENT ON COLUMN public.custom_rules.operator IS 'Operador da regra (extraído de rule_config)';
COMMENT ON COLUMN public.custom_rules.value IS 'Valor de comparação (extraído de rule_config)';

-- Opcional: Atualizar regras existentes (se houver) extraindo do JSONB
UPDATE public.custom_rules
SET
    field = rule_config->>'field',
    operator = rule_config->>'operator',
    value = rule_config->>'value'
WHERE field IS NULL AND rule_config IS NOT NULL;
