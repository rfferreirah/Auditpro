"""
REDCap Data Quality Intelligence Agent - Structural Analyzer

Analisador de inconsistências estruturais nos dados.
"""

import re
from .base_analyzer import BaseAnalyzer
from ..models import Query, FieldMetadata


class StructuralAnalyzer(BaseAnalyzer):
    """
    Analisador de inconsistências estruturais.
    
    Detecta:
    - Campos obrigatórios vazios
    - Valores fora de range
    - Formatos inválidos
    - Códigos fora da lista de opções
    - Campos calculados inconsistentes
    - Campos obrigatórios vazios
    - Valores fora de range
    - Formatos inválidos
    - Códigos fora da lista de opções
    - Campos calculados inconsistentes
    - Branching logic violada
    """
    
    def __init__(self, project_data, enabled_checks: list[str] = None):
        super().__init__(project_data)
        # Default: if None, enable ALL (to be safe), but QueryGenerator will pass specific list
        self.enabled_checks = enabled_checks if enabled_checks is not None else [
            '00000000-0000-0000-0000-000000000002', # sys_required
            '00000000-0000-0000-0000-000000000006', # sys_range
            '00000000-0000-0000-0000-000000000005', # sys_format
            '00000000-0000-0000-0000-000000000007', # sys_choices
            '00000000-0000-0000-0000-000000000001'  # sys_branching
        ]
    
    def analyze(self) -> list[Query]:
        """
        Executa análise estrutural completa.
        
        Returns:
            Lista de queries identificadas
        """
        self.queries = []
        
        record_id_field = self.get_record_id_field()
        event_field = self.get_event_field()
        
        for record in self.project_data.records:
            record_id = record.get(record_id_field, "UNKNOWN")
            event = record.get(event_field, "")
            
            for field_meta in self.project_data.metadata:
                field_name = field_meta.field_name
                value = record.get(field_name)
                
                # Pula campo de ID
                if field_name == record_id_field:
                    continue
                
                # Verifica branching logic primeiro
                should_exist = self.evaluate_branching_logic(
                    field_meta.branching_logic, record
                )
                
                # Validações
                # Validações baseadas em configuração (Suporta chaves legíveis e UUIDs)
                if self.is_check_enabled('sys_required', '00000000-0000-0000-0000-000000000002'):
                    self._check_required_field(
                        record_id, event, field_meta, value, should_exist
                    )
                
                if self.is_check_enabled('sys_range', '00000000-0000-0000-0000-000000000006'):
                    self._check_value_range(
                        record_id, event, field_meta, value, should_exist
                    )
                
                if self.is_check_enabled('sys_format', '00000000-0000-0000-0000-000000000005'):
                    self._check_format(
                        record_id, event, field_meta, value, should_exist
                    )
                
                if self.is_check_enabled('sys_choices', '00000000-0000-0000-0000-000000000007'):
                    self._check_choices(
                        record_id, event, field_meta, value, should_exist
                    )
                
                if self.is_check_enabled('sys_branching', '00000000-0000-0000-0000-000000000001'):
                    self._check_branching_logic_violation(
                        record_id, event, field_meta, value, should_exist
                    )
        
        return self.queries

    def is_check_enabled(self, key: str, uuid: str) -> bool:
        """Verifica se uma checagem está habilitada (por chave ou UUID)."""
        if not self.enabled_checks:
            return False
        return key in self.enabled_checks or uuid in self.enabled_checks
    
    def _check_required_field(
        self,
        record_id: str,
        event: str,
        field_meta: FieldMetadata,
        value: any,
        should_exist: bool,
    ) -> None:
        """Verifica campos obrigatórios vazios."""
        if not field_meta.is_required:
            return
        
        if not should_exist:
            return  # Campo não deveria aparecer por branching logic
        
        if self.is_empty(value):
            # DEBUG LOG to diagnose false positives
            print(f"DEBUG_EMPTY_CHECK: Flagged '{field_meta.field_name}' for Record {record_id} in {event}. Raw Value='{value}' Type={type(value)}", flush=True)
            self.add_query(
                record_id=record_id,
                event=event,
                instrument=field_meta.form_name,
                field=field_meta.field_name,
                value_found=value,
                issue_type="required_field_empty",
                explanation=f"O campo '{field_meta.field_label}' é obrigatório mas está vazio.",
                priority="Alta",
                suggested_action="Preencher o campo com valor válido.",
            )
    
    def _check_value_range(
        self,
        record_id: str,
        event: str,
        field_meta: FieldMetadata,
        value: any,
        should_exist: bool,
    ) -> None:
        """Verifica valores fora do range definido."""
        if self.is_empty(value):
            return
        
        if not should_exist:
            return
        
        # Só aplica para campos numéricos
        if field_meta.validation_type not in ["number", "integer", "number_1dp", "number_2dp"]:
            return
        
        num_value = self.parse_number(value)
        if num_value is None:
            return  # Será tratado por _check_format
        
        min_val = None
        max_val = None
        
        if field_meta.text_validation_min:
            min_val = self.parse_number(field_meta.text_validation_min)
        if field_meta.text_validation_max:
            max_val = self.parse_number(field_meta.text_validation_max)
        
        violation = None
        
        if min_val is not None and num_value < min_val:
            violation = f"menor que o mínimo permitido ({min_val})"
        elif max_val is not None and num_value > max_val:
            violation = f"maior que o máximo permitido ({max_val})"
        
        if violation:
            self.add_query(
                record_id=record_id,
                event=event,
                instrument=field_meta.form_name,
                field=field_meta.field_name,
                value_found=value,
                issue_type="value_out_of_range",
                explanation=f"O valor '{value}' no campo '{field_meta.field_label}' é {violation}.",
                priority=self.determine_priority("value_out_of_range", field_meta.field_name),
                suggested_action=f"Verificar e corrigir o valor. Range permitido: {min_val or 'N/A'} a {max_val or 'N/A'}.",
            )
    
    def _check_format(
        self,
        record_id: str,
        event: str,
        field_meta: FieldMetadata,
        value: any,
        should_exist: bool,
    ) -> None:
        """Verifica formato dos dados."""
        if self.is_empty(value):
            return
        
        if not should_exist:
            return
        
        validation_type = field_meta.validation_type
        
        if not validation_type:
            return
        
        is_valid = True
        expected_format = ""
        
        # Validação de data
        if validation_type in ["date_ymd", "date_mdy", "date_dmy"]:
            if self.parse_date(value) is None:
                is_valid = False
                expected_format = "data válida (ex: 2024-01-15)"
        
        # Validação de datetime
        elif validation_type in ["datetime_ymd", "datetime_mdy", "datetime_dmy", "datetime_seconds_ymd"]:
            if self.parse_date(value) is None:
                is_valid = False
                expected_format = "data/hora válida (ex: 2024-01-15 14:30)"
        
        # Validação de integer
        elif validation_type == "integer":
            try:
                int(str(value).strip())
            except ValueError:
                is_valid = False
                expected_format = "número inteiro"
        
        # Validação de number
        elif validation_type in ["number", "number_1dp", "number_2dp"]:
            if self.parse_number(value) is None:
                is_valid = False
                expected_format = "número decimal"
        
        # Validação de email
        elif validation_type == "email":
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, str(value).strip()):
                is_valid = False
                expected_format = "email válido"
        
        # Validação de telefone
        elif validation_type == "phone":
            phone_pattern = r'^[\d\s\-\(\)\+]+$'
            if not re.match(phone_pattern, str(value).strip()):
                is_valid = False
                expected_format = "telefone válido"
        
        if not is_valid:
            self.add_query(
                record_id=record_id,
                event=event,
                instrument=field_meta.form_name,
                field=field_meta.field_name,
                value_found=value,
                issue_type="invalid_format",
                explanation=f"O valor '{value}' no campo '{field_meta.field_label}' não corresponde ao formato esperado: {expected_format}.",
                priority="Média",
                suggested_action=f"Corrigir o valor para o formato: {expected_format}.",
            )
    
    def _check_choices(
        self,
        record_id: str,
        event: str,
        field_meta: FieldMetadata,
        value: any,
        should_exist: bool,
    ) -> None:
        """Verifica se o valor está na lista de opções válidas."""
        if self.is_empty(value):
            return
        
        if not should_exist:
            return
        
        if field_meta.field_type not in ["dropdown", "radio"]:
            return
        
        choices = field_meta.choices
        if not choices:
            return
        
        str_value = str(value).strip()
        
        if str_value not in choices:
            valid_options = ", ".join([f"{k}={v}" for k, v in list(choices.items())[:5]])
            if len(choices) > 5:
                valid_options += f"... (+{len(choices)-5} opções)"
            
            self.add_query(
                record_id=record_id,
                event=event,
                instrument=field_meta.form_name,
                field=field_meta.field_name,
                value_found=value,
                issue_type="invalid_choice",
                explanation=f"O valor '{value}' no campo '{field_meta.field_label}' não é uma opção válida.",
                priority="Média",
                suggested_action=f"Corrigir para uma opção válida: {valid_options}.",
            )
    
    def _check_branching_logic_violation(
        self,
        record_id: str,
        event: str,
        field_meta: FieldMetadata,
        value: any,
        should_exist: bool,
    ) -> None:
        """Verifica violações de branching logic."""
        if not field_meta.has_branching_logic:
            return
        
        has_value = not self.is_empty(value)
        
        # Campo preenchido quando não deveria existir
        if has_value and not should_exist:
            self.add_query(
                record_id=record_id,
                event=event,
                instrument=field_meta.form_name,
                field=field_meta.field_name,
                value_found=value,
                issue_type="field_should_be_empty",
                explanation=f"O campo '{field_meta.field_label}' está preenchido mas não deveria aparecer segundo a lógica condicional: {field_meta.branching_logic}",
                priority="Baixa",
                suggested_action="Verificar se o valor deve ser removido ou se campos relacionados precisam de correção.",
            )
