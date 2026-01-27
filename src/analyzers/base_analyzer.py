"""
REDCap Data Quality Intelligence Agent - Base Analyzer

Classe base para todos os analisadores de qualidade de dados.
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from dateutil import parser as date_parser

from ..models import ProjectData, Query, FieldMetadata
import config


class BaseAnalyzer(ABC):
    """
    Classe base abstrata para analisadores de qualidade de dados.
    
    Todos os analisadores específicos devem herdar desta classe e
    implementar o método analyze().
    """
    
    def __init__(self, project_data: ProjectData):
        """
        Inicializa o analisador.
        
        Args:
            project_data: Dados do projeto REDCap
        """
        self.project_data = project_data
        self.queries: list[Query] = []
        
    @abstractmethod
    def analyze(self) -> list[Query]:
        """
        Executa a análise de qualidade.
        
        Returns:
            Lista de queries identificadas
        """
        pass
    
    def add_query(
        self,
        record_id: str,
        event: str,
        instrument: str,
        field: str,
        value_found: any,
        issue_type: str,
        explanation: str,
        priority: str = "Média",
        suggested_action: Optional[str] = None,
        modification_severity: Optional[str] = None,
        modification_details: Optional[str] = None,
    ) -> None:
        """
        Adiciona uma query à lista.
        
        Args:
            record_id: ID do participante
            event: Nome do evento
            instrument: Nome do formulário
            field: Nome do campo
            value_found: Valor encontrado
            issue_type: Tipo de inconsistência
            explanation: Explicação técnica
            priority: Alta, Média ou Baixa
            suggested_action: Sugestão de correção (opcional)
            modification_severity: Grau de modificação (Simples, Moderada, Complexa)
            modification_details: Detalhes sobre a modificação necessária
        """
        # Auto-determina grau de modificação se não fornecido
        if modification_severity is None:
            modification_severity = self._determine_modification_severity(issue_type)
        
        if modification_details is None:
            modification_details = self._get_modification_details(issue_type, value_found)
        
        query = Query(
            record_id=str(record_id),
            event=event or "N/A",
            instrument=instrument,
            field=field,
            value_found=value_found,
            issue_type=issue_type,
            explanation=explanation,
            priority=priority,
            suggested_action=suggested_action,
            modification_severity=modification_severity,
            modification_details=modification_details,
        )
        self.queries.append(query)
    
    def _determine_modification_severity(self, issue_type: str) -> str:
        """
        Determina o grau de modificação baseado no tipo de issue.
        
        Returns:
            "Simples", "Moderada" ou "Complexa"
        """
        # Modificações simples - apenas preencher ou corrigir valor
        simple_types = [
            "required_field_empty",
            "invalid_choice",
            "invalid_format",
            "value_out_of_range",
        ]
                # Modificações complexas - requer análise detalhada
        complex_types = [
            "physiologically_impossible",
            "clinical_classification_mismatch",
            "death_date_inconsistent",
            "suspicious_edit_pattern",
            "inclusion_criteria_violated",
            "exclusion_criteria_violated",
            "broken_sequence",
        ]
        
        if issue_type in simple_types:
            return "Simples"
        elif issue_type in complex_types:
            return "Complexa"
        else:
            return "Moderada"
    
    def _get_modification_details(self, issue_type: str, value_found: any) -> str:
        """
        Gera detalhes sobre a modificação necessária.
        
        Returns:
            String com detalhes da modificação
        """
        details = {
            "required_field_empty": "Preencher valor ausente. Consultar fonte primária de dados ou contatar participante.",
            "invalid_choice": "Corrigir código inválido para opção válida. Verificar lista de opções no dicionário de dados.",
            "invalid_format": "Ajustar formato do valor (ex: data, número). Verificar formato esperado no REDCap.",
            "value_out_of_range": "Verificar valor com fonte primária. Se correto, documentar exceção no campo de comentários.",
            "date_out_of_order": "Revisar cronologia dos eventos. Verificar se datas foram invertidas ou se evento foi registrado no formulário errado.",
            "followup_before_baseline": "Verificar se data de follow-up está correta ou se baseline precisa correção.",
            "event_out_of_timeline": "Documentar desvio de protocolo ou corrigir data se erro de digitação.",
            "field_should_be_empty": "Remover valor ou corrigir campo condicional relacionado.",
            "calculated_field_mismatch": "Verificar valores fonte e recalcular. Pode indicar erro de digitação.",
            "physiologically_impossible": "Requer investigação detalhada. Verificar com equipe clínica e fonte primária.",
            "clinical_classification_mismatch": "Revisar valores clínicos relacionados. Possível inversão de valores.",
            "death_date_inconsistent": "Investigação crítica. Verificar prontuário e registros oficiais.",
            "suspicious_edit_pattern": "Auditar edições. Verificar com usuário responsável pelas modificações.",
            "broken_sequence": "Verificar sequência de instrumentos repetidos. Pode indicar dados faltantes.",
        }
        
        return details.get(issue_type, "Verificar valor e corrigir conforme necessário.")
    
    def get_field_metadata(self, field_name: str) -> Optional[FieldMetadata]:
        """
        Obtém metadados de um campo.
        
        Args:
            field_name: Nome do campo
            
        Returns:
            FieldMetadata ou None se não encontrado
        """
        return self.project_data.metadata_by_field.get(field_name)
    
    def get_record_id_field(self) -> str:
        """
        Obtém o nome do campo de ID do registro.
        
        Returns:
            Nome do campo de record_id
        """
        if self.project_data.metadata:
            return self.project_data.metadata[0].field_name
        return "record_id"
    
    def get_event_field(self) -> str:
        """
        Obtém o nome do campo de evento.
        
        Returns:
            Nome do campo de evento
        """
        return "redcap_event_name"
    
    def is_empty(self, value: any) -> bool:
        """
        Verifica se um valor está vazio.
        
        Args:
            value: Valor a verificar
            
        Returns:
            True se vazio
        """
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        return False
    
    def parse_date(self, value: str) -> Optional[datetime]:
        """
        Tenta fazer parse de uma string de data.
        
        Args:
            value: String com data
            
        Returns:
            datetime ou None se não for possível parsear
        """
        if self.is_empty(value):
            return None
        
        # Tenta formatos conhecidos primeiro
        for fmt in config.DATE_FORMATS:
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        
        # Tenta parser genérico
        try:
            return date_parser.parse(value.strip())
        except (ValueError, TypeError):
            return None
    
    def parse_number(self, value: str) -> Optional[float]:
        """
        Tenta fazer parse de um número.
        
        Args:
            value: String com número
            
        Returns:
            float ou None se não for possível parsear
        """
        if self.is_empty(value):
            return None
        
        try:
            # Remove espaços e troca vírgula por ponto
            clean_value = str(value).strip().replace(",", ".")
            return float(clean_value)
        except (ValueError, TypeError):
            return None
    
    def evaluate_branching_logic(self, logic: str, record: dict) -> bool:
        """
        Avalia branching logic do REDCap.
        
        Args:
            logic: String com a lógica condicional
            record: Registro atual
            
        Returns:
            True se a condição é satisfeita (campo deve aparecer)
        """
        if not logic or not logic.strip():
            return True  # Sem lógica = sempre visível
        
        try:
            # Converte sintaxe REDCap para Python
            python_logic = self._convert_redcap_logic(logic, record)
            # 🛡️ SECURITY FIX: Validação adicional antes do eval
            if "__" in python_logic or "lambda" in python_logic or "import" in python_logic:
                # Log or just return False/True safely
                print(f"Security Warning: Dangerous pattern detected in logic: {python_logic}")
                return False

            # 🛡️ SECURITY FIX: Restringir eval para evitar injeção de código
            # Remove builtins para que comandos como __import__ não funcionem
            return eval(python_logic, {"__builtins__": None}, {})
        except Exception:
            # Se não conseguir avaliar, assume que é válido
            return True
    
    def _convert_redcap_logic(self, logic: str, record: dict) -> str:
        """
        Converte branching logic do REDCap para expressão Python.
        
        Args:
            logic: Lógica REDCap
            record: Registro para obter valores
            
        Returns:
            String com expressão Python
        """
        import re
        
        result = logic
        
        # Substitui operadores
        result = result.replace(" and ", " and ")
        result = result.replace(" or ", " or ")
        result = result.replace("<>", "!=")
        result = result.replace("=", "==").replace("!==", "!=").replace("<==", "<=").replace(">==", ">=")
        
        # Encontra referências a campos [field_name]
        field_pattern = r'\[([^\]]+)\]'
        
        def replace_field(match):
            field_name = match.group(1)
            # Trata checkboxes [field(code)]
            checkbox_match = re.match(r'(\w+)\((\d+)\)', field_name)
            if checkbox_match:
                base_field = checkbox_match.group(1)
                code = checkbox_match.group(2)
                checkbox_field = f"{base_field}___{code}"
                value = record.get(checkbox_field, "")
                return f'"{value}"'
            else:
                value = record.get(field_name, "")
                if isinstance(value, str):
                    return f'"{value}"'
                return str(value) if value else '""'
        
        result = re.sub(field_pattern, replace_field, result)
        
        return result
    
    def determine_priority(self, issue_type: str, field_name: str = "") -> str:
        """
        Determina a prioridade de uma query baseado no tipo.
        
        Args:
            issue_type: Tipo de inconsistência
            field_name: Nome do campo (opcional)
            
        Returns:
            "Alta", "Média" ou "Baixa"
        """
        # Issues de alta prioridade
        high_priority_types = [
            "required_field_empty",
            "physiologically_impossible",
            "inclusion_criteria_violated",
            "exclusion_criteria_violated",
            "death_date_inconsistent",
            "followup_before_baseline",
        ]
        
        # Issues de baixa prioridade
        low_priority_types = [
            "field_should_be_empty",
        ]
        
        # Campos críticos sempre alta prioridade
        if field_name in config.CRITICAL_DATE_FIELDS:
            return "Alta"
        
        if issue_type in high_priority_types:
            return "Alta"
        elif issue_type in low_priority_types:
            return "Baixa"
        else:
            return "Média"
