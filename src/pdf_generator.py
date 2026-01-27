"""
REDCap Data Quality Intelligence Agent - PDF Report Generator

Gerador de relatórios PDF profissionais e estruturados.
"""

import io
import html
from datetime import datetime
from pathlib import Path
from collections import Counter
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER

import config
from src.models import QualityReport, Query


class PDFReportGenerator:
    """
    Gerador de relatórios PDF profissionais.
    """
    
    def __init__(self, report: QualityReport, project_name: str = "Projeto REDCap", field_labels: Optional[dict] = None, user_name: str = None):
        """
        Inicializa o gerador de PDF.
        
        Args:
            report: Relatório de qualidade
            project_name: Nome do projeto
            field_labels: Dicionário mapping field_name -> field_label
            user_name: Nome do usuário que gerou o relatório
        """
        self.report = report
        self.project_name = project_name
        self.field_labels = field_labels or {}
        self.user_name = user_name or "Usuário do Sistema"
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Configura estilos customizados."""
        # Título principal
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a365d'),
        ))
        
        # Subtítulo
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#4a5568'),
        ))
        
        # Cabeçalho de seção
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#2c5282'),
            borderPadding=(5, 5, 5, 5),
        ))
        
        # Texto normal
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=8,
            leading=14,
        ))
        
        # Query de alta prioridade
        self.styles.add(ParagraphStyle(
            name='HighPriority',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#c53030'),
            leftIndent=10,
        ))
        
        # Query de média prioridade
        self.styles.add(ParagraphStyle(
            name='MediumPriority',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#d69e2e'),
            leftIndent=10,
        ))
        
        # Query de baixa prioridade
        self.styles.add(ParagraphStyle(
            name='LowPriority',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#38a169'),
            leftIndent=10,
        ))
    
    def _create_header(self, elements: list):
        """Cria o cabeçalho do relatório."""
        elements.append(Paragraph(
            "Relatório de Qualidade de Dados",
            self.styles['CustomTitle']
        ))
        elements.append(Paragraph(
            f"Projeto: {self.project_name}",
            self.styles['CustomSubtitle']
        ))
        
        # Date and User
        date_str = datetime.now().strftime('%d/%m/%Y às %H:%M')
        elements.append(Paragraph(
            f"Gerado em: {date_str}<br/>Gerado por: {self.user_name}",
            self.styles['CustomSubtitle']
        ))
        
        elements.append(HRFlowable(
            width="100%", thickness=2, color=colors.HexColor('#2c5282')
        ))
        elements.append(Spacer(1, 20))
    
    def _create_summary_section(self, elements: list):
        """Cria a seção de resumo executivo."""
        elements.append(Paragraph("📊 Resumo Executivo", self.styles['SectionHeader']))
        
        summary = self.report.project_summary
        
        # Estatísticas gerais
        stats_data = [
            ['Métrica', 'Valor'],
            ['Total de Participantes', str(summary.total_records)],
            ['Total de Queries Geradas', str(summary.total_queries_generated)],
        ]
        
        # Contagem por prioridade
        priority_counts = Counter(q.priority for q in self.report.queries)
        stats_data.append(['Queries de Alta Prioridade', str(priority_counts.get('Alta', 0))])
        stats_data.append(['Queries de Média Prioridade', str(priority_counts.get('Média', 0))])
        stats_data.append(['Queries de Baixa Prioridade', str(priority_counts.get('Baixa', 0))])
        
        stats_table = Table(stats_data, colWidths=[10*cm, 5*cm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#edf2f7')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 20))
        
        # Tipos de erro mais comuns
        if summary.most_common_error_types:
            elements.append(Paragraph(
                "<b>Tipos de Inconsistência Mais Comuns:</b>",
                self.styles['CustomBody']
            ))
            for i, error_type in enumerate(summary.most_common_error_types[:5], 1):
                desc = config.ISSUE_TYPES.get(error_type, error_type)
                elements.append(Paragraph(
                    f"  {i}. {desc}",
                    self.styles['CustomBody']
                ))
            elements.append(Spacer(1, 10))
        
        # Campos com mais problemas
        if summary.fields_with_most_issues:
            elements.append(Paragraph(
                "<b>Campos com Mais Problemas:</b>",
                self.styles['CustomBody']
            ))
            for i, field in enumerate(summary.fields_with_most_issues[:5], 1):
                elements.append(Paragraph(
                    f"  {i}. {field}",
                    self.styles['CustomBody']
                ))

    def _create_queries_section(self, elements: list, priority: Optional[str] = None):
        """Cria a seção de queries detalhadas."""
        queries = self.report.queries
        
        if priority:
            queries = [q for q in queries if q.priority == priority]
            title = f"🔍 Queries - Prioridade {priority}"
        else:
            title = "🔍 Todas as Queries"
        
        if not queries:
            return
        
        elements.append(PageBreak())
        elements.append(Paragraph(title, self.styles['SectionHeader']))
        elements.append(Spacer(1, 10))
        
        # Agrupa por participante
        queries_by_record: dict[str, list[Query]] = {}
        for query in queries:
            if query.record_id not in queries_by_record:
                queries_by_record[query.record_id] = []
            queries_by_record[query.record_id].append(query)
        
        # Limita para evitar PDF muito grande
        max_records = 50
        shown_records = 0
        
        for record_id, record_queries in sorted(queries_by_record.items()):
            if shown_records >= max_records:
                elements.append(Paragraph(
                    f"<i>... e mais {len(queries_by_record) - max_records} participantes com queries.</i>",
                    self.styles['CustomBody']
                ))
                break
            
            shown_records += 1
            
            # Cabeçalho do participante
            elements.append(Paragraph(
                f"<b>Participante: {record_id}</b> ({len(record_queries)} queries)",
                self.styles['CustomBody']
            ))
            
            # Tabela de queries
            table_data = [['Campo', 'Valor', 'Tipo', 'Prioridade']]
            
            for query in record_queries[:10]:  # Limita queries por participante
                # Trunca valor se muito longo e escapa HTML
                raw_value = str(query.value_found) if query.value_found else "N/A"
                if len(raw_value) > 30:
                    raw_value = raw_value[:27] + "..."
                value = html.escape(raw_value)
                
                raw_issue = config.ISSUE_TYPES.get(query.issue_type, query.issue_type)
                if len(raw_issue) > 25:
                    raw_issue = raw_issue[:22] + "..."
                issue_desc = html.escape(raw_issue)
                
                # Prepara célula do campo com label
                field_name = html.escape(query.field)
                field_label = self.field_labels.get(query.field, "")
                
                # Remove HTML tags simples se houver
                if field_label:
                    if "<" in field_label:
                        import re
                        field_label = re.sub(r'<[^>]*>', '', field_label)
                    
                    # Trunca label se muito longo antes de escapar
                    if len(field_label) > 40:
                        field_label = field_label[:37] + "..."
                    
                    # Escapa caracteres especiais para evitar quebra do PDF
                    field_label = html.escape(field_label)
                
                # Constrói conteúdo da célula
                field_text = f"<b>{field_name}</b>"
                if field_label:
                    field_text += f"<br/><font color='#666666' size='7'>{field_label}</font>"
                
                field_cell = Paragraph(field_text, self.styles['CustomBody'])
                
                table_data.append([
                    field_cell,
                    value,
                    issue_desc,
                    query.priority
                ])
            
            if len(record_queries) > 10:
                table_data.append(['...', f'+{len(record_queries) - 10} queries', '', ''])
            
            query_table = Table(table_data, colWidths=[4*cm, 4*cm, 5*cm, 2*cm])
            
            # Cores por prioridade
            style_commands = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (-1, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]
            
            # Aplica cores de prioridade
            for i, row in enumerate(table_data[1:], 1):
                if row[3] == 'Alta':
                    style_commands.append(('BACKGROUND', (-1, i), (-1, i), colors.HexColor('#fed7d7')))
                    style_commands.append(('TEXTCOLOR', (-1, i), (-1, i), colors.HexColor('#c53030')))
                elif row[3] == 'Média':
                    style_commands.append(('BACKGROUND', (-1, i), (-1, i), colors.HexColor('#fefcbf')))
                    style_commands.append(('TEXTCOLOR', (-1, i), (-1, i), colors.HexColor('#d69e2e')))
                elif row[3] == 'Baixa':
                    style_commands.append(('BACKGROUND', (-1, i), (-1, i), colors.HexColor('#c6f6d5')))
                    style_commands.append(('TEXTCOLOR', (-1, i), (-1, i), colors.HexColor('#38a169')))
            
            query_table.setStyle(TableStyle(style_commands))
            elements.append(query_table)
            elements.append(Spacer(1, 15))
    
    def _create_footer(self, elements: list):
        """Cria o rodapé do relatório."""
        elements.append(Spacer(1, 30))
        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#cbd5e0')
        ))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(
            "Relatório gerado automaticamente pelo Audit PRO",
            ParagraphStyle(
                'Footer',
                fontSize=8,
                textColor=colors.HexColor('#718096'),
                alignment=TA_CENTER
            )
        ))
    
    def generate(self, output_path: Optional[Path] = None) -> Path:
        """
        Gera o relatório PDF.
        
        Args:
            output_path: Caminho do arquivo (opcional)
            
        Returns:
            Path do arquivo gerado
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = config.OUTPUT_DIR / f"quality_report_{timestamp}.pdf"
        
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        elements = []
        
        # Constrói o documento
        self._create_header(elements)
        self._create_summary_section(elements)
        
        # Queries por prioridade
        self._create_queries_section(elements, priority="Alta")
        self._create_queries_section(elements, priority="Média")
        self._create_queries_section(elements, priority="Baixa")
        
        self._create_footer(elements)
        
        # Gera o PDF
        doc.build(elements)
        
        return output_path
    
    def generate_bytes(self) -> bytes:
        """
        Gera o PDF e retorna como bytes (para download web).
        
        Returns:
            Bytes do PDF
        """
        buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        elements = []
        
        self._create_header(elements)
        self._create_summary_section(elements)
        self._create_queries_section(elements, priority="Alta")
        self._create_queries_section(elements, priority="Média")
        self._create_queries_section(elements, priority="Baixa")
        self._create_footer(elements)
        
        doc.build(elements)
        
        buffer.seek(0)
        return buffer.read()
