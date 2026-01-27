"""
REDCap Data Quality Intelligence Agent - Clinical Analyzer

Analisador de inconsistências clínicas nos dados.
"""

from typing import Optional

from .base_analyzer import BaseAnalyzer
from ..models import Query
import config
from ..rules_manager import rules_manager # Import para verificar duplicatas

class ClinicalAnalyzer(BaseAnalyzer):
    """
    Analisador de inconsistências clínicas.
    
    Detecta:
    - Valores fisiologicamente impossíveis
    - Critérios de inclusão/exclusão violados
    - Classificações clínicas incorretas
    """
    
    def __init__(self, project_data, custom_limits: Optional[dict] = None):
        """
        Inicializa o analisador clínico.
        
        Args:
            project_data: Dados do projeto
            custom_limits: Limites clínicos customizados (opcional)
        """
        super().__init__(project_data)
        self.clinical_limits = {**config.CLINICAL_LIMITS}
        if custom_limits:
            self.clinical_limits.update(custom_limits)
    
    def analyze(self) -> list[Query]:
        """
        Executa análise clínica completa.
        
        Returns:
            Lista de queries identificadas
        """
        self.queries = []
        
        record_id_field = self.get_record_id_field()
        event_field = self.get_event_field()
        
        for record in self.project_data.records:
            record_id = record.get(record_id_field, "UNKNOWN")
            event = record.get(event_field, "")
            
            self._check_physiological_values(record_id, event, record)
            self._check_blood_pressure_consistency(record_id, event, record)
            self._check_bmi_consistency(record_id, event, record)
            self._check_age_consistency(record_id, event, record)
        
        return self.queries
    
    def _find_field_by_pattern(self, record: dict, patterns: list[str]) -> Optional[tuple[str, any]]:
        """
        Encontra um campo por padrões de nome.
        
        Args:
            record: Registro atual
            patterns: Lista de padrões a buscar
            
        Returns:
            Tupla (field_name, value) ou None
        """
        for field_name, value in record.items():
            field_lower = field_name.lower()
            for pattern in patterns:
                if pattern.lower() in field_lower:
                    if not self.is_empty(value):
                        return (field_name, value)
        return None
    
    def _check_physiological_values(self, record_id: str, event: str, record: dict) -> None:
        """Verifica valores contra limites fisiológicos."""
        for field_name, value in record.items():
            if self.is_empty(value):
                continue
            
            num_value = self.parse_number(value)
            if num_value is None:
                continue
            
            # Busca correspondência com limites conhecidos
            field_lower = field_name.lower()
            
            for limit_key, limits in self.clinical_limits.items():
                if limit_key.lower() in field_lower or field_lower in limit_key.lower():
                    min_val = limits.get("min")
                    max_val = limits.get("max")
                    unit = limits.get("unit", "")
                    
                    if min_val is not None and num_value < min_val:
                        field_meta = self.get_field_metadata(field_name)
                        self.add_query(
                            record_id=record_id,
                            event=event,
                            instrument=field_meta.form_name if field_meta else "N/A",
                            field=field_name,
                            value_found=value,
                            issue_type="physiologically_impossible",
                            explanation=f"O valor {value} {unit} é fisiologicamente impossível (mínimo esperado: {min_val} {unit}).",
                            priority="Alta",
                            suggested_action=f"Verificar entrada de dados. Valor deve estar entre {min_val} e {max_val} {unit}.",
                        )
                    elif max_val is not None and num_value > max_val:
                        field_meta = self.get_field_metadata(field_name)
                        self.add_query(
                            record_id=record_id,
                            event=event,
                            instrument=field_meta.form_name if field_meta else "N/A",
                            field=field_name,
                            value_found=value,
                            issue_type="physiologically_impossible",
                            explanation=f"O valor {value} {unit} é fisiologicamente impossível (máximo esperado: {max_val} {unit}).",
                            priority="Alta",
                            suggested_action=f"Verificar entrada de dados. Valor deve estar entre {min_val} e {max_val} {unit}.",
                        )
                    break
    
    def _check_blood_pressure_consistency(self, record_id: str, event: str, record: dict) -> None:
        """Verifica consistência entre pressão sistólica e diastólica."""
        # Busca campos de PA
        systolic_patterns = ["systolic", "pas", "sistolica", "sbp"]
        diastolic_patterns = ["diastolic", "pad", "diastolica", "dbp"]
        
        systolic = self._find_field_by_pattern(record, systolic_patterns)
        diastolic = self._find_field_by_pattern(record, diastolic_patterns)
        
        if not systolic or not diastolic:
            return
        
        sys_field, sys_value = systolic
        dia_field, dia_value = diastolic
        
        sys_num = self.parse_number(sys_value)
        dia_num = self.parse_number(dia_value)
        
        if sys_num is None or dia_num is None:
            return
        
        # Diastólica deve ser menor que sistólica
        if dia_num >= sys_num:
            field_meta = self.get_field_metadata(dia_field)
            self.add_query(
                record_id=record_id,
                event=event,
                instrument=field_meta.form_name if field_meta else "N/A",
                field=dia_field,
                value_found=f"Sistólica: {sys_value}, Diastólica: {dia_value}",
                issue_type="clinical_classification_mismatch",
                explanation=f"Pressão diastólica ({dia_value} mmHg) é maior ou igual à sistólica ({sys_value} mmHg), o que é clinicamente impossível.",
                priority="Alta",
                suggested_action="Verificar se os valores foram invertidos ou se há erro de digitação.",
            )
        
        # Diferença muito pequena (< 10 mmHg) é suspeita
        elif sys_num - dia_num < 10:
            field_meta = self.get_field_metadata(dia_field)
            self.add_query(
                record_id=record_id,
                event=event,
                instrument=field_meta.form_name if field_meta else "N/A",
                field=dia_field,
                value_found=f"Diferencial: {sys_num - dia_num} mmHg",
                issue_type="clinical_classification_mismatch",
                explanation=f"Pressão diferencial muito baixa ({sys_num - dia_num} mmHg). Diferencial < 10 mmHg é altamente improvável.",
                priority="Média",
                suggested_action="Verificar medição da pressão arterial.",
            )
    
    def _check_bmi_consistency(self, record_id: str, event: str, record: dict) -> None:
        """Verifica consistência do IMC com peso e altura."""
        # Busca campos
        weight_patterns = ["weight", "peso", "wt"]
        height_patterns = ["height", "altura", "estatura"]  # Removed 'ht' as it matches 'weight'
        bmi_patterns = ["bmi", "imc"]
        
        weight = self._find_field_by_pattern(record, weight_patterns)
        height = self._find_field_by_pattern(record, height_patterns)
        bmi = self._find_field_by_pattern(record, bmi_patterns)
        
        if not weight or not height:
            return
        
        weight_num = self.parse_number(weight[1])
        height_num = self.parse_number(height[1])
        
        if weight_num is None or height_num is None:
            return
        
        # Converte altura para metros se estiver em cm
        if height_num > 3:  # Provavelmente em cm
            height_m = height_num / 100
        else:
            height_m = height_num
        
        if height_m <= 0:
            return
        
        calculated_bmi = weight_num / (height_m ** 2)
        
        # Se há campo de IMC preenchido, verifica se confere
        if bmi:
            bmi_num = self.parse_number(bmi[1])
            if bmi_num is not None:
                diff = abs(calculated_bmi - bmi_num)
                if diff > 1:  # Tolerância de 1 unidade
                    field_meta = self.get_field_metadata(bmi[0])
                    self.add_query(
                        record_id=record_id,
                        event=event,
                        instrument=field_meta.form_name if field_meta else "N/A",
                        field=bmi[0],
                        value_found=f"Registrado: {bmi[1]}, Calculado: {calculated_bmi:.1f}",
                        issue_type="calculated_field_mismatch",
                        explanation=f"O IMC registrado ({bmi[1]}) difere do calculado ({calculated_bmi:.1f}) baseado em peso ({weight[1]}) e altura ({height[1]}).",
                        priority="Média",
                        suggested_action="Verificar peso e altura, ou recalcular o IMC.",
                    )
        
        # Verifica se IMC está em faixa plausível
        if calculated_bmi < 10 or calculated_bmi > 80:
            field_meta = self.get_field_metadata(weight[0])
            self.add_query(
                record_id=record_id,
                event=event,
                instrument=field_meta.form_name if field_meta else "N/A",
                field=weight[0],
                value_found=f"Peso: {weight[1]}, Altura: {height[1]}, IMC: {calculated_bmi:.1f}",
                issue_type="physiologically_impossible",
                explanation=f"O IMC calculado ({calculated_bmi:.1f}) está fora da faixa fisiológica plausível (10-80).",
                priority="Alta",
                suggested_action="Verificar os valores de peso e altura.",
            )
    
    def _check_age_consistency(self, record_id: str, event: str, record: dict) -> None:
        """Verifica consistência de idade."""
        # Busca campos de idade e data de nascimento
        age_patterns = ["age", "idade"]
        dob_patterns = ["birth", "nascimento", "dob", "dtn"]
        
        age = self._find_field_by_pattern(record, age_patterns)
        dob = self._find_field_by_pattern(record, dob_patterns)
        
        if age:
            age_num = self.parse_number(age[1])
            if age_num is not None:
                # Idade negativa
                if age_num < 0:
                    field_meta = self.get_field_metadata(age[0])
                    self.add_query(
                        record_id=record_id,
                        event=event,
                        instrument=field_meta.form_name if field_meta else "N/A",
                        field=age[0],
                        value_found=age[1],
                        issue_type="physiologically_impossible",
                        explanation="Idade negativa é impossível.",
                        priority="Alta",
                        suggested_action="Corrigir valor da idade.",
                    )
                # Idade muito alta
                elif age_num > 120:
                    field_meta = self.get_field_metadata(age[0])
                    self.add_query(
                        record_id=record_id,
                        event=event,
                        instrument=field_meta.form_name if field_meta else "N/A",
                        field=age[0],
                        value_found=age[1],
                        issue_type="physiologically_impossible",
                        explanation=f"Idade {age_num} anos é altamente improvável (> 120 anos).",
                        priority="Alta",
                        suggested_action="Verificar data de nascimento e idade.",
                    )
        
        # Se temos data de nascimento e data de visita, podemos verificar
        if dob:
            dob_date = self.parse_date(dob[1])
            if dob_date:
                from datetime import datetime
                today = datetime.now()
                
                if dob_date > today:
                    field_meta = self.get_field_metadata(dob[0])
                    self.add_query(
                        record_id=record_id,
                        event=event,
                        instrument=field_meta.form_name if field_meta else "N/A",
                        field=dob[0],
                        value_found=dob[1],
                        issue_type="physiologically_impossible",
                        explanation="Data de nascimento está no futuro.",
                        priority="Alta",
                        suggested_action="Corrigir data de nascimento.",
                    )
