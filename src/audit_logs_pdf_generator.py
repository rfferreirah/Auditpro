"""
REDCap Data Quality Intelligence Agent - Audit Logs PDF Generator

Gerador de PDF para logs de auditoria do REDCap.
"""

import io
import html
from datetime import datetime, timezone, timedelta
from typing import Optional, Union

# Timezone de Brasília (UTC-3)
TZ_BRASILIA = timezone(timedelta(hours=-3))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


class AuditLogsPDFGenerator:
    """
    Gerador de PDF para logs de auditoria do REDCap.
    """
    
    def __init__( 
        self, 
        logs: list[dict], 
        project_name: str = "Projeto REDCap",
        user_name: str = None
    ):
        """
        Inicializa o gerador de PDF para logs.
        
        Args:
            logs: Lista de logs (dicts com timestamp, username, action, details, record)
            project_name: Nome do projeto
            user_name: Nome do usuário que gerou o relatório
        """
        self.logs = logs or []
        self.project_name = project_name
        self.user_name = user_name or "Usuário do Sistema"
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Configura estilos customizados."""
        # Título principal
        self.styles.add(ParagraphStyle(
            name='AuditTitle',
            parent=self.styles['Heading1'],
            fontSize=22,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a365d'),
        ))
        
        # Subtítulo
        self.styles.add(ParagraphStyle(
            name='AuditSubtitle',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#4a5568'),
        ))
        
        # Cabeçalho de seção
        self.styles.add(ParagraphStyle(
            name='AuditSectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=15,
            spaceAfter=10,
            textColor=colors.HexColor('#2c5282'),
        ))
        
        # Texto normal
        self.styles.add(ParagraphStyle(
            name='AuditBody',
            parent=self.styles['Normal'],
            fontSize=9,
            spaceAfter=6,
            leading=12,
        ))
        
        # Célula da tabela
        self.styles.add(ParagraphStyle(
            name='AuditCell',
            parent=self.styles['Normal'],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
        ))
    
    def _create_header(self, elements: list):
        """Cria o cabeçalho do relatório."""
        elements.append(Paragraph(
            "📋 Logs de Auditoria REDCap",
            self.styles['AuditTitle']
        ))
        elements.append(Paragraph(
            f"Projeto: {html.escape(self.project_name)}",
            self.styles['AuditSubtitle']
        ))
        
        # Data e Usuário
        date_str = datetime.now(TZ_BRASILIA).strftime('%d/%m/%Y às %H:%M')
        elements.append(Paragraph(
            f"Exportado em: {date_str}<br/>Por: {html.escape(self.user_name)}",
            self.styles['AuditSubtitle']
        ))
        
        elements.append(HRFlowable(
            width="100%", thickness=2, color=colors.HexColor('#2c5282')
        ))
        elements.append(Spacer(1, 15))
    
    def _create_summary_section(self, elements: list):
        """Cria a seção de resumo."""
        elements.append(Paragraph("📊 Resumo", self.styles['AuditSectionHeader']))
        
        total_logs = len(self.logs)
        
        # Contagem por ação
        action_counts = {}
        user_counts = {}
        for log in self.logs:
            action = log.get('action', 'Unknown')
            action_counts[action] = action_counts.get(action, 0) + 1
            
            user = log.get('username', 'Unknown')
            user_counts[user] = user_counts.get(user, 0) + 1
        
        # Estatísticas gerais
        stats_data = [
            ['Métrica', 'Valor'],
            ['Total de Logs', str(total_logs)],
            ['Usuários Únicos', str(len(user_counts))],
            ['Tipos de Ação', str(len(action_counts))],
        ]
        
        # Top ações
        top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        for action, count in top_actions:
            stats_data.append([f'Ação: {action[:30]}...', str(count)] if len(action) > 30 else [f'Ação: {action}', str(count)])
        
        stats_table = Table(stats_data, colWidths=[10*cm, 5*cm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#edf2f7')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 20))
    
    def _create_logs_table(self, elements: list):
        """Cria a tabela de logs."""
        if not self.logs:
            elements.append(Paragraph(
                "<i>Nenhum log de auditoria encontrado.</i>",
                self.styles['AuditBody']
            ))
            return
        
        elements.append(Paragraph("📝 Detalhes dos Logs", self.styles['AuditSectionHeader']))
        elements.append(Spacer(1, 10))
        
        # Cabeçalho da tabela
        table_data = [['Data/Hora', 'Usuário', 'Ação', 'Registro', 'Detalhes']]
        
        # Limita para não gerar PDF muito grande
        max_logs = 500
        logs_to_show = self.logs[:max_logs]
        
        for log in logs_to_show:
            timestamp = log.get('timestamp', 'N/A')
            username = log.get('username', 'N/A')
            action = log.get('action', 'N/A')
            record = log.get('record', '-')
            details = log.get('details', '-')
            
            # Trunca campos longos
            if details and len(str(details)) > 50:
                details = str(details)[:47] + "..."
            if action and len(str(action)) > 30:
                action = str(action)[:27] + "..."
            
            # Escapa HTML
            table_data.append([
                html.escape(str(timestamp)),
                html.escape(str(username)),
                html.escape(str(action)),
                html.escape(str(record)) if record else '-',
                html.escape(str(details)) if details else '-',
            ])
        
        # Define larguras das colunas
        col_widths = [2.8*cm, 2.5*cm, 4*cm, 2*cm, 5.5*cm]
        
        logs_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        logs_table.setStyle(TableStyle([
            # Cabeçalho
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Corpo
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Bordas e padding
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            
            # Alternância de cores nas linhas
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
        ]))
        
        elements.append(logs_table)
        
        if len(self.logs) > max_logs:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph(
                f"<i>⚠️ Mostrando {max_logs} de {len(self.logs)} logs. Exporte para CSV para ver todos.</i>",
                self.styles['AuditBody']
            ))
    
    def _create_footer(self, elements: list):
        """Cria o rodapé do relatório."""
        elements.append(Spacer(1, 30))
        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor('#cbd5e0')
        ))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(
            "Logs de Auditoria exportados pelo AuditPRO",
            ParagraphStyle(
                'AuditFooter',
                fontSize=8,
                textColor=colors.HexColor('#718096'),
                alignment=TA_CENTER
            )
        ))
    
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
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        elements = []
        
        self._create_header(elements)
        self._create_summary_section(elements)
        self._create_logs_table(elements)
        self._create_footer(elements)
        
        doc.build(elements)
        
        buffer.seek(0)
        return buffer.read()
