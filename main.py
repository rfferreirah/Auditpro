"""
REDCap Data Quality Intelligence Agent - Main CLI

Interface de linha de comando para o agente de qualidade de dados.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Adiciona diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent))

import config
from src.redcap_client import REDCapClient, create_client_from_env, REDCapAPIError
from src.query_generator import QueryGenerator
from src.models import ProjectData

console = Console()


def print_banner():
    """Imprime banner do agente."""
    banner = """
╔═══════════════════════════════════════════════════════════════════╗
║          REDCap Data Quality Intelligence Agent v1.0              ║
║                                                                   ║
║   Análise automatizada de qualidade de dados para estudos        ║
║   clínicos utilizando a API do REDCap                             ║
╚═══════════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


def test_connection(args):
    """Testa conexão com a API REDCap."""
    console.print("\n[bold]🔌 Testando conexão com REDCap...[/bold]")
    
    try:
        client = create_client_from_env()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Conectando...", total=None)
            
            project_info = client.export_project_info()
            progress.update(task, description="Conexão estabelecida!")
        
        console.print("\n[green]✅ Conexão bem-sucedida![/green]")
        console.print(f"   Projeto: {project_info.get('project_title', 'N/A')}")
        console.print(f"   ID: {project_info.get('project_id', 'N/A')}")
        console.print(f"   Longitudinal: {'Sim' if project_info.get('is_longitudinal') else 'Não'}")
        
    except ValueError as e:
        console.print(f"\n[red]❌ Erro de configuração: {e}[/red]")
        console.print("[dim]Verifique se o arquivo .env está configurado corretamente.[/dim]")
        return 1
    except REDCapAPIError as e:
        console.print(f"\n[red]❌ Erro na API: {e}[/red]")
        return 1
    
    return 0


def run_analysis(args):
    """Executa análise completa."""
    console.print("\n[bold]🔍 Iniciando Análise de Qualidade de Dados...[/bold]")
    
    try:
        # Conecta à API
        console.print("\n[cyan]Conectando à API REDCap...[/cyan]")
        client = create_client_from_env()
        
        # Exporta dados
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Exportando dados do projeto...", total=None)
            project_data = client.export_all_data(include_logs=args.include_logs)
            progress.update(task, description="Dados exportados!")
        
        # Estatísticas dos dados
        console.print("\n[bold]📊 Dados do Projeto:[/bold]")
        console.print(f"   • Campos (metadata): {len(project_data.metadata)}")
        console.print(f"   • Registros: {len(project_data.records)}")
        console.print(f"   • Eventos: {len(project_data.events)}")
        console.print(f"   • Braços: {len(project_data.arms)}")
        console.print(f"   • Logs: {len(project_data.logs)}")
        
        # Executa análise
        generator = QueryGenerator(
            project_data=project_data,
            include_operational=args.include_logs,
        )
        
        queries = generator.run_all_analyzers()
        
        # Exibe resumo
        generator.print_summary()
        
        # Exibe queries detalhadas
        if args.verbose:
            generator.print_queries(
                limit=args.limit,
                priority=args.priority,
            )
        
        # Exporta JSON
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = None
        
        report_path = generator.export_json(output_path)
        console.print(f"\n[green]✅ Relatório salvo em: {report_path}[/green]")
        
    except ValueError as e:
        console.print(f"\n[red]❌ Erro de configuração: {e}[/red]")
        return 1
    except REDCapAPIError as e:
        console.print(f"\n[red]❌ Erro na API: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"\n[red]❌ Erro inesperado: {e}[/red]")
        if config.DEBUG:
            console.print_exception()
        return 1
    
    return 0


def run_demo(args):
    """Executa demonstração com dados fictícios."""
    console.print("\n[bold]🎯 Modo Demonstração[/bold]")
    console.print("[dim]Executando análise com dados fictícios...[/dim]")
    
    # Importa gerador de demo
    try:
        from demo_data import generate_demo_data
        project_data = generate_demo_data()
    except ImportError:
        console.print("[red]❌ Arquivo demo_data.py não encontrado.[/red]")
        console.print("[dim]Execute: python create_demo.py para gerar dados de demonstração.[/dim]")
        return 1
    
    # Executa análise
    generator = QueryGenerator(project_data=project_data)
    queries = generator.run_all_analyzers()
    
    # Exibe resultados
    generator.print_summary()
    generator.print_queries(limit=args.limit)
    
    # Exporta
    report_path = generator.export_json()
    console.print(f"\n[green]✅ Relatório de demonstração salvo em: {report_path}[/green]")
    
    return 0


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="REDCap Data Quality Intelligence Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python main.py --test-connection     Testa conexão com REDCap
  python main.py --analyze             Executa análise completa
  python main.py --analyze -v          Análise com queries detalhadas
  python main.py --demo                Demo com dados fictícios
        """,
    )
    
    # Modos de operação
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--test-connection", "-t",
        action="store_true",
        help="Testa conexão com a API REDCap",
    )
    mode_group.add_argument(
        "--analyze", "-a",
        action="store_true",
        help="Executa análise completa de qualidade",
    )
    mode_group.add_argument(
        "--demo", "-d",
        action="store_true",
        help="Executa demonstração com dados fictícios",
    )
    
    # Opções de análise
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Exibe queries detalhadas no console",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=20,
        help="Limite de queries a exibir (padrão: 20)",
    )
    parser.add_argument(
        "--priority", "-p",
        choices=["Alta", "Média", "Baixa"],
        help="Filtrar queries por prioridade",
    )
    parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Incluir análise de logs de auditoria",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Caminho para salvar o relatório JSON",
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    if args.test_connection:
        return test_connection(args)
    elif args.analyze:
        return run_analysis(args)
    elif args.demo:
        return run_demo(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
