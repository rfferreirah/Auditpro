-- ============================================================
-- ATUALIZAÇÃO DE SCHEMA: Analysis History
-- Adiciona coluna project_title para facilitar identificação
-- ============================================================

ALTER TABLE public.analysis_history
ADD COLUMN IF NOT EXISTS project_title TEXT;

COMMENT ON COLUMN public.analysis_history.project_title IS 'Título do projeto (denormalizado para facilitar visualização)';

-- Opcional: Tentar popular dados existentes fazendo join com a tabela projects
-- Isso só funciona se a tabela projects tiver os dados e os IDs baterem
UPDATE public.analysis_history ah
SET project_title = p.project_title
FROM public.projects p
WHERE ah.project_id = p.id
AND ah.project_title IS NULL;
