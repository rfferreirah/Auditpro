"""
REDCap Data Quality Intelligence Agent - Data Models

Modelos Pydantic para validação e estruturação de dados.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class FieldMetadata(BaseModel):
    """Metadados de um campo do REDCap."""
    
    field_name: str
    form_name: str
    section_header: Optional[str] = None
    field_type: str  # text, notes, calc, dropdown, radio, checkbox, etc.
    field_label: str
    select_choices_or_calculations: Optional[str] = None
    field_note: Optional[str] = None
    text_validation_type_or_show_slider_number: Optional[str] = None
    text_validation_min: Optional[str] = None
    text_validation_max: Optional[str] = None
    identifier: Optional[str] = None
    branching_logic: Optional[str] = None
    required_field: Optional[str] = None  # 'y' or ''
    custom_alignment: Optional[str] = None
    question_number: Optional[str] = None
    matrix_group_name: Optional[str] = None
    matrix_ranking: Optional[str] = None
    field_annotation: Optional[str] = None
    
    @property
    def is_required(self) -> bool:
        """Verifica se o campo é obrigatório."""
        return self.required_field == "y"
    
    @property
    def has_branching_logic(self) -> bool:
        """Verifica se o campo tem branching logic."""
        return bool(self.branching_logic and self.branching_logic.strip())
    
    @property
    def validation_type(self) -> Optional[str]:
        """Retorna o tipo de validação do campo."""
        return self.text_validation_type_or_show_slider_number
    
    @property
    def choices(self) -> dict:
        """Retorna as opções de escolha como dicionário {código: label}."""
        if not self.select_choices_or_calculations:
            return {}
        
        choices = {}
        if self.field_type in ["dropdown", "radio", "checkbox"]:
            for item in self.select_choices_or_calculations.split("|"):
                if "," in item:
                    parts = item.split(",", 1)
                    code = parts[0].strip()
                    label = parts[1].strip() if len(parts) > 1 else ""
                    choices[code] = label
        return choices


class Event(BaseModel):
    """Evento do projeto REDCap."""
    
    event_name: str
    arm_num: int
    unique_event_name: str
    custom_event_label: Optional[str] = None
    event_id: Optional[int] = None
    days_offset: Optional[int] = None
    offset_min: Optional[int] = None
    offset_max: Optional[int] = None
    
    @property
    def display_name(self) -> str:
        """Nome de exibição do evento."""
        return self.custom_event_label or self.event_name


class Arm(BaseModel):
    """Braço do estudo REDCap."""
    
    arm_num: int
    name: str


class FormEventMapping(BaseModel):
    """Mapeamento de formulário para evento."""
    
    arm_num: int
    unique_event_name: str
    form: str


class LogEntry(BaseModel):
    """Entrada de log de auditoria."""
    
    timestamp: str
    username: str
    action: str
    details: Optional[str] = None
    record: Optional[str] = None
    
    @property
    def parsed_timestamp(self) -> Optional[datetime]:
        """Converte timestamp para datetime."""
        try:
            return datetime.strptime(self.timestamp, "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return None


class Query(BaseModel):
    """Query gerada pelo análise de qualidade."""
    
    record_id: str
    event: str
    instrument: str
    field: str
    value_found: Any
    issue_type: str
    explanation: str
    suggested_action: Optional[str] = None
    priority: str = Field(pattern="^(Alta|Média|Baixa)$")
    
    # Grau de modificação necessária
    modification_severity: str = Field(
        default="Simples",
        pattern="^(Simples|Moderada|Complexa)$"
    )
    modification_details: Optional[str] = None
    
    # Link direto para o REDCap
    redcap_link: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "record_id": self.record_id,
            "event": self.event,
            "instrument": self.instrument,
            "field": self.field,
            "value_found": str(self.value_found) if self.value_found is not None else None,
            "issue_type": self.issue_type,
            "explanation": self.explanation,
            "suggested_action": self.suggested_action,
            "priority": self.priority,
            "modification_severity": self.modification_severity,
            "modification_details": self.modification_details,
            "redcap_link": self.redcap_link,
        }


class ProjectSummary(BaseModel):
    """Resumo do projeto após análise."""
    
    total_records: int
    total_queries_generated: int
    most_common_error_types: list[str]
    fields_with_most_issues: list[str]
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "total_records": self.total_records,
            "total_queries_generated": self.total_queries_generated,
            "most_common_error_types": self.most_common_error_types,
            "fields_with_most_issues": self.fields_with_most_issues,
        }


class QualityReport(BaseModel):
    """Relatório completo de qualidade de dados."""
    
    project_summary: ProjectSummary
    queries: list[Query]
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """Converte para dicionário formatado para JSON."""
        return {
            "project_summary": self.project_summary.to_dict(),
            "queries": [q.to_dict() for q in self.queries],
            "generated_at": self.generated_at,
        }
    
    @classmethod
    def create_summary(cls, queries: list[Query], total_records: int) -> "QualityReport":
        """Cria relatório com resumo calculado automaticamente."""
        # Contagem de tipos de erro
        error_counts: dict[str, int] = {}
        field_counts: dict[str, int] = {}
        
        for query in queries:
            error_counts[query.issue_type] = error_counts.get(query.issue_type, 0) + 1
            field_counts[query.field] = field_counts.get(query.field, 0) + 1
        
        # Top 5 erros mais comuns
        most_common_errors = sorted(error_counts.keys(), key=lambda x: error_counts[x], reverse=True)[:5]
        
        # Top 5 campos com mais problemas
        fields_with_issues = sorted(field_counts.keys(), key=lambda x: field_counts[x], reverse=True)[:5]
        
        summary = ProjectSummary(
            total_records=total_records,
            total_queries_generated=len(queries),
            most_common_error_types=most_common_errors,
            fields_with_most_issues=fields_with_issues,
        )
        
        return cls(project_summary=summary, queries=queries)


class ProjectData(BaseModel):
    """Container para todos os dados do projeto REDCap."""
    
    metadata: list[FieldMetadata]
    records: list[dict]
    events: list[Event] = []
    arms: list[Arm] = []
    form_event_mapping: list[FormEventMapping] = []
    logs: list[LogEntry] = []
    
    @property
    def metadata_by_field(self) -> dict[str, FieldMetadata]:
        """Retorna metadados indexados por nome do campo."""
        return {field.field_name: field for field in self.metadata}
    
    @property
    def events_by_name(self) -> dict[str, Event]:
        """Retorna eventos indexados por unique_event_name."""
        return {event.unique_event_name: event for event in self.events}
    
    @property
    def forms_by_event(self) -> dict[str, list[str]]:
        """Retorna formulários agrupados por evento."""
        mapping: dict[str, list[str]] = {}
        for fem in self.form_event_mapping:
            if fem.unique_event_name not in mapping:
                mapping[fem.unique_event_name] = []
            mapping[fem.unique_event_name].append(fem.form)
        return mapping
