"""
REDCap Data Quality Intelligence Agent - Operational Analyzer

Analisador de inconsistências operacionais (logs e auditoria).
"""

from collections import defaultdict
from datetime import timedelta

from .base_analyzer import BaseAnalyzer
from ..models import Query


class OperationalAnalyzer(BaseAnalyzer):
    """
    Analisador de inconsistências operacionais.
    
    Detecta:
    - Picos de edição suspeitos
    - Alterações após encerramento do caso
    - Padrões anormais de auditoria
    - Alto volume de edições por usuário
    """
    
    def __init__(self, project_data, edit_threshold: int = 10, time_window_hours: int = 1):
        """
        Inicializa o analisador operacional.
        
        Args:
            project_data: Dados do projeto
            edit_threshold: Número de edições em janela para considerar suspeito
            time_window_hours: Janela de tempo em horas para detectar picos
        """
        super().__init__(project_data)
        self.edit_threshold = edit_threshold
        self.time_window = timedelta(hours=time_window_hours)
    
    def analyze(self) -> list[Query]:
        """
        Executa análise operacional completa.
        
        Returns:
            Lista de queries identificadas
        """
        self.queries = []
        
        if not self.project_data.logs:
            return self.queries
        
        self._check_edit_spikes()
        self._check_high_volume_users()
        self._check_after_hours_edits()
        self._check_field_specific_patterns()
        
        return self.queries
    
    def _check_edit_spikes(self) -> None:
        """Detecta picos de edição por registro."""
        # Agrupa logs por registro
        logs_by_record = defaultdict(list)
        
        for log in self.project_data.logs:
            if log.record:
                logs_by_record[log.record].append(log)
        
        for record_id, logs in logs_by_record.items():
            # Ordena por timestamp
            sorted_logs = sorted(
                [log_entry for log_entry in logs if log_entry.parsed_timestamp],
                key=lambda x: x.parsed_timestamp
            )
            
            if len(sorted_logs) < self.edit_threshold:
                continue
            
            # Detecta janelas com muitas edições
            for i, log in enumerate(sorted_logs):
                window_end = log.parsed_timestamp + self.time_window
                edits_in_window = sum(
                    1 for log_entry in sorted_logs[i:]
                    if log_entry.parsed_timestamp <= window_end
                )
                
                if edits_in_window >= self.edit_threshold:
                    self.add_query(
                        record_id=record_id,
                        event="N/A",
                        instrument="Audit Log",
                        field="multiple_fields",
                        value_found=f"{edits_in_window} edições em {self.time_window.seconds // 3600}h",
                        issue_type="suspicious_edit_pattern",
                        explanation=f"Detectado pico de {edits_in_window} edições em uma janela de {self.time_window.seconds // 3600} hora(s) iniciando em {log.timestamp}. Usuário: {log.username}.",
                        priority="Média",
                        suggested_action="Revisar as alterações realizadas neste período para verificar integridade dos dados.",
                    )
                    break  # Só reporta uma vez por registro
    
    def _check_high_volume_users(self) -> None:
        """Detecta usuários com volume anormal de edições."""
        edits_by_user = defaultdict(int)
        records_by_user = defaultdict(set)
        
        for log in self.project_data.logs:
            edits_by_user[log.username] += 1
            if log.record:
                records_by_user[log.username].add(log.record)
        
        if not edits_by_user:
            return
        
        # Calcula média e desvio
        values = list(edits_by_user.values())
        avg = sum(values) / len(values)
        
        # Usuários com mais de 3x a média são suspeitos
        threshold = avg * 3
        
        for user, count in edits_by_user.items():
            if count > threshold and count > self.edit_threshold * 5:
                self.add_query(
                    record_id="GLOBAL",
                    event="N/A",
                    instrument="Audit Log",
                    field="user_activity",
                    value_found=f"Usuário: {user}, Edições: {count}",
                    issue_type="high_edit_volume",
                    explanation=f"O usuário '{user}' realizou {count} edições (média: {avg:.0f}), afetando {len(records_by_user[user])} registros. Isso representa um volume significativamente acima do normal.",
                    priority="Baixa",
                    suggested_action="Verificar se o alto volume é justificado (ex: entrada de dados em lote) ou requer investigação.",
                )
    
    def _check_after_hours_edits(self) -> None:
        """Detecta edições em horários incomuns."""
        unusual_edits = defaultdict(list)
        
        for log in self.project_data.logs:
            ts = log.parsed_timestamp
            if not ts:
                continue
            
            # Define horário comercial (8h-20h)
            hour = ts.hour
            is_weekend = ts.weekday() >= 5
            is_after_hours = hour < 6 or hour > 22
            
            if is_weekend or is_after_hours:
                if log.record:
                    unusual_edits[log.record].append({
                        "timestamp": log.timestamp,
                        "user": log.username,
                        "action": log.action,
                        "is_weekend": is_weekend,
                        "hour": hour,
                    })
        
        # Reporta registros com múltiplas edições fora de horário
        for record_id, edits in unusual_edits.items():
            if len(edits) >= 3:  # Só reporta se houver padrão
                users = set(e["user"] for e in edits)
                self.add_query(
                    record_id=record_id,
                    event="N/A",
                    instrument="Audit Log",
                    field="edit_timing",
                    value_found=f"{len(edits)} edições fora de horário por {len(users)} usuário(s)",
                    issue_type="suspicious_edit_pattern",
                    explanation=f"Detectadas {len(edits)} edições em horários incomuns (madrugada ou fim de semana) por {', '.join(users)}.",
                    priority="Baixa",
                    suggested_action="Verificar se as edições são legítimas ou se há padrão de manipulação de dados.",
                )
    
    def _check_field_specific_patterns(self) -> None:
        """Detecta padrões suspeitos em campos específicos."""
        # Agrupa edições por campo
        field_edits = defaultdict(list)
        
        for log in self.project_data.logs:
            if log.details:
                # Tenta extrair nome do campo do detalhe
                # Formato típico: "campo = valor"
                if "=" in log.details:
                    field_name = log.details.split("=")[0].strip()
                    field_edits[field_name].append({
                        "record": log.record,
                        "user": log.username,
                        "timestamp": log.timestamp,
                    })
        
        # Detecta campos com muitas correções
        for field_name, edits in field_edits.items():
            unique_records = set(e["record"] for e in edits if e["record"])
            
            if len(edits) > len(unique_records) * 2:  # Média de 2+ edições por registro
                self.add_query(
                    record_id="GLOBAL",
                    event="N/A",
                    instrument="Audit Log",
                    field=field_name,
                    value_found=f"{len(edits)} edições em {len(unique_records)} registros",
                    issue_type="suspicious_edit_pattern",
                    explanation=f"O campo '{field_name}' foi editado múltiplas vezes ({len(edits)} edições em {len(unique_records)} registros). Isso pode indicar problemas de treinamento ou clareza do formulário.",
                    priority="Baixa",
                    suggested_action="Revisar se o campo está causando confusão aos usuários ou se há padrão de correção sistemática.",
                )
