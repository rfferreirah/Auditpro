# REDCap Insight Agent (BI & Reporting)
**Conceito, Funcionalidades e Roadmap Técnico**

## 1. O Conceito
A ideia é criar um **Agente de Inteligência de Negócios (BI)** integrado ao AuditPRO. Enquanto o AuditPRO cuida da *Qualidade* (erros, discrepâncias), o **Insight Agent** cuidará da *Visualização e Interpretação* (tendências, progressos, estatísticas).

Em vez de construir dashboards complexos manualmente (como no PowerBI/Tableau), o usuário usa a IA para "conversar" com os dados do REDCap.

**Exemplo de Interação:**
> *Usuário:* "Gere um gráfico de barras comparando a média de idade entre os grupos Controle e Intervenção, separado por gênero."
>
> *Insight Agent:* "Entendido. Acessei os dados atualizados. Aqui está o gráfico: [Gráfico Gerado]. Notei também que o grupo Controle tem 20% mais participantes homens que o esperado."

---

## 2. Arquitetura "Data Lake" (O Segredo da Performance)
Para que isso seja rápido e amigável, não podemos consultar a API do REDCap a cada pergunta (seria lento).
**Solução:** Criar um "Espelho" (Sync) no Supabase.

1.  **Sync Engine:** Um script Python roda a cada hora (ou sob demanda) e baixa os dados do REDCap via API.
2.  **Schema Mapping:** Transforma estruturas complexas do REDCap (checkboxes, eventos longitudinais) em tabelas SQL relacionais otimizadas.
3.  **Semantic Layer:** A IA lê o Dicionário de Dados (Codebook) para entender que a variável `dm_gender` significa "Gênero do Participante".

---

## 3. Ideias de Funcionalidades (Além do Básico)

### 3.1. Chat-to-Chart (Conversa para Gráfico)
O usuário não precisa saber arrastar colunas ou configurar eixos.
- **Funcionalidade:** O usuário pede em linguagem natural, a IA escreve código Python (Pandas/Matplotlib) ou SQL em tempo real e renderiza o gráfico na tela.
- **Diferencial:** Capacidade de filtrar dados complexos ("Mostre apenas pacientes que completaram a visita 3 mas não tiveram eventos adversos").

### 3.2. Relatórios de Segurança Automatizados (Safety Signals)
Para estudos clínicos, segurança é crítica.
- **Monitor de Eventos Adversos (AE):** Tabelas automáticas categorizadas por gravidade e causalidade.
- **Detecção de Sinais:** A IA alerta se a frequência de "Cefaleia" no grupo Intervenção for estatisticamente maior que no Placebo (Teste Qui-quadrado automático).

### 3.3. Funil de Recrutamento & Retenção (Study Progress)
- **Enrollment Forecast:** "Com a taxa atual, terminaremos o recrutamento em 14 de Março de 2026."
- **Diagrama CONSORT Automático:** Gera os números para o fluxograma obrigatório em publicações (Triados -> Elegíveis -> Randomizados -> Analisados).

### 3.4. Geração de PDF Narrativo
Em vez de só gráficos, a IA escreve o texto.
- **Caso de Uso:** "Escreva o relatório mensal para o patrocinador."
- **Resultado:** Um PDF contendo:
    1. Resumo Executivo (escrito pela IA).
    2. Tabelas demográficas (Tabela 1 de artigos científicos).
    3. Lista de desvios de protocolo.
    4. Gráficos de evolução.

### 3.5. Comparativo Multi-Site (Para Gestores)
- Scorecard de Performance: Compare seus 10 centros de pesquisa.
- "O Centro RJ está recrutando mais rápido, mas tem 3x mais queries pendentes que o Centro SP."

---

## 4. Roadmap de Implementação

### Fase 1: Infraestrutura de Dados (Semanas 1-2)
*   [ ] Implementar **Sync Module** (`redcap_to_sql.py`) para baixar dados brutos.
*   [ ] Criar **Data Flattener**: Converter o modelo "EAV" do REDCap para tabelas "Wide" (uma coluna por variável) amigáveis para análise.
*   [ ] Banco de Dados Analítico no Supabase.

### Fase 2: Motor de Análise Estatística (Semanas 3-4)
*   [ ] Módulo Pandas Avançado: Funções pré-prontas para Tabela 1, Testes T, Qui-quadrado.
*   [ ] Integração Chart.js / Plotly no Frontend.
*   [ ] Endpoint de API que recebe um JSON de dados e devolve configurações de gráfico.

### Fase 3: O Agente de IA (Semanas 5-6)
*   [ ] **Prompt Engineering (Analista de Dados):** Ensinar a IA a escrever queries Pandas baseadas no Codebook.
*   [ ] Integração com LangChain Pandas DataFrame Agent.
*   [ ] Chat Interface na aplicação Web.

### Fase 4: Geração de Documentos e Alertas (Semanas 7-8)
*   [ ] Engine de PDFs (ReportLab ou WeasyPrint) montando layouts com texto + imagens dos gráficos.
*   [ ] Agendamento de emails com "Resumo da Semana".

---

## 5. Viabilidade Técnica
- **Complexidade:** Alta no backend (sincronização de dados), Média no frontend.
- **Custo:** Nulo em licenças (usando Python Open Source). Custo de API da LLM (OpenAI/Anthropic) será recorrente, mas baixo por relatório.
- **Valor Agregado:** Altíssimo. Elimina o trabalho manual de "copiar e colar" dados para o Excel/SPSS para gerar relatórios básicos.

## 6. Próximos Passos
Se aprovado, recomendo começar pela **Fase 1 (Sync)**. Ter os dados do REDCap em um banco SQL local (Supabase) desbloqueia tanto o AuditPRO V2 quanto este novo Insight Agent.
