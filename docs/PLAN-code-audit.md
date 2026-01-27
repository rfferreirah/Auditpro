# Plano de Auditoria de Código Completo

## Objetivo
Realizar uma auditoria abrangente na base de código para garantir segurança, maximizar desempenho e estabelecer uma suíte robusta de testes automatizados.

## Tipo de Projeto
**WEB / BACKEND** (Python/Flask + Integração REDCap)

## Tarefas

### 1. Reforço de Segurança (Security Hardening)
- [ ] **Auditoria de Dependências** → Verificar: Executar `pip-audit` ou `safety check` e resolver vulnerabilidades críticas.
- [ ] **Análise Estática** → Verificar: Executar `bandit -r .` e corrigir problemas de alta gravidade (ex: hardcoded secrets, desserialização insegura).
- [ ] **Gerenciamento de Segredos** → Verificar: Garantir que nenhum token de API esteja hardcoded; confirmar uso de `.env` em `config.py`.

### 2. Qualidade de Código & Linting
- [ ] **Linting** → Verificar: Executar `flake8 .` (ou `pylint`) e resolver erros de formatação/lógica.
- [ ] **Verificação de Tipos** → Verificar: Executar `mypy .` para impor type hints, especialmente em `src/`.

### 3. Testes Automatizados (Pytest)
- [ ] **Configuração de Testes** → Verificar: Criar `tests/conftest.py` com fixtures para o cliente REDCap e dados simulados (mock).
- [ ] **Testes Unitários (Core)** → Verificar: Escrever testes para a lógica de `QueryGenerator` (simulando dados do projeto) -> Todos devem passar.
- [ ] **Testes Unitários (Utils)** → Verificar: Escrever testes para geração de URL e tratamento de erros no `REDCapClient`.
- [ ] **Teste de Integração** → Verificar: Criar um smoke test que acesse o servidor `run_prod.py` local (ex: `/api/test-connection`).

### 4. Otimização de Performance
- [ ] **Perfilamento de Consultas** → Verificar: Perfilar `run_all_analyzers` com `cProfile` para identificar gargalos.
- [ ] **Otimização de Resposta** → Verificar: Garantir que o tempo de resposta de `/api/analyze` seja aceitável para grandes conjuntos de dados (simulados).

## Fase X: Verificação
- [ ] **Segurança:** `bandit` passa sem gravidade Alta.
- [ ] **Lint:** `flake8` retorna código de saída 0.
- [ ] **Testes:** `pytest` passa em todos os testes.
- [ ] **Build:** `run_prod.py` inicia sem erros.
