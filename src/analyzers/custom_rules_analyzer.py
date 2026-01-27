"""
REDCap Data Quality Intelligence Agent - Custom Rules Analyzer

Analisador que aplica regras customizadas definidas pelo usuário.
"""

import re
from typing import Optional
from collections import Counter

from .base_analyzer import BaseAnalyzer
from ..models import Query
from ..rules_manager import rules_manager


class CustomRulesAnalyzer(BaseAnalyzer):
    """
    Analisador de regras customizadas.
    
    Aplica regras definidas pelo usuário via interface web.
    Suporta tipos:
    - range: valor entre min e max
    - comparison: comparação simples (=, !=, <, >, <=, >=)
    - cross_field: comparação entre dois campos
    - regex: expressão regular
    - condition: lógica condicional (SE campo=valor ENTÃO ...)
    - uniqueness: verifica duplicidade de valores
    """
    
    def __init__(self, project_data, user_id=None, access_token=None):
        super().__init__(project_data)
        self.user_id = user_id
        self.access_token = access_token
    
    def analyze(self) -> list[Query]:
        """
        Executa análise com regras customizadas.
        
        Returns:
            Lista de queries identificadas
        """
        self.queries = []
        
        # Carrega regras habilitadas para o usuário
        rules = rules_manager.get_enabled_rules(self.user_id, self.access_token)
        
        if not rules:
            print(f"DEBUG: No enabled rules found for user_id={self.user_id} (token={'present' if self.access_token else 'MISSING'}).")
            return self.queries
            
        print(f"DEBUG: Analying {len(rules)} custom rules.")
        
        # Otimização para Unicidade: Pré-calcula contagem de valores para regras de 'uniqueness'
        uniqueness_maps = {}
        for rule in rules:
            if rule.rule_type == "uniqueness":
                field_values = [
                    str(r.get(rule.field)).strip() 
                    for r in self.project_data.records 
                    if not self.is_empty(r.get(rule.field))
                ]
                count = Counter(field_values)
                uniqueness_maps[rule.field] = count
                print(f"DEBUG: Uniqueness map for '{rule.field}': found {len(field_values)} values, {len(count)} unique. Duplicates: {[k for k,v in count.items() if v > 1]}")

        record_id_field = self.get_record_id_field()
        event_field = self.get_event_field()
        
        for record in self.project_data.records:
            record_id = record.get(record_id_field, "UNKNOWN")
            event = record.get(event_field, "")
            
            for rule in rules:
                if rule.field == '_ALL_':
                    # Apply to ALL fields in record
                    # We must iterate over METADATA to catch empty fields that might not be in the record dict
                    if self.project_data.metadata:
                        fields_to_check = [m.field_name for m in self.project_data.metadata]
                    else:
                        # Fallback if metadata is not available (should rarely happen)
                        fields_to_check = list(record.keys())

                    for field_name in fields_to_check:
                        # Skip system fields
                        if field_name in ['redcap_event_name', 'redcap_repeat_instrument', 'redcap_repeat_instance']:
                            continue
                            
                        # Apply rule
                        self._apply_rule(record_id, event, record, rule, uniqueness_maps, field_override=field_name)
                else:
                    self._apply_rule(record_id, event, record, rule, uniqueness_maps)
        
        return self.queries
    
    def _apply_rule(self, record_id: str, event: str, record: dict, rule, uniqueness_maps=None, field_override=None) -> None:
        """Aplica uma regra a um registro."""
        
        target_field = field_override if field_override else rule.field
        field_value = record.get(target_field)
        
        # Pula campos vazios, exceto se:
        # 1. O operador for explicitamente para checar vazio/não vazio
        # 2. A regra for do tipo 'condition' (pois a condição pode ser justamente sobre estar vazio)
        is_empty_check = rule.operator in ["empty", "not_empty"]
        is_condition_rule = rule.rule_type == "condition"
        
        if self.is_empty(field_value) and not is_empty_check and not is_condition_rule:
            return
        
        # Obtém metadata do campo para nome do instrumento
        field_meta = self.get_field_metadata(target_field)
        instrument = field_meta.form_name if field_meta else "unknown"
        
        violation = False
        
        if rule.rule_type == "range":
            violation = self._check_range(field_value, rule)
        elif rule.rule_type == "comparison":
            violation = self._check_comparison(field_value, rule)
        elif rule.rule_type == "cross_field":
            violation = self._check_cross_field(record, rule, target_field)
        elif rule.rule_type == "regex":
            violation = self._check_regex(field_value, rule)
        elif rule.rule_type == "condition":
            violation = self._check_condition(record, rule, target_field)
        elif rule.rule_type == "uniqueness":
            violation = self._check_uniqueness(field_value, rule, uniqueness_maps)
        
        if violation:
            self.add_query(
                record_id=record_id,
                event=event,
                instrument=instrument,
                field=target_field,
                value_found=field_value,
                issue_type="custom_rule_violation",
                explanation=rule.message or f"Violação da regra: {rule.name}",
                priority=rule.priority,
                suggested_action=f"Verificar campo conforme regra customizada: {rule.name}",
            )
    
    def _check_range(self, value, rule) -> bool:
        """Verifica se valor está fora do range."""
        num_value = self.parse_number(value)
        if num_value is None:
            return False
        
        # value pode ser dict {min, max} ou lista [min, max]
        if isinstance(rule.value, dict):
            min_val = rule.value.get("min")
            max_val = rule.value.get("max")
        elif isinstance(rule.value, list) and len(rule.value) >= 2:
            min_val, max_val = rule.value[0], rule.value[1]
        else:
            return False
        
        if min_val is not None and num_value < min_val:
            return True
        if max_val is not None and num_value > max_val:
            return True
        
        return False
    
    def _check_comparison(self, value, rule) -> bool:
        """Verifica comparação simples."""
        operator = rule.operator
        compare_value = rule.value
        
        # Tenta converter para número se possível
        num_value = self.parse_number(value)
        num_compare = self.parse_number(compare_value) if compare_value is not None else None
        
        # Se ambos são números, compara numericamente
        if num_value is not None and num_compare is not None:
            return self._compare_values(num_value, operator, num_compare)
        
        # Comparação como string
        str_value = str(value).strip() if value is not None else ""
        str_compare = str(compare_value).strip() if compare_value is not None else ""
        
        if operator == "=":
            return str_value != str_compare
        elif operator == "!=":
            return str_value == str_compare
        elif operator == "empty":
            return not self.is_empty(value)  # Viola se NÃO estiver vazio
        elif operator == "not_empty":
            return self.is_empty(value)  # Viola se estiver vazio
        elif operator == "contains":
            return str_compare not in str_value
        
        return False
    
    def _compare_values(self, value, operator: str, compare_value) -> bool:
        """Compara valores numéricos. Retorna True se VIOLA a regra."""
        if operator == "=":
            return value != compare_value
        elif operator == "!=":
            return value == compare_value
        elif operator == "<":
            return not (value < compare_value)  # Viola se NÃO for menor
        elif operator == ">":
            return not (value > compare_value)
        elif operator == "<=":
            return not (value <= compare_value)
        elif operator == ">=":
            return not (value >= compare_value)
        return False
    
    def _check_cross_field(self, record: dict, rule, target_field: str = None) -> bool:
        """Verifica comparação entre dois campos."""
        if not rule.field2:
            return False
        
        actual_field = target_field if target_field else rule.field
        
        value1 = record.get(actual_field)
        value2 = record.get(rule.field2)
        
        if self.is_empty(value1) or self.is_empty(value2):
            return False
        
        # Tenta como datas primeiro
        date1 = self.parse_date(value1)
        date2 = self.parse_date(value2)
        
        if date1 and date2:
            return self._compare_values_cross(date1, rule.operator, date2)
        
        # Tenta como números
        num1 = self.parse_number(value1)
        num2 = self.parse_number(value2)
        
        if num1 is not None and num2 is not None:
            return self._compare_values_cross(num1, rule.operator, num2)
        
        # Compara como strings
        return self._compare_values_cross(str(value1), rule.operator, str(value2))
    
    def _compare_values_cross(self, value1, operator: str, value2) -> bool:
        """Compara dois valores. Retorna True se VIOLA a expectativa."""
        # Aqui a lógica é: a regra define o que DEVERIA ser verdade
        # Se não for, é uma violação
        if operator == ">":
            return not (value1 > value2)
        elif operator == "<":
            return not (value1 < value2)
        elif operator == ">=":
            return not (value1 >= value2)
        elif operator == "<=":
            return not (value1 <= value2)
        elif operator == "=":
            return value1 != value2
        elif operator == "!=":
            return value1 == value2
        return False
    
    def _check_regex(self, value, rule) -> bool:
        """Verifica se valor corresponde à expressão regular."""
        if self.is_empty(value):
            return False
        
        try:
            pattern = rule.value
            match = re.match(pattern, str(value))
            
            if rule.operator == "matches":
                return match is None  # Viola se NÃO corresponde
            elif rule.operator == "not_matches":
                return match is not None  # Viola se corresponde
        except re.error:
            return False
        
        return False
    
    def _check_condition(self, record: dict, rule, target_field: str = None) -> bool:
        """
        Verifica regra condicional (SE-ENTÃO).
        """
        if not isinstance(rule.value, dict):
            return False
        
        condition = rule.value
        actual_field = target_field if target_field else rule.field
        
        # Verifica a condição IF
        # Se if_field não estiver definido ou for igual ao field original da regra (_ALL_ ou outro),
        # usamos o actual_field (campo atual da iteração)
        if_field_config = condition.get("if_field")
        if_field = if_field_config if if_field_config and if_field_config != rule.field else actual_field
        
        if_operator = condition.get("if_operator", "=")
        if_value = condition.get("if_value")
        
        field_value = record.get(if_field)
        
        # Se a condição IF não é satisfeita, não há violação
        if not self._condition_matches(field_value, if_operator, if_value):
            return False
        
        # A condição IF foi satisfeita, agora verifica THEN
        then_field_config = condition.get("then_field")
        # Mesma lógica para o then_field
        then_field = then_field_config if then_field_config and then_field_config != rule.field else (rule.field2 or actual_field)
        
        then_operator = condition.get("then_operator", "=")
        then_value = condition.get("then_value")
        
        then_field_value = record.get(then_field)
        
        # Viola se o THEN não é satisfeito
        return not self._condition_matches(then_field_value, then_operator, then_value)
    
    def _check_uniqueness(self, value, rule, uniqueness_maps) -> bool:
        """Verifica se o valor é único no projeto."""
        if not uniqueness_maps or rule.field not in uniqueness_maps:
            return False
        
        if self.is_empty(value):
            return False
            
        str_val = str(value).strip()
        count = uniqueness_maps[rule.field].get(str_val, 0)
        
        # Se contagem > 1, existe duplicidade
        if count > 1:
            # Atualiza mensagem se necessário
            if not rule.message:
                rule.message = f"Valor duplicado encontrado '{value}' ({count} ocorrências)"
            print(f"DEBUG: Validating uniqueness for '{str_val}': Count={count} -> VIOLATION")
            return True
            
        return False
        
    def _condition_matches(self, value, operator: str, expected) -> bool:
        """Verifica se uma condição é satisfeita."""
        str_value = str(value).strip() if value is not None else ""
        str_expected = str(expected).strip() if expected is not None else ""
        
        if operator == "=":
            return str_value == str_expected
        elif operator == "!=":
            return str_value != str_expected
        elif operator == "empty":
            return self.is_empty(value)
        elif operator == "not_empty":
            return not self.is_empty(value)
        
        # Comparações numéricas
        num_value = self.parse_number(value)
        num_expected = self.parse_number(expected)
        
        if num_value is not None and num_expected is not None:
            if operator == "<":
                return num_value < num_expected
            elif operator == ">":
                return num_value > num_expected
            elif operator == "<=":
                return num_value <= num_expected
            elif operator == ">=":
                return num_value >= num_expected
        
        return False
