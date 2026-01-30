"""
REDCap Data Quality Intelligence Agent - LangChain AI Analyzer

Agente com IA para análise inteligente de qualidade de dados.
Utiliza LangChain com Claude para fornecer insights mais profundos.
"""

import json
from typing import Optional

# Tenta importar LangChain (opcional)
try:
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

# Tenta importar Google GenAI
try:
    import google.generativeai as genai
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False

from src.models import ProjectData, Query, QualityReport
import config
import json


class AIAnalyzer:
    """
    Analisador com IA usando LangChain (OpenAI/Claude) ou Google GenAI SDK (Gemini).
    
    Fornece análises mais profundas e recomendações inteligentes
    baseadas nos dados e queries identificadas.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa o analisador de IA.
        
        Args:
            api_key: Chave da API (opcional, usa env se não fornecida)
        """
        self.provider = config.AI_PROVIDER
        self.llm = None
        self.gemini_model = None
        
        if self.provider == "anthropic" and LANGCHAIN_AVAILABLE:
            key = api_key or config.ANTHROPIC_API_KEY
            if key:
                self.llm = ChatAnthropic(
                    model="claude-3-5-sonnet-20240620",
                    api_key=key,
                    temperature=0.3,
                    max_tokens=4096,
                )
        elif self.provider == "openai" and LANGCHAIN_AVAILABLE:
            key = api_key or config.OPENAI_API_KEY
            if key:
                self.llm = ChatOpenAI(
                    model="gpt-4-turbo-preview",
                    api_key=key,
                    temperature=0.3,
                    max_tokens=4096,
                )
        elif self.provider == "gemini" and GOOGLE_GENAI_AVAILABLE:
            key = api_key or config.GOOGLE_API_KEY
            if key:
                genai.configure(api_key=key)
                # Tenta modelo flash, se falhar o fallback é tratado nas chamadas ou init
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    
    @property
    def is_available(self) -> bool:
        """Verifica se a IA está disponível."""
        if self.provider == "gemini":
            return self.gemini_model is not None
        return self.llm is not None
    
    def _invoke_gemini(self, system_instruction: str, user_input: str) -> str:
        """Invocação direta do Gemini com tratamento de erros e fallback."""
        if not self.gemini_model:
            raise Exception("Gemini model not initialized")
            
        full_prompt = f"{system_instruction}\n\nUser Request:\n{user_input}"
        
        try:
            response = self.gemini_model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            # Fallback trivial para gemini-pro se o erro for 404/not found
            error_str = str(e)
            if "404" in error_str or "not found" in error_str.lower():
                print("DEBUG: Fallback to gemini-pro")
                try:
                    fallback_model = genai.GenerativeModel('gemini-pro')
                    response = fallback_model.generate_content(full_prompt)
                    return response.text
                except Exception as e2:
                    raise Exception(f"Gemini Error (Primary & Fallback): {str(e2)}")
            raise e

    def analyze(self, project_data: ProjectData, include_logs: bool = False, structural_checks: list[str] = None) -> QualityReport:
        """
        Executa o pipeline completo de análise.
        
        Args:
            project_data: Dados do projeto REDCap
            include_logs: Se True, analisa logs de auditoria
            structural_checks: Lista de verificações estruturais a ativar
            
        Returns:
            QualityReport completo
        """
        all_queries = []
        
        # 1. Análise Estrutural (Configurável)
        # Se structural_checks for None, o analyzer usará seus defaults (tudo ativado)
        # Se for uma lista vazia [], desativará tudo
        # Placeholder for StructuralAnalyzer import
        # from src.analyzers import StructuralAnalyzer 
        # structural = StructuralAnalyzer(project_data, enabled_checks=structural_checks)
        # all_queries.extend(structural.analyze())
        
        # Placeholder for other analyzers
        # data_consistency = DataConsistencyAnalyzer(project_data)
        # all_queries.extend(data_consistency.analyze())
        
        # audit_log = AuditLogAnalyzer(project_data)
        # if include_logs:
        #     all_queries.extend(audit_log.analyze())
            
        # report = QualityReport(project_data, all_queries)
        # return report
        return QualityReport(project_data, all_queries) # Temporary return
    
    def analyze_queries(self, report: QualityReport, project_data: ProjectData) -> dict:
        """
        Analisa queries com IA e fornece insights.
        
        Args:
            report: Relatório de qualidade
            project_data: Dados do projeto
            
        Returns:
            Dicionário com análise de IA
        """
        if not self.is_available:
            return {"available": False, "message": f"IA ({self.provider}) não configurada. Verifique as chaves de API no .env"}
        
        summary = self._prepare_summary(report, project_data)
        
        system_prompt = """Você é um especialista em Data Management de estudos clínicos com vasta experiência em REDCap.
Sua tarefa é analisar os resultados de uma auditoria automática de qualidade de dados e fornecer:
1. **Análise Executiva**: Resumo do estado geral da qualidade dos dados (2-3 parágrafos)
2. **Principais Preocupações**: Lista das 5 questões mais críticas que precisam de atenção imediata
3. **Padrões Identificados**: Tendências ou padrões nos erros que indicam problemas sistêmicos
4. **Recomendações**: Ações concretas para melhorar a qualidade dos dados
5. **Priorização**: Ordem sugerida para resolver os problemas
Seja objetivo e técnico. Use terminologia de pesquisa clínica."""

        user_prompt = f"""Analise os seguintes resultados de auditoria de qualidade de dados do REDCap:
## Informações do Projeto
- Total de participantes: {summary['total_records']}
- Total de queries geradas: {summary['total_queries']}
- Queries de Alta Prioridade: {summary['high_priority']}
- Queries de Média Prioridade: {summary['medium_priority']}
- Queries de Baixa Prioridade: {summary['low_priority']}
## Tipos de Erro Mais Comuns
{summary['error_types']}
## Campos com Mais Problemas
{summary['problem_fields']}
## Amostra de Queries (primeiras 20)
{summary['sample_queries']}
Por favor, forneça sua análise detalhada."""

        try:
            if self.provider == "gemini":
                analysis = self._invoke_gemini(system_prompt, user_prompt)
            else:
                prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{user_input}")])
                chain = prompt | self.llm | StrOutputParser()
                analysis = chain.invoke({"user_input": user_prompt})

            return {"available": True, "analysis": analysis}
        except Exception as e:
            return {"available": False, "message": f"Erro na análise de IA: {str(e)}"}
    
    def suggest_corrections(self, queries: list[Query]) -> list[dict]:
        """
        Sugere correções específicas para queries usando IA.
        
        Args:
            queries: Lista de queries a analisar
            
        Returns:
            Lista de sugestões de correção
        """
        if not self.is_available: return []
        
        # Limita a 10 queries para não exceder tokens
        queries_to_analyze = queries[:10]
        
        queries_text = "\n".join([
            f"- Campo: {q.field}, Valor: {q.value_found}, Erro: {q.issue_type}, "
            f"Explicação: {q.explanation}"
            for q in queries_to_analyze
        ])
        
        system_prompt = """Você é um especialista em correção de dados de estudos clínicos.
Para cada query de qualidade apresentada, sugira uma correção específica e prática.
Responda em JSON com o formato:
[{"field": "nome_campo", "suggestion": "sugestão de correção", "action": "ação recomendada"}]"""
        
        user_prompt = f"""Sugira correções para as seguintes queries:
{queries_text}
Retorne apenas o JSON, sem explicações adicionais."""

        try:
            if self.provider == "gemini":
                result = self._invoke_gemini(system_prompt, user_prompt)
            else:
                prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{queries}")])
                chain = prompt | self.llm | StrOutputParser()
                result = chain.invoke({"queries": queries_text})
            
            # Limpeza do resultado (Markdown block removal se necessário)
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.endswith("```"):
                result = result[:-3]
                
            # Tenta parsear JSON
            suggestions = json.loads(result)
            return suggestions
        except Exception:
            return []
    
    def generate_report_summary(self, report: QualityReport) -> str:
        """
        Gera um resumo executivo do relatório usando IA.
        
        Args:
            report: Relatório de qualidade
            
        Returns:
            Resumo em texto
        """
        if not self.is_available: return "Análise de IA não disponível."
        
        from collections import Counter
        priority_counts = Counter(q.priority for q in report.queries)
        
        system_prompt = """Você é um especialista em pesquisa clínica escrevendo um resumo executivo 
para o investigador principal de um estudo. Seja conciso e profissional."""
        
        user_prompt = f"""Escreva um resumo executivo (máximo 3 parágrafos) sobre a qualidade dos dados:
- Total de participantes: {report.project_summary.total_records}
- Total de queries: {report.project_summary.total_queries_generated}
- Alta prioridade: {priority_counts.get("Alta", 0)}
- Média prioridade: {priority_counts.get("Média", 0)}
- Baixa prioridade: {priority_counts.get("Baixa", 0)}
- Principais tipos de erro: {", ".join(report.project_summary.most_common_error_types[:5])}"""

        try:
            if self.provider == "gemini":
                return self._invoke_gemini(system_prompt, user_prompt)
            else:
                prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{user_input}")])
                chain = prompt | self.llm | StrOutputParser()
                return chain.invoke({"user_input": user_prompt})
        except Exception as e:
            return f"Erro ao gerar resumo: {str(e)}"
    
    def _prepare_summary(self, report: QualityReport, project_data: ProjectData) -> dict:
        """Prepara resumo dos dados para análise de IA."""
        from collections import Counter
        
        priority_counts = Counter(q.priority for q in report.queries)
        error_types = Counter(q.issue_type for q in report.queries)
        
        # Formata tipos de erro
        error_types_text = "\n".join([
            f"- {config.ISSUE_TYPES.get(t, t)}: {c} ocorrências"
            for t, c in error_types.most_common(10)
        ])
        
        # Formata campos com problemas
        problem_fields_text = "\n".join([
            f"- {field}"
            for field in report.project_summary.fields_with_most_issues[:10]
        ])
        
        # Amostra de queries
        sample_queries_text = "\n".join([
            f"- [{q.priority}] Record {q.record_id}, Campo: {q.field}, "
            f"Tipo: {config.ISSUE_TYPES.get(q.issue_type, q.issue_type)}"
            for q in report.queries[:20]
        ])
        
        return {
            "total_records": report.project_summary.total_records,
            "total_queries": report.project_summary.total_queries_generated,
            "high_priority": priority_counts.get("Alta", 0),
            "medium_priority": priority_counts.get("Média", 0),
            "low_priority": priority_counts.get("Baixa", 0),
            "error_types": error_types_text,
            "problem_fields": problem_fields_text,
            "sample_queries": sample_queries_text,
        }

    def parse_natural_language_rule(self, text: str, field_list: list[str] = None, event_list: list[str] = None) -> dict:
        """
        Interpreta uma regra em linguagem natural e converte para JSON estruturado.
        
        Args:
            text: Texto da regra (ex: "A idade deve ser maior que 18")
            field_list: Lista opcional de nomes de variáveis do projeto
            event_list: Lista opcional de nomes de eventos (para cross-event)
            
        Returns:
            Dicionário com a estrutura da regra ou erro
        """
        if not self.is_available:
            return {"success": False, "error": "IA não configurada"}
            
        context_str = ""
        if field_list:
            # Limita a 500 campos para não estourar o contexto
            context_str += f"""
CONTEXTO - CAMPOS:
Abaixo estão os nomes reais das variáveis (campos) no banco de dados.
Sempre que possível, use um valor desta lista para o campo 'field'.
Se o usuário disser "idade", e na lista tiver "age_years", use "age_years".

Campos Disponíveis: [{', '.join(field_list[:500])}]
"""

        if event_list:
            context_str += f"""
CONTEXTO - EVENTOS:
Abaixo estão os nomes únicos dos eventos (visitas) no projeto.
Use estes nomes exatos para 'event1' e 'event2' em regras Cross-Event.

Eventos Disponíveis: [{', '.join(event_list[:100])}]
"""

        # Build prompt using string concatenation to safely handle JSON braces
        system_intro = "Você é um assistente especialista em criação de regras de validação de dados.\n"
        system_intro += "Sua tarefa é converter uma solicitação em linguagem natural para um objeto JSON de regra estruturada.\n"
        
        # Schema definition - IMPORTANT: double braces {{ }} to escape for LangChain
        schema_def = """
        O Schema da Regra é:
        {{
            "name": "Nome curto e descritivo da regra",
            "field": "nome_do_campo_snake_case (se 'todo o projeto', use '_ALL_')",
            "rule_type": "comparison" | "range" | "regex" | "condition" | "uniqueness" | "cross_event",
            "operator": "=" | "!=" | ">" | "<" | ">=" | "<=" | "between" | "matches" | "contains" | "unique" | "empty" | "not_empty" | "present_implies",
            "value": "valor da regra (para cross_event, é o nome do segundo campo)",
            "priority": "Alta" | "Média" | "Baixa",
            "message": "Mensagem de erro amigável pro usuário",
            "event1": "Nome do evento do primeiro campo (opcional, só para cross_event)",
            "event2": "Nome do evento do segundo campo (opcional, só para cross_event)"
        }}
        
        BIBLIOTECA DE PADRÕES INTELIGENTES:
        1. COMPARAÇÃO SIMPLES: rule_type="comparison", operator="=", value="X"
        2. RANGE NUMÉRICO: rule_type="range", operator="between", value="min,max"
        3. FORMATO (Regex): rule_type="regex", operator="matches", value="pattern"
        4. DATAS RELATIVAS (HOJE/FUTURO):
           - "A data de nascimento não pode ser no futuro"
           - JSON: {{"rule_type": "comparison", "operator": "<=", "value": "_TODAY_"}}
           - "Data de inclusão deve ser anterior a hoje" -> operator "<", value "_TODAY_"
           - "Data deve ser hoje ou futuro" -> operator ">=", value "_TODAY_"
           Use o token especial "_TODAY_" sempre que a regra mencionar "hoje", "futuro", "passado" ou "data atual".
           
        5. CROSS-EVENT (Entre Visitas):
           - "O peso na Semana 4 deve ser menor que na Triagem"
           - JSON: {{
               "name": "Peso Semana 4 < Triagem",
               "field": "weight",
               "rule_type": "cross_event",
               "operator": "<",
               "value": "weight", 
               "event1": "week_4_arm_1", 
               "event2": "screening_arm_1",
               "priority": "Média",
               "message": "Perda de peso esperada não observada"
             }}
           
        Exemplos Avançados:
        
        User: "O CPF deve ter formato válido"
        JSON: {{"name": "Formato CPF", "field": "cpf", "rule_type": "regex", "operator": "matches", "value": "^\\d{{3}}\\.\\d{{3}}\\.\\d{{3}}-\\d{{2}}$", "priority": "Alta", "message": "CPF fora do padrão XXX.XXX.XXX-XX"}}

        User: "A data da alta deve ser posterior a data de admissão"
        JSON: {{"name": "Consistência de Datas", "field": "dt_alta", "rule_type": "comparison", "operator": ">", "value": "dt_admissao", "priority": "Alta", "message": "Data de alta deve ser posterior à admissão"}}
        
        User: "No evento Follow-up, o status deve ser Completo"
        JSON: {{"name": "Status em Follow-up", "field": "status", "rule_type": "comparison", "operator": "=", "value": "Completo", "event1": "follow_up_arm_1", "priority": "Média", "message": "Status incorreto no Follow-up"}}
        """
        
        full_system_message = system_intro + context_str + schema_def
        user_prompt = f"""Converta esta regra para JSON:
"{text}"

Retorne APENAS o JSON válido, sem markdown ou explicações."""

        try:
            if self.provider == "gemini":
                result = self._invoke_gemini(full_system_message, user_prompt)
            else:
                prompt = ChatPromptTemplate.from_messages([("system", full_system_message), ("human", "{text}")])
                chain = prompt | self.llm | StrOutputParser()
                result = chain.invoke({"text": text})
            
            # Limpeza do resultado (Markdown block removal se necessário)
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.endswith("```"):
                result = result[:-3]
                
            rule_data = json.loads(result)
            return {
                "success": True,
                "rule": rule_data
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro ao interpretar regra: {str(e)}"
            }


def create_ai_analyzer() -> AIAnalyzer:
    """
    Cria instância do analisador de IA.
    
    Returns:
        AIAnalyzer configurado
    """
    return AIAnalyzer()
