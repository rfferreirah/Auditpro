"""
REDCap Data Quality Intelligence Agent - Query Generator

Consolidador de queries e gerador de relatório final.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from collections import Counter

from rich.console import Console
from rich.table import Table

from .models import Query, QualityReport, ProjectData
from .analyzers import (
    StructuralAnalyzer,
    TemporalAnalyzer,
    ClinicalAnalyzer,
    OperationalAnalyzer,
    OperationalAnalyzer,
    CustomRulesAnalyzer,
)
from .rules_manager import rules_manager
import config

console = Console()


class QueryGenerator:
    """
    Gerador de queries inteligentes.
    
    Consolida análises de todos os analisadores e gera
    relatório final estruturado.
    """
    
    def __init__(
        self,
        project_data: ProjectData,
        custom_clinical_limits: Optional[dict] = None,
        include_operational: bool = True,
        user_id: str = None,
        access_token: str = None,
        active_checks: Optional[list[str]] = None,
    ):
        """
        Inicializa o gerador de queries.
        
        Args:
            project_data: Dados do projeto REDCap
            custom_clinical_limits: Limites clínicos customizados
            include_operational: Se deve incluir análise de logs
            user_id: ID do usuário para carregar regras customizadas
            access_token: Token de acesso para queries autenticadas
        """
        self.project_data = project_data
        self.custom_clinical_limits = custom_clinical_limits
        self.include_operational = include_operational
        self.user_id = user_id
        self.access_token = access_token
        self.active_checks = active_checks
        self.queries: list[Query] = []
    
    def run_all_analyzers(self) -> list[Query]:
        """
        Executa todos os analisadores.
        
        Returns:
            Lista consolidada de queries
        """
        self.queries = []
        
        active_rules = rules_manager.get_enabled_rules()
        active_ids = {r.id for r in active_rules}
        
        # Analisador Estrutural (Configurado via rules_manager ou override)
        if self.active_checks is not None:
             # Se recebemos checks explícitos do frontend, usamos eles
             enabled_structural_checks = [c for c in self.active_checks if c.startswith('sys_')]
        else:
             # Fallback para rules_manager
             enabled_structural_checks = [
                rid for rid in active_ids 
                if rid.startswith('sys_') 
                and rid not in ['sys_temporal', 'sys_clinical', 'sys_operational'] # Separate structural ones
            ]
        
        # Analisador Estrutural
        console.print(f"\n[bold cyan]📋 Executando Análise Estrutural ({len(enabled_structural_checks)} checks ativos)...[/bold cyan]")
        structural = StructuralAnalyzer(self.project_data, enabled_checks=enabled_structural_checks)
        structural_queries = structural.analyze()
        self.queries.extend(structural_queries)
        console.print(f"   ✓ {len(structural_queries)} inconsistências encontradas")
        
        # Analisador Temporal
        if 'sys_temporal' in active_ids:
            console.print("\n[bold cyan]📅 Executando Análise Temporal...[/bold cyan]")
            temporal = TemporalAnalyzer(self.project_data)
            temporal_queries = temporal.analyze()
            self.queries.extend(temporal_queries)
            console.print(f"   ✓ {len(temporal_queries)} inconsistências encontradas")
        
        # Analisador Clínico
        if 'sys_clinical' in active_ids:
            console.print("\n[bold cyan]🏥 Executando Análise Clínica...[/bold cyan]")
            clinical = ClinicalAnalyzer(self.project_data, self.custom_clinical_limits)
            clinical_queries = clinical.analyze()
            self.queries.extend(clinical_queries)
            console.print(f"   ✓ {len(clinical_queries)} inconsistências encontradas")
        
        # Analisador Operacional (se houver logs)
        if 'sys_operational' in active_ids:
            if self.include_operational and self.project_data.logs:
                console.print("\n[bold cyan]📊 Executando Análise Operacional...[/bold cyan]")
                operational = OperationalAnalyzer(self.project_data)
                operational_queries = operational.analyze()
                self.queries.extend(operational_queries)
                console.print(f"   ✓ {len(operational_queries)} padrões identificados")
            elif self.include_operational:
                console.print("\n[dim]⚠ Análise Operacional ignorada (logs não disponíveis)[/dim]")
        
        # Analisador de Regras Customizadas
        console.print("\n[bold cyan]⚙️ Executando Regras Customizadas...[/bold cyan]")
        custom_rules = CustomRulesAnalyzer(self.project_data, user_id=self.user_id, access_token=self.access_token)
        custom_queries = custom_rules.analyze()
        self.queries.extend(custom_queries)
        console.print(f"   ✓ {len(custom_queries)} violações de regras customizadas")
        
        console.print(f"   ✓ {len(custom_queries)} violações de regras customizadas")
        
        # Enriquecimento: Garante que todos os queries tenham o nome do formulário (instrument)
        # Isso é crucial para o Deep Linking (link direto para o campo)
        console.print("\n[dim]Enriquecendo metadata das queries...[/dim]")
        field_to_form = {f.field_name: f.form_name for f in self.project_data.metadata}
        
        for q in self.queries:
            if not q.instrument or q.instrument == "N/A":
                if q.field in field_to_form:
                    q.instrument = field_to_form[q.field]

        return self.queries
    
    def generate_report(self) -> QualityReport:
        """
        Gera relatório de qualidade.
        
        Returns:
            QualityReport com resumo e queries
        """
        # Conta registros únicos
        record_id_field = self.project_data.metadata[0].field_name if self.project_data.metadata else "record_id"
        unique_records = set()
        for record in self.project_data.records:
            unique_records.add(record.get(record_id_field, "UNKNOWN"))
        
        return QualityReport.create_summary(
            queries=self.queries,
            total_records=len(unique_records),
        )
    
    def export_json(self, output_path: Optional[Path] = None) -> Path:
        """
        Exporta relatório para JSON.
        
        Args:
            output_path: Caminho do arquivo (opcional)
            
        Returns:
            Path do arquivo gerado
        """
        report = self.generate_report()
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = config.OUTPUT_DIR / f"quality_report_{timestamp}.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        return output_path
    
    def print_summary(self) -> None:
        """Imprime resumo das queries no console."""
        if not self.queries:
            console.print("\n[green]✅ Nenhuma inconsistência encontrada![/green]")
            return
        
        # Contagem por prioridade
        priority_counts = Counter(q.priority for q in self.queries)
        
        # Contagem por tipo
        type_counts = Counter(q.issue_type for q in self.queries)
        
        # Tabela de resumo
        console.print("\n[bold]📊 RESUMO DA ANÁLISE[/bold]")
        console.print("=" * 50)
        
        # Por prioridade
        table = Table(title="Por Prioridade")
        table.add_column("Prioridade", style="bold")
        table.add_column("Quantidade", justify="right")
        
        for priority in ["Alta", "Média", "Baixa"]:
            count = priority_counts.get(priority, 0)
            style = "red" if priority == "Alta" else "yellow" if priority == "Média" else "green"
            table.add_row(priority, f"[{style}]{count}[/{style}]")
        
        table.add_row("[bold]TOTAL[/bold]", f"[bold]{len(self.queries)}[/bold]")
        console.print(table)
        
        # Top 5 tipos de erro
        console.print("\n[bold]🔍 Tipos de Inconsistência Mais Comuns:[/bold]")
        for issue_type, count in type_counts.most_common(5):
            desc = config.ISSUE_TYPES.get(issue_type, issue_type)
            console.print(f"   • {desc}: {count}")
    
    def print_queries(self, limit: int = 20, priority: Optional[str] = None) -> None:
        """
        Imprime queries detalhadas no console.
        
        Args:
            limit: Número máximo de queries a exibir
            priority: Filtrar por prioridade (opcional)
        """
        queries = self.queries
        
        if priority:
            queries = [q for q in queries if q.priority == priority]
        
        if not queries:
            console.print("[dim]Nenhuma query para exibir.[/dim]")
            return
        
        # Ordena por prioridade
        priority_order = {"Alta": 0, "Média": 1, "Baixa": 2}
        queries = sorted(queries, key=lambda q: priority_order.get(q.priority, 3))
        
        console.print(f"\n[bold]📝 QUERIES ({min(limit, len(queries))} de {len(queries)})[/bold]")
        console.print("=" * 70)
        
        for i, query in enumerate(queries[:limit]):
            priority_style = "red" if query.priority == "Alta" else "yellow" if query.priority == "Média" else "green"
            
            console.print(f"\n[bold]#{i+1}[/bold] [{priority_style}][{query.priority}][/{priority_style}]")
            console.print(f"   [bold]Record:[/bold] {query.record_id} | [bold]Evento:[/bold] {query.event}")
            console.print(f"   [bold]Campo:[/bold] {query.field} ({query.instrument})")
            console.print(f"   [bold]Valor:[/bold] {query.value_found}")
            console.print(f"   [bold]Tipo:[/bold] {config.ISSUE_TYPES.get(query.issue_type, query.issue_type)}")
            console.print(f"   [bold]Explicação:[/bold] {query.explanation}")
            if query.suggested_action:
                console.print(f"   [bold]Sugestão:[/bold] {query.suggested_action}")
        
        if len(queries) > limit:
            console.print(f"\n[dim]... e mais {len(queries) - limit} queries. Use --limit para ver mais.[/dim]")
