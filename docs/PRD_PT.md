# Documento de Requisitos do Produto (PRD)
## REDCap Data Quality Intelligence Agent (Audit PRO)

**Versão:** 2.0
**Data:** 24/01/2026
**Status:** Ativo/Desenvolvimento

---

## 1. Visão Geral do Produto
O **Audit PRO** é um agente automatizado inteligente projetado para revolucionar o gerenciamento de qualidade de dados em pesquisas clínicas. Ele conecta-se diretamente a bancos de dados REDCap para realizar auditorias instantâneas e abrangentes, identificando inconsistências, dados ausentes e erros lógicos que o monitoramento manual muitas vezes deixa passar. Combinando regras de validação determinísticas com IA Generativa (LLMs), oferece uma abordagem híbrida para "Data Cleaning".

## 2. Declaração do Problema
- **Ineficiência:** A limpeza manual de dados em Excel ou via verificações visuais consome muito tempo (horas/dias).
- **Erro Humano:** A fadiga leva a erros despercebidos em grandes conjuntos de dados.
- **Riscos de Segurança:** Dados clínicos inválidos (ex: impossibilidades fisiológicas) podem passar despercebidos.
- **Complexidade:** Criar regras lógicas personalizadas no REDCap exige conhecimento técnico que usuários padrão geralmente não possuem.

## 3. Metas e Objetivos
- **Reduzir Tempo de Auditoria:** Cortar o tempo de limpeza de horas para segundos.
- **Democratizar Lógica:** Permitir que usuários não técnicos criem regras de validação complexas usando linguagem natural (IA).
- **Garantir Integridade:** Garantir 100% de detecção de erros estruturais de processamento definidos.
- **Relatórios Profissionais:** Gerar relatórios em PDF/JSON prontos para auditoria e monitores.

## 4. Personas do Usuário
1.  **Gerente de Dados Clínicos (CDM):** Precisa de detecção confiável de erros em massa e gerenciamento de queries.
2.  **Investigador Principal (IP):** Precisa de garantia da integridade dos dados para publicações.
3.  **Coordenador de Estudo:** Precisa de feedback imediato sobre erros de digitação antes das visitas de monitoria.
4.  **Monitor (CRA):** Precisa de um checklist de problemas para verificar durante as visitas ao centro.

## 5. Requisitos Funcionais

### 5.1 Autenticação e Gestão de Usuários
- [x] **Cadastro/Login:** Autenticação segura por e-mail/senha (Supabase).
- [x] **Gestão de Papéis:** Suporte para diferentes papéis (Gerente, Coordenador, etc.).
- [x] **Gestão de Sessão:** Logout seguro e persistência de sessão.

### 5.2 Integração REDCap
- [x] **Conexão API:** Conectar via Token API e URL.
- [x] **Exportação de Metadados:** Buscar dicionário do projeto (variáveis, formulários).
- [x] **Exportação de Dados:** Buscar dados clínicos (registros, eventos).
- [x] **Logging:** Opção para incluir logs de auditoria na análise.

### 5.3 Motor de Análise de Dados
- [x] **Análise Estrutural:** Detectar campos ausentes, erros de lógica condicional (branching logic) e incompatibilidade de tipos de dados.
- [x] **Geração de Queries:** Gerar automaticamente queries para problemas identificados.
- [x] **Priorização:** Classificar automaticamente problemas como Alta, Média ou Baixa prioridade.
- [x] **Análise com IA (LangChain + Claude):** Gerar resumos executivos e insights a partir de padrões de queries.

### 5.4 Motor de Regras Customizadas
- [x] **CRUD de Regras:** Interface para Criar, Ler, Atualizar, Deletar regras de validação personalizadas (armazenadas em JSON).
- [x] **Tipos de Regras Suportados:**
    - `comparison` (Operadores padrão: =, !=, <, >, <=, >=)
    - `range` (Entre valores)
    - `regex` (Correspondência de padrão)
    - `cross_field` (Lógica de comparação entre dois campos distintos)
    - `condition` (Lógica condicional)
- [x] **Geração por Linguagem Natural:** Funcionalidade "Regra Mágica" para gerar lógica Python a partir de texto/voz usando IA.
- [x] **Lógica Cross-Form:** Modelo de backend suporta `field2` para comparações entre variáveis de formulários diferentes.

### 5.5 Relatórios e Dashboard
- [x] **Dashboard Interativo:** Resumo visual dos problemas (gráficos, estatísticas).
- [x] **Navegador de Queries:** Visualização paginada de todas as queries geradas com filtros.
- [x] **Exportação PDF:** Geração de relatório profissional.
- [x] **Exportação JSON:** Exportação de dados brutos para ferramentas externas.
- [x] **Design System:** UI consistente baseada em glassmorphism e estética moderna.

## 6. Arquitetura Técnica
- **Backend:** Python (Flask)
- **Banco de Dados:** Supabase (PostgreSQL)
- **Frontend:** HTML5, CSS3 (Design System Customizado), JavaScript (Vanilla + Chart.js)
- **Motor de IA:** Orquestração LangChain com Anthropic Claude 3.5 Sonnet
- **Integração:** REDCap PyCap / API Padrão

## 7. Requisitos Não Funcionais
- **Performance:** A análise de projetos padrão (<5000 registros) deve ser concluída em <30 segundos.
- **Segurança:** Os Tokens de API nunca devem ser armazenados permanentemente sem criptografia.
- **Usabilidade:** A interface deve suportar Modos Claro/Escuro e ser responsiva.
- **Compliance:** A saída deve ser adequada para documentação de Boas Práticas Clínicas (GCP).

## 8. Roadmap e Melhorias Futuras

### Fase 1: Polimento de UX/UI (Foco Atual)
- [ ] **Ícones:** Substituir emojis por Phosphor Icons/Heroicons para um visual profissional.
- [ ] **Contraste:** Melhorar acessibilidade e taxas de contraste no Modo Claro.
- [ ] **Micro-interações:** Adicionar estados de carregamento e efeitos de hover para melhor "sensação".

### Fase 2: IA Avançada e Automação
- [ ] **Voz-para-Regra:** Permitir que usuários ditem regras via microfone.
- [ ] **Upload Automático de Queries:** Postar automaticamente queries específicas geradas de volta no REDCap (Write API).
- [ ] **Sistema Multi-Agente:** Implementar agentes especializados para diferentes domínios (Oncologia, Cardiologia).

### Fase 3: Escala SaaS
- [ ] **Integração Stripe:** Gestão de assinaturas.
- [ ] **Colaboração em Equipe:** Projetos compartilhados e comentários dentro do Audit PRO.
- [ ] **Webhooks de API:** Disparar análise automaticamente quando dados são inseridos no REDCap.

## 9. Métricas de Sucesso
- **Taxa de Ativação:** % de cadastros que executam pelo menos uma análise.
- **Retenção:** % of usuários retornando para auditorias semanais/mensais.
- **Geração de Regras:** % de regras geradas por IA bem-sucedidas vs. edições manuais.
