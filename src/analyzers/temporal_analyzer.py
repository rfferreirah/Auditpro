"""
REDCap Data Quality Intelligence Agent - Temporal Analyzer

Analisador de inconsistências temporais nos dados.
"""

from datetime import datetime
from typing import Optional
from collections import defaultdict

from .base_analyzer import BaseAnalyzer
from ..models import Query
import config


class TemporalAnalyzer(BaseAnalyzer):
    """
    Analisador de inconsistências temporais.
    
    Detecta:
    - Datas fora de ordem cronológica
    - Follow-up anterior à baseline
    - Eventos adversos fora da timeline
    - Data de óbito inconsistente
    - Sequências de repeating instruments quebradas
    """
    
    def analyze(self) -> list[Query]:
        """
        Executa análise temporal completa.
        
        Returns:
            Lista de queries identificadas
        """
        self.queries = []
        
        # Agrupa registros por participante
        records_by_participant = self._group_records_by_participant()
        
        for participant_id, records in records_by_participant.items():
            self._check_date_order(participant_id, records)
            self._check_baseline_vs_followup(participant_id, records)
            self._check_death_date(participant_id, records)
            self._check_event_timeline(participant_id, records)
        
        # Verifica sequências de repeating instruments
        self._check_repeating_sequences()
        
        return self.queries
    
    def _group_records_by_participant(self) -> dict[str, list[dict]]:
        """Agrupa registros por participante."""
        record_id_field = self.get_record_id_field()
        grouped = defaultdict(list)
        
        for record in self.project_data.records:
            participant_id = record.get(record_id_field, "UNKNOWN")
            grouped[participant_id].append(record)
        
        return dict(grouped)
    
    def _find_date_fields(self) -> list[str]:
        """Encontra todos os campos de data no projeto."""
        date_fields = []
        
        for field_meta in self.project_data.metadata:
            validation = field_meta.validation_type
            if validation and "date" in validation.lower():
                date_fields.append(field_meta.field_name)
        
        return date_fields
    
    def _find_baseline_date(self, records: list[dict]) -> Optional[tuple[datetime, str, dict]]:
        """
        Encontra a data de baseline de um participante.
        
        Returns:
            Tupla (datetime, field_name, record) ou None
        """
        date_fields = self._find_date_fields()
        
        # Primeiro tenta campos conhecidos de baseline
        for field_name in config.BASELINE_DATE_FIELDS:
            for record in records:
                value = record.get(field_name)
                if value:
                    parsed = self.parse_date(value)
                    if parsed:
                        return (parsed, field_name, record)
        
        # Se não encontrar, usa a data mais antiga
        earliest = None
        earliest_field = None
        earliest_record = None
        
        for record in records:
            for field_name in date_fields:
                value = record.get(field_name)
                if value:
                    parsed = self.parse_date(value)
                    if parsed:
                        if earliest is None or parsed < earliest:
                            earliest = parsed
                            earliest_field = field_name
                            earliest_record = record
        
        if earliest:
            return (earliest, earliest_field, earliest_record)
        return None
    
    def _check_date_order(self, participant_id: str, records: list[dict]) -> None:
        """Verifica ordem cronológica geral das datas."""
        if not self.project_data.events:
            return  # Não é longitudinal
        
        event_field = self.get_event_field()
        date_fields = self._find_date_fields()
        
        # Mapa de ordem dos eventos
        event_order = {event.unique_event_name: idx for idx, event in enumerate(self.project_data.events)}
        
        # Coleta datas por evento
        event_dates: dict[str, list[tuple[datetime, str, dict]]] = defaultdict(list)
        
        for record in records:
            event_name = record.get(event_field, "")
            
            for field_name in date_fields:
                value = record.get(field_name)
                if value:
                    parsed = self.parse_date(value)
                    if parsed:
                        event_dates[event_name].append((parsed, field_name, record))
        
        # Verifica ordem entre eventos consecutivos
        sorted_events = sorted(event_dates.keys(), key=lambda e: event_order.get(e, 999))
        
        for i in range(len(sorted_events) - 1):
            curr_event = sorted_events[i]
            next_event = sorted_events[i + 1]
            
            if not event_dates[curr_event] or not event_dates[next_event]:
                continue
            
            # Encontra a data mais tardia do evento atual e mais cedo do próximo
            latest_curr = max(d[0] for d in event_dates[curr_event])
            earliest_next = min(d[0] for d in event_dates[next_event])
            
            if earliest_next < latest_curr:
                # Encontra qual campo específico
                for date_val, field_name, record in event_dates[next_event]:
                    if date_val < latest_curr:
                        field_meta = self.get_field_metadata(field_name)
                        self.add_query(
                            record_id=participant_id,
                            event=next_event,
                            instrument=field_meta.form_name if field_meta else "N/A",
                            field=field_name,
                            value_found=record.get(field_name),
                            issue_type="date_out_of_order",
                            explanation=f"A data '{record.get(field_name)}' no evento '{next_event}' é anterior à data mais recente do evento anterior '{curr_event}' ({latest_curr.strftime('%Y-%m-%d')}).",
                            priority="Alta",
                            suggested_action="Verificar se as datas estão corretas ou se os eventos foram registrados no formulário errado.",
                        )
    
    def _check_baseline_vs_followup(self, participant_id: str, records: list[dict]) -> None:
        """Verifica se datas de follow-up são posteriores à baseline."""
        baseline_info = self._find_baseline_date(records)
        if not baseline_info:
            return
        
        baseline_date, baseline_field, baseline_record = baseline_info
        date_fields = self._find_date_fields()
        event_field = self.get_event_field()
        
        for record in records:
            event = record.get(event_field, "")
            
            # Pula o próprio registro de baseline
            if record is baseline_record:
                continue
            
            for field_name in date_fields:
                # Pula campos de baseline conhecidos
                if field_name in config.BASELINE_DATE_FIELDS:
                    continue
                
                value = record.get(field_name)
                if not value:
                    continue
                
                parsed = self.parse_date(value)
                if parsed and parsed < baseline_date:
                    field_meta = self.get_field_metadata(field_name)
                    self.add_query(
                        record_id=participant_id,
                        event=event,
                        instrument=field_meta.form_name if field_meta else "N/A",
                        field=field_name,
                        value_found=value,
                        issue_type="followup_before_baseline",
                        explanation=f"A data '{value}' é anterior à data de baseline ({baseline_date.strftime('%Y-%m-%d')} em '{baseline_field}').",
                        priority="Alta",
                        suggested_action="Verificar se a data está correta. Datas de follow-up devem ser posteriores à baseline.",
                    )
    
    def _check_death_date(self, participant_id: str, records: list[dict]) -> None:
        """Verifica consistência de data de óbito."""
        event_field = self.get_event_field()
        date_fields = self._find_date_fields()
        
        # Encontra data de óbito
        death_date = None
        death_field = None

        
        for field_name in config.CRITICAL_DATE_FIELDS:
            if "death" in field_name.lower() or "obito" in field_name.lower():
                for record in records:
                    value = record.get(field_name)
                    if value:
                        parsed = self.parse_date(value)
                        if parsed:
                            death_date = parsed
                            death_field = field_name

                            break
        
        if not death_date:
            return
        
        # Verifica datas posteriores ao óbito
        for record in records:
            event = record.get(event_field, "")
            
            for field_name in date_fields:
                if field_name == death_field:
                    continue
                
                value = record.get(field_name)
                if not value:
                    continue
                
                parsed = self.parse_date(value)
                if parsed and parsed > death_date:
                    field_meta = self.get_field_metadata(field_name)
                    self.add_query(
                        record_id=participant_id,
                        event=event,
                        instrument=field_meta.form_name if field_meta else "N/A",
                        field=field_name,
                        value_found=value,
                        issue_type="death_date_inconsistent",
                        explanation=f"A data '{value}' é posterior à data de óbito ({death_date.strftime('%Y-%m-%d')}).",
                        priority="Alta",
                        suggested_action="Verificar se a data de óbito está correta ou se este registro foi feito erroneamente após o óbito.",
                    )
    
    def _check_event_timeline(self, participant_id: str, records: list[dict]) -> None:
        """Verifica se eventos estão dentro da janela esperada."""
        if not self.project_data.events:
            return
        
        event_field = self.get_event_field()
        date_fields = self._find_date_fields()
        
        # Encontra baseline para referência
        baseline_info = self._find_baseline_date(records)
        if not baseline_info:
            return
        
        baseline_date = baseline_info[0]
        
        for record in records:
            event_name = record.get(event_field, "")
            event_meta = self.project_data.events_by_name.get(event_name)
            
            if not event_meta:
                continue
            
            # Verifica se há janela de visita definida
            if event_meta.days_offset is None:
                continue
            
            expected_date = baseline_date
            # Adiciona offset em dias
            from datetime import timedelta
            expected_date = baseline_date + timedelta(days=event_meta.days_offset)
            
            min_date = expected_date
            max_date = expected_date
            
            if event_meta.offset_min is not None:
                min_date = baseline_date + timedelta(days=event_meta.offset_min)
            if event_meta.offset_max is not None:
                max_date = baseline_date + timedelta(days=event_meta.offset_max)
            
            # Verifica datas do evento
            for field_name in date_fields:
                value = record.get(field_name)
                if not value:
                    continue
                
                parsed = self.parse_date(value)
                if not parsed:
                    continue
                
                if parsed < min_date or parsed > max_date:
                    field_meta = self.get_field_metadata(field_name)
                    self.add_query(
                        record_id=participant_id,
                        event=event_name,
                        instrument=field_meta.form_name if field_meta else "N/A",
                        field=field_name,
                        value_found=value,
                        issue_type="event_out_of_timeline",
                        explanation=f"A data '{value}' está fora da janela esperada para o evento '{event_name}' (esperado: {min_date.strftime('%Y-%m-%d')} a {max_date.strftime('%Y-%m-%d')}).",
                        priority="Média",
                        suggested_action="Verificar se a visita foi realizada fora do protocolo ou se há erro na data.",
                    )
    
    def _check_repeating_sequences(self) -> None:
        """Verifica sequências de repeating instruments."""
        record_id_field = self.get_record_id_field()
        
        # Agrupa por participante e instrumento
        repeating: dict[tuple[str, str], list[int]] = defaultdict(list)
        
        for record in self.project_data.records:
            participant_id = record.get(record_id_field, "UNKNOWN")
            instance = record.get("redcap_repeat_instance")
            instrument = record.get("redcap_repeat_instrument")
            
            if instance and instrument:
                try:
                    instance_num = int(instance)
                    repeating[(participant_id, instrument)].append(instance_num)
                except (ValueError, TypeError):
                    pass
        
        for (participant_id, instrument), instances in repeating.items():
            sorted_instances = sorted(instances)
            
            # Verifica gaps na sequência
            for i, inst in enumerate(sorted_instances):
                expected = i + 1
                if inst != expected:
                    self.add_query(
                        record_id=participant_id,
                        event="N/A",
                        instrument=instrument,
                        field="redcap_repeat_instance",
                        value_found=f"Sequência encontrada: {sorted_instances}",
                        issue_type="repeating_sequence_broken",
                        explanation=f"Sequência do repeating instrument '{instrument}' está quebrada. Esperado instância {expected}, encontrado {inst}.",
                        priority="Média",
                        suggested_action="Verificar se há instâncias faltando ou duplicadas.",
                    )
                    break  # Só reporta o primeiro gap
