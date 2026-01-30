"""
REDCap Data Quality Intelligence Agent - Web Application

Interface web visual para pesquisadores executarem análises.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, Response, session, redirect, url_for, flash

import io

import sys
sys.path.insert(0, str(Path(__file__).parent))

import config
from src.redcap_client import REDCapClient, REDCapAPIError
from src.query_generator import QueryGenerator
from src.pdf_generator import PDFReportGenerator
from src.models import QualityReport
from src.ai_analyzer import AIAnalyzer
from src.auth_manager import auth_manager, login_required
from src.db_manager import db

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = config.SECRET_KEY

# Armazena última análise para download e paginação
# Cache em memória para análises (por usuário)
# Em produção, idealmente usaria Redis ou arquivo temporário
analysis_cache = {}

def get_analysis_context(user_id):
    """Recupera contexto de análise do usuário."""
    if not user_id:
        return None
    return analysis_cache.get(user_id, {
        "report": None, "project_name": None, "queries": [], 
        "client": None, "project_id": None, "field_labels": {}, "field_names": []
    })

def update_analysis_context(user_id, data):
    """Atualiza contexto de análise do usuário."""
    if not user_id:
        return
    if user_id not in analysis_cache:
        analysis_cache[user_id] = {}
    analysis_cache[user_id].update(data)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Página de Cadastro."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        organization = request.form.get('organization')
        role = request.form.get('role')
        role_outro = request.form.get('role_outro')
        
        # Validate passwords match
        if password != confirm_password:
            flash('As senhas não coincidem', 'error')
            return render_template('register.html')
        
        # Validate password length
        if len(password) < 8:
            flash('A senha deve ter pelo menos 8 caracteres', 'error')
            return render_template('register.html')
        
        result = auth_manager.register(email, password, full_name, organization, role, role_outro)
        if result['success']:
            flash(result.get('message', 'Conta criada com sucesso!'), 'success')
            return redirect(url_for('login'))
        else:
            flash(result['error'], 'error')
            
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de Login."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        result = auth_manager.login(email, password)
        if result['success']:
            return redirect(url_for('index'))
        else:
            flash(result['error'], 'error')
            
    return render_template('login.html')

@app.route('/login/google')
def login_google():
    """Iniciar login com Google"""
    auth_url = auth_manager.get_oauth_url('google')
    if auth_url:
        return redirect(auth_url)
    flash('Erro ao iniciar login com Google. Verifique a configuração do Supabase.', 'error')
    return redirect(url_for('login'))

@app.route('/auth/callback')
def auth_callback():
    """Callback do Supabase OAuth"""
    # Em um fluxo PKCE real, o Supabase redireciona com o token no hash da URL (#access_token=...)
    # O backend Flask não vê o hash da URL.
    # O fluxo correto com SSR + Supabase Auth geralmente requer que o redirecionamento vá para uma página frontend
    # que captura o hash e envia para o backend, OU usar o fluxo de Code Exchange.
    
    # Para simplificar neste MVP, vamos redirecionar para uma página de "Processando Login..."
    # que captura o token do hash e envia para uma rota de set-session via POST.
    return render_template('auth_callback.html')

@app.route('/auth/set_session', methods=['POST'])
def auth_set_session():
    """Define a sessão Flask a partir do token recebido do frontend"""
    try:
        data = request.get_json()
        if not data:
             return jsonify({"success": False, "error": "Invalid JSON"}), 400

        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        code = data.get('code')
        
        if code:
            # Auth Code Flow (PKCE/Server-side)
            result = auth_manager.exchange_code(code)
            return jsonify(result)
        
        if not access_token:
            return jsonify({"success": False, "error": "Token ou Código ausente"}), 400
            
        result = auth_manager.set_session(access_token, refresh_token)
        return jsonify(result)
    except Exception as e:
        print(f"Error in auth_set_session: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/logout')
def logout():
    """Logout do usuário."""
    auth_manager.logout()
    return redirect(url_for('login'))


@app.route('/auth/confirm')
def auth_confirm():
    """Página de confirmação de e-mail (callback do Supabase)."""
    # Supabase redireciona com tokens na URL fragment (#access_token=...)
    # Como o fragment não chega ao servidor, mostramos a página de sucesso
    # e deixamos o frontend processar o token se necessário
    
    # Verificar se há parâmetros de erro
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    
    if error:
        return render_template('confirm.html', status='error', message=error_description)
    
    # Token type indica confirmação bem-sucedida
    token_type = request.args.get('type')
    
    if token_type == 'signup' or token_type == 'email':
        return render_template('confirm.html', status='success')
    
    # Default: mostrar sucesso (Supabase redireciona após confirmação)
    return render_template('confirm.html', status='success')


@app.context_processor
def inject_user():
    """Inject user data into all templates."""
    user_name = session.get('user_name')
    if not user_name and session.get('user_email'):
        user_name = session.get('user_email').split('@')[0]
    
    return dict(
        user_name=user_name,
        user_id=session.get('user_id'),
        user_email=session.get('user_email')
    )


@app.route('/')
@login_required
def index():
    """Página principal."""
    return render_template('index.html')


@app.route('/design-system')
@login_required
def design_system():
    """Página de showcase do Design System."""
    return render_template('design-system.html')


@app.after_request
def add_header(response):
    """Adiciona headers para evitar cache agressivo (corrige problema de updates de UI)."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """Testa conexão com a API REDCap."""
    try:
        data = request.get_json()
        # Tenta pegar do payload ou variáveis de ambiente (fallback)
        api_url = data.get('api_url', '').strip() or os.getenv('REDCAP_API_URL')
        api_token = data.get('api_token', '').strip() or os.getenv('REDCAP_API_TOKEN')
        
        if not api_url or not api_token:
            return jsonify({
                'success': False,
                'error': 'URL e Token são obrigatórios'
            }), 400
        
        # Debug: show what we're receiving (Safe logging)
        print(f"[DEBUG test-connection] Testing connection to REDCap...", flush=True)
        
        # STEP 1: Quick connection test (uses lightweight 'version' API call)
        client = REDCapClient(api_url, api_token)
        client.test_connection()  # Raises REDCapAPIError if fails
        
        # STEP 2: Only after connection confirmed, get project info
        print(f"[DEBUG test-connection] Connection OK, fetching project info...", flush=True)
        project_info = client.export_project_info()
        
        # Persiste o client no contexto do usuário
        user_id = session.get('user_id')
        token = session.get('access_token')
        
        # IMPORTANTE: Limpa cache antigo ao conectar a um novo projeto
        # Isso evita que dados do projeto anterior fiquem persistidos
        if user_id and user_id in analysis_cache:
            print(f"[DEBUG test-connection] Clearing previous cache for user {user_id[:8]}...", flush=True)
            del analysis_cache[user_id]
        
        # Prepara dados para o contexto (iniciando do zero)
        context_update = {
            'client': client,
            'project_name': project_info.get('project_title', 'Projeto REDCap'),
            'user_id': user_id,
            'report': None,
            'queries': [],
            'field_labels': {},
            'field_names': []
        }
        
        project_id = None
        
        if user_id:
            # Salva projeto de forma não-bloqueante (erro no DB não impede o teste)
            try:
                project_id = db.save_project(
                    user_id=user_id,
                    project_title=project_info.get('project_title', 'Projeto REDCap'),
                    api_url=api_url,
                    redcap_project_id=project_info.get('project_id'),
                    is_longitudinal=project_info.get('is_longitudinal', False),
                    token=token
                )
            except Exception as db_error:
                print(f"[WARN] Erro ao salvar projeto no banco (não crítico): {db_error}", flush=True)
                project_id = None
            context_update['project_id'] = project_id
            
            # Atualiza cache seguro
        if user_id:
            session['api_url'] = api_url
            session['api_token'] = api_token
            try:
                update_analysis_context(user_id, context_update)
            except Exception as cache_error:
                print(f"[WARN] Erro ao atualizar cache (não crítico): {cache_error}", flush=True)
            
        return jsonify({
            'success': True,
            'project': {
                'title': project_info.get('project_title', 'N/A'),
                'id': project_info.get('project_id', 'N/A'),
                'is_longitudinal': project_info.get('is_longitudinal', False),
            }
        })
        
    except REDCapAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro inesperado: {str(e)}'
        }), 500


def _build_queries_page(queries, client, labels_map=None):
    """Constrói lista de queries para exibição."""
    if labels_map is None:
        labels_map = {}
        
    queries_preview = []
    for q in queries:
        # Gera link direto para o REDCap
        # Obtém label do campo (limita tamanho se necessário)
        field_label = labels_map.get(q.field, "")
        
        redcap_link = client.generate_field_url(
            record_id=q.record_id,
            event=q.event if q.event != "N/A" else "",
            instrument=q.instrument if q.instrument != "N/A" else "",
            field=q.field,
            field_label=field_label,
        )
        # Remove HTML tags simples se houver
        if field_label and "<" in field_label:
            import re
            field_label = re.sub(r'<[^>]*>', '', field_label)
        
        queries_preview.append({
            'record_id': q.record_id,
            'event': q.event,
            'instrument': q.instrument,
            'field': q.field,
            'field_label': field_label,
            'value': str(q.value_found) if q.value_found is not None and str(q.value_found) != "" else 'N/A',
            'issue_type': config.ISSUE_TYPES.get(q.issue_type, q.issue_type),
            'explanation': q.explanation,
            'priority': q.priority,
            'suggested_action': q.suggested_action,
            'redcap_link': redcap_link,
        })
    return queries_preview


@app.route('/api/queries', methods=['GET'])
def get_queries_page():
    """Retorna página de queries com paginação."""
    try:
        user_id = session.get('user_id')
        ctx = get_analysis_context(user_id)
        
        if not ctx or not ctx['queries']:
            return jsonify({'success': False, 'error': 'Execute uma análise primeiro'}), 400
        
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 50, type=int)
        priority_filter = request.args.get('priority', None)
        search_term = request.args.get('search', '').strip().lower()
        
        # print(f"DEBUG_PAGINATION: Page={page}, Size={page_size}, Search='{search_term}'", flush=True)
        # print(f"DEBUG_FULL_ARGS: {dict(request.args)}", flush=True)
        
        queries = ctx['queries']
        client = ctx['client']
        field_labels = ctx.get('field_labels', {})
        
        # Captura filtros de coluna
        filter_record_id = request.args.get('filter_record_id', '').strip().lower()
        filter_event = request.args.get('filter_event_id', '').strip().lower()
        filter_field = request.args.get('filter_field', '').strip().lower()
        filter_value = request.args.get('filter_value', '').strip().lower()
        filter_issue_type = request.args.get('filter_issue_type', '').strip().lower()
        filter_priority = request.args.get('filter_priority', '').strip().lower()

        # DEBUG LOGS
        # print(f"DEBUG_FILTER_PARAMS: Val='{filter_value}', Pri='{filter_priority}', Field='{filter_field}'", flush=True)

        
        # 1. Filtra por prioridade (Botões Superiores)
        if priority_filter and priority_filter.lower() in ['alta', 'média', 'baixa', 'media']:
            # Mapa para normalizar
            norm_map = {'media': 'média'}
            p_val = norm_map.get(priority_filter.lower(), priority_filter.lower())
            
            # DEBUG: Log what we are looking for
            # print(f"DEBUG_PRIORITY: Filtering for '{p_val}'", flush=True)
            queries = [
                q for q in queries 
                if q.priority and str(q.priority).strip().lower() == p_val
            ]

        # 2. Filtros de Coluna (Excel-like) - Lógica OR entre opções selecionadas
        def check_filter(text_val, filter_input, field_name="unknown"):
            if not filter_input:
                return True
            # Converte o valor da célula para string minúscula
            text_val = str(text_val).strip().lower() if text_val is not None else ""
            
            # Opções marcadas (separadas por vírgula)
            search_terms = [t.strip() for t in filter_input.split(',')]
            
            # Exact Match
            match = any(term == text_val for term in search_terms if term)
            return match

        if filter_record_id:
            queries = [q for q in queries if check_filter(q.record_id, filter_record_id, 'record')]
        if filter_event:
            queries = [q for q in queries if check_filter(q.event, filter_event, 'event')]
        if filter_field:
            queries = [q for q in queries if check_filter(q.field, filter_field, 'field')]
        if filter_value:
            queries = [q for q in queries if check_filter(q.value_found, filter_value, 'value')]
        if filter_issue_type:
            queries = [q for q in queries if check_filter(q.issue_type, filter_issue_type, 'issue')]
        if filter_priority:
            queries = [q for q in queries if check_filter(q.priority, filter_priority, 'priority')]

        import unicodedata
        def remove_accents(input_str):
            if not input_str: return ""
            nfkd_form = unicodedata.normalize('NFKD', str(input_str))
            return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

        # 3. Busca Global Expandida (com remoção de acentos)
        if search_term:
            # print(f"[DEBUG search] Searching for: '{search_term}' | Page Size: {page_size}", flush=True)
            search_normalized = remove_accents(search_term)
            
            def match_field(val):
                return search_normalized in remove_accents(val)

            queries_before = len(queries)
            queries = [
                q for q in queries 
                if match_field(q.record_id) or 
                match_field(q.event) or
                match_field(q.field) or 
                match_field(field_labels.get(q.field, "")) or
                match_field(q.value_found) or
                match_field(q.issue_type) or
                match_field(q.explanation) or
                match_field(q.priority) or
                match_field(q.suggested_action)
            ]
            # print(f"[DEBUG search] Results: {len(queries)} (was {queries_before})", flush=True)
        
        # Calcula paginação
        total_queries = len(queries)
        total_pages = (total_queries + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        page_queries = queries[start_idx:end_idx]
        queries_preview = _build_queries_page(page_queries, client, ctx.get('field_labels', {}))
        
        return jsonify({
            'success': True,
            'queries': queries_preview,
            'page': page,
            'page_size': page_size,
            'total_queries': total_queries,
            'total_pages': total_pages,
            'debug_params': {
                'received_value': request.args.get('filter_value', ''),
                'received_field': request.args.get('filter_field', ''),
                'active_columns': [k for k in request.args.keys() if k.startswith('filter_')]
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro no servidor ao filtrar: {str(e)}'
        }), 500


@app.route('/api/filter-options', methods=['GET'])
def get_filter_options():
    """Retorna opções únicas para os filtros (dropdowns)."""
    user_id = session.get('user_id')
    ctx = get_analysis_context(user_id)
    
    print(f"DEBUG: get_filter_options called for user {user_id}", flush=True)
    # RE-DEPLOY TRIGGER
    if not ctx or not ctx['queries']:
        print("DEBUG: No context or queries found for options", flush=True)
        return jsonify({'success': False, 'options': {}})
    
    try:
        queries = ctx['queries']
        field_labels = ctx.get('field_labels', {})
        
        # OTIMIZAÇÃO: Loop único para evitar 4 iterações em lista gigante
        # E Limite de itens para evitar OOM/Timeout em projetos grandes (17k+ items)
        rec_set = set()
        evt_set = set()
        fld_set = set()
        val_set = set()
        
        MAX_OPTIONS = 1000  # Limite de segurança para dropdowns
        
        for q in queries:
            try:
                # Record ID
                if q.record_id and len(rec_set) < MAX_OPTIONS:
                    rec_set.add(str(q.record_id))
                
                # Event
                if q.event and q.event != "N/A" and len(evt_set) < MAX_OPTIONS:
                    evt_set.add(str(q.event))
                    
                # Field
                if q.field and len(fld_set) < MAX_OPTIONS:
                    fld_set.add(q.field)
                    
                # Value
                if q.value_found is not None and len(val_set) < MAX_OPTIONS:
                     v_str = str(q.value_found)
                     if v_str != "":
                         val_set.add(v_str)
            except:
                pass

        # Converte para listas ordenadas
        record_ids = sorted(list(rec_set))
        events = sorted(list(evt_set))
        fields = sorted(list(fld_set))
        values = sorted(list(val_set))
        
        fields_data = []
        for f in fields:
            fields_data.append({
                'value': f,
                'label': f + (f" ({field_labels.get(f, '')})" if field_labels.get(f) else "")
            })
            
        return jsonify({
            'success': True,
            'options': {
                'record_id': record_ids if len(record_ids) < MAX_OPTIONS else record_ids + ["(Muitos itens...)"],
                'event_id': events,
                'field': fields_data, 
                'value': values if len(values) < MAX_OPTIONS else values + ["(Muitos itens...)"]
            },
            'meta': {
                'total_queries': len(queries),
                'truncated': len(queries) > MAX_OPTIONS
            }
        })
            
    except Exception as e:
        print(f"ERROR in get_filter_options: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Executa análise de qualidade."""
    global analysis_cache
    
    try:
        data = request.get_json() or {}
        
        # Prioridade: Session > Payload > Env
        api_url = session.get('api_url') or data.get('api_url', '').strip() or os.getenv('REDCAP_API_URL')
        api_token = session.get('api_token') or data.get('api_token', '').strip() or os.getenv('REDCAP_API_TOKEN')
        include_logs = data.get('include_logs', False)
        structural_checks = data.get('structural_checks', None)
        
        if not api_url or not api_token:
            return jsonify({
                'success': False,
                'error': 'URL e Token são obrigatórios'
            }), 400
        
        # Conecta e exporta dados
        client = REDCapClient(api_url, api_token)
        project_info = client.export_project_info()
        project_data = client.export_all_data(include_logs=include_logs)
        
        # Get user_id for custom rules
        user_id = session.get('user_id')
        access_token = session.get('access_token')
        
        # Executa análise
        generator = QueryGenerator(
            project_data=project_data,
            include_operational=include_logs,
            user_id=user_id,
            access_token=access_token,
            active_checks=structural_checks,
        )
        queries = generator.run_all_analyzers()
        report = generator.generate_report()
        
        token = access_token
        
        # Prepara contexto
        ctx_update = {
            'report': report,
            'project_name': project_info.get('project_title', 'Projeto REDCap'),
            'queries': queries,
            'client': client
        }
        
        # Cache field names and labels for AI context and UI
        try:
            ctx_update['field_names'] = [f.field_name for f in project_data.metadata]
            ctx_update['field_labels'] = {f.field_name: f.field_label for f in project_data.metadata}
        except:
            ctx_update['field_names'] = []
            ctx_update['field_labels'] = {}
        
        # Contagem por prioridade
        from collections import Counter
        priority_counts = Counter(q.priority for q in queries)
        type_counts = Counter(q.issue_type for q in queries)
        
        # Determine duration (mock for now or calc actual)
        duration_ms = 0 # Placeholder
        
        # Save analysis to DB
        # Look for project_id in cache first, if not there, context isn't fully set yet
        ctx = get_analysis_context(user_id)
        project_id = ctx.get('project_id') if ctx else None
        
        # If project_id is missing (session lost?), try to save project again
        if user_id and not project_id:
            try:
                project_id = db.save_project(
                    user_id=user_id,
                    project_title=project_info.get('project_title', 'Projeto REDCap'),
                    api_url=api_url,
                    redcap_project_id=project_info.get('project_id'),
                    is_longitudinal=project_info.get('is_longitudinal', False),
                    token=token
                )
            except Exception as db_err:
                print(f"[WARN] Erro ao salvar projeto no analyze: {db_err}", flush=True)
                project_id = None
            
        if user_id and project_id:
            try:
                analysis_id = db.save_analysis(   
                    user_id=user_id,
                    project_id=project_id,
                    report=report,
                    ai_analysis_used=False,
                    duration_ms=duration_ms,
                    token=token,
                    project_title=project_info.get('project_title', 'Projeto sem título')
                )
                
                # Update counts
                db.update_analysis_counts(
                    analysis_id,
                    high=priority_counts.get('Alta', 0),
                    medium=priority_counts.get('Média', 0),
                    low=priority_counts.get('Baixa', 0),
                    token=token
                )
            except Exception as db_err:
                print(f"[WARN] Erro ao salvar análise no DB: {db_err}", flush=True)
                
        if user_id:
            ctx_update['project_id'] = project_id
            update_analysis_context(user_id, ctx_update)
            
        # Prepara primeira página de queries (50 por página)
        page_size = 50
        queries_preview = _build_queries_page(queries[:page_size], client, ctx_update.get('field_labels', {}))
        
        return jsonify({
            'success': True,
            'summary': {
                'project_name': project_info.get('project_title', 'N/A'),
                'total_records': report.project_summary.total_records,
                'total_queries': report.project_summary.total_queries_generated,
                'high_priority': priority_counts.get('Alta', 0),
                'medium_priority': priority_counts.get('Média', 0),
                'low_priority': priority_counts.get('Baixa', 0),
                'most_common_errors': [
                    config.ISSUE_TYPES.get(t, t) 
                    for t in report.project_summary.most_common_error_types[:5]
                ],
                'fields_with_issues': report.project_summary.fields_with_most_issues[:5],
            },
            'queries': queries_preview,
            'total_queries_available': len(queries),
            'page': 1,
            'page_size': page_size,
            'total_pages': (len(queries) + page_size - 1) // page_size,
        })
        
    except REDCapAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro inesperado: {str(e)}'
        }), 500


@app.route('/api/ai-analysis', methods=['POST'])
def ai_analysis():
    """Executa análise com IA (LangChain + Claude)."""
    user_id = session.get('user_id')
    ctx = get_analysis_context(user_id)
    
    if not ctx or not ctx['report']:
        return jsonify({
            'success': False,
            'error': 'Execute uma análise primeiro'
        }), 400
    
    try:
        from src.ai_analyzer import AIAnalyzer
        
        ai = AIAnalyzer()
        
        if not ai.is_available:
            return jsonify({
                'success': False,
                'error': 'Configure ANTHROPIC_API_KEY no arquivo .env para usar análise com IA'
            }), 400
        
        # Gera resumo executivo
        summary = ai.generate_report_summary(ctx['report'])
        
        return jsonify({
            'success': True,
            'ai_summary': summary,
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro na análise de IA: {str(e)}'
        }), 500


@app.route('/api/download/pdf')
def download_pdf():
    """Download do relatório em PDF."""
    user_id = session.get('user_id')
    ctx = get_analysis_context(user_id)
    
    if not ctx or not ctx['report']:
        return jsonify({'error': 'Nenhuma análise disponível'}), 400
    
    try:
        pdf_gen = PDFReportGenerator(
            report=ctx['report'],
            project_name=ctx['project_name'] or 'Projeto REDCap',
            field_labels=ctx.get('field_labels', {}),
            user_name=session.get('user_name', 'Usuário AuditPRO')
        )
        pdf_bytes = pdf_gen.generate_bytes()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"quality_report_{timestamp}.pdf"
        
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500






@app.route('/api/download/json')
def download_json():
    """Download do relatório em JSON."""
    user_id = session.get('user_id')
    ctx = get_analysis_context(user_id)
    
    if not ctx or not ctx['report']:
        return jsonify({'error': 'Nenhuma análise disponível'}), 400
    
    try:
        json_data = json.dumps(
            ctx['report'].to_dict(),
            ensure_ascii=False,
            indent=2
        )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"quality_report_{timestamp}.json"
        
        return Response(
            json_data,
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/csv')
def download_csv():
    """Download do relatório em CSV."""
    user_id = session.get('user_id')
    ctx = get_analysis_context(user_id)
    
    if not ctx or not ctx['report']:
        return jsonify({'error': 'Nenhuma análise disponível'}), 400
    
    try:
        import csv
        from io import StringIO
        
        queries = ctx['queries']
        field_labels = ctx.get('field_labels', {})
        client = ctx.get('client')
        
        si = StringIO()
        cw = csv.writer(si)
        
        # Headers
        cw.writerow(['Record ID', 'Event', 'Instrument', 'Field', 'Field Label', 'Value', 'Issue Type', 'Priority', 'Explanation', 'Suggested Action', 'REDCap Link'])
        
        for q in queries:
            # Generate Link
            link = ""
            if client:
                 link = client.generate_field_url(
                    record_id=q.record_id,
                    event=q.event if q.event != "N/A" else "",
                    instrument=q.instrument if q.instrument != "N/A" else "",
                    field=q.field
                )
            
            label = field_labels.get(q.field, "")
            # Clean label
            if label and '<' in label:
                import re
                label = re.sub(r'<[^>]*>', '', label)
                
            cw.writerow([
                q.record_id,
                q.event,
                q.instrument,
                q.field,
                label,
                q.value_found,
                config.ISSUE_TYPES.get(q.issue_type, q.issue_type),
                q.priority,
                q.explanation,
                q.suggested_action,
                link
            ])
            
        output = si.getvalue()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"quality_report_{timestamp}.csv"
        
        # Add BOM for Excel compatibility with UTF-8
        bom_output = '\ufeff' + output
        
        return Response(
            bom_output,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/queries/save', methods=['POST'])
def save_query():
    """Salva uma query (bookmark/issue)."""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
            
        data = request.get_json()
        ctx = get_analysis_context(user_id)
        project_id = ctx.get('project_id') if ctx else None
        
        # Se não houver project_id na sessão, tenta pegar do payload ou falha
        if not project_id:
             project_id = data.get('project_id')
             
        query_id = db.save_query_issue(user_id, project_id, data)
        
        if query_id:
            db.log_audit_event(user_id, 'save_query', 'saved_queries', query_id)
            return jsonify({'success': True, 'query_id': query_id, 'message': 'Query salva com sucesso'})
        
        return jsonify({'success': False, 'error': 'Erro ao salvar query'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/queries/saved', methods=['GET'])
def get_saved_queries():
    """Lista queries salvas."""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
            
        project_id = request.args.get('project_id')
        queries = db.get_saved_queries(user_id, project_id)
        
        return jsonify({'success': True, 'queries': queries})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== CUSTOM RULES API ====================

from src.rules_manager import rules_manager


@app.route('/api/rules', methods=['GET'])
def get_rules():
    """Lista todas as regras customizadas."""
    try:
        user_id = session.get('user_id')
        token = session.get('access_token')
        rules = rules_manager.load_rules(user_id, token)
        return jsonify({
            'success': True,
            'rules': [r.to_dict() for r in rules]
        })
    except Exception as e:
        # Retry logic for JWT Expiration
        if "JWT expired" in str(e) or "PGRST303" in str(e):
            refresh_token = session.get('refresh_token')
            if refresh_token:
                res = auth_manager.refresh_session(refresh_token)
                if res.get('success'):
                    try:
                        # Retry with new token
                        new_token = res['access_token']
                        rules = rules_manager.load_rules(user_id, new_token)
                        return jsonify({
                            'success': True,
                            'rules': [r.to_dict() for r in rules]
                        })
                    except Exception as retry_e:
                        print(f"Erro ao retentar carregar regras: {retry_e}")
                        pass # Fall through to generic error
                else:
                     return jsonify({'success': False, 'error': 'Sessão expirada. Por favor, faça login novamente.'}), 401
            else:
                 return jsonify({'success': False, 'error': 'Sessão expirada. Por favor, faça login novamente.'}), 401

        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rules', methods=['POST'])
def create_rule():
    """Cria uma nova regra customizada."""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
        
        print(f"DEBUG create_rule: user_id={user_id} (type={type(user_id).__name__})")
        
        token = session.get('access_token')
        data = request.json
        
        print(f"DEBUG create_rule: Calling add_rule with data: {data}")
        
        rule = rules_manager.add_rule(data, user_id, token)
        
        print(f"DEBUG create_rule: Returned rule: {rule}")
        
        if not rule:
             return jsonify({'success': False, 'error': 'Erro ao salvar regra no banco de dados. Verifique os logs do servidor.'}), 500
        
        # Audit Log
        db.log_audit_event(user_id, 'create_rule', 'custom_rules', rule.id, data)
        
        return jsonify({
            'success': True,
            'rule': rule.to_dict(),
            'message': 'Regra criada com sucesso'
        })
    except Exception as e:
        # Retry logic for JWT Expiration
        if "JWT expired" in str(e) or "PGRST303" in str(e):
            refresh_token = session.get('refresh_token')
            if refresh_token:
                res = auth_manager.refresh_session(refresh_token)
                if res.get('success'):
                    try:
                        # Retry with new token
                        new_token = res['access_token']
                        rule = rules_manager.add_rule(data, user_id, new_token)
                        
                        if rule:
                             db.log_audit_event(user_id, 'create_rule', 'custom_rules', rule.id, rule.to_dict())
                             return jsonify({
                                'success': True,
                                'rule': rule.to_dict(),
                                'message': 'Regra criada com sucesso'
                             })
                    except Exception:
                        pass # Fall through to generic error
                else:
                     return jsonify({'success': False, 'error': 'Sessão expirada. Por favor, faça login novamente.'}), 401
            else:
                 return jsonify({'success': False, 'error': 'Sessão expirada. Por favor, faça login novamente.'}), 401

        print(f"Erro ao criar regra: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500





@app.route('/api/rules/<rule_id>', methods=['GET'])
def get_rule(rule_id):
    """Obtém uma regra específica."""
    try:
        user_id = session.get('user_id')
        token = session.get('access_token')
        rule = rules_manager.get_rule(rule_id, user_id, token)
        
        if rule:
            return jsonify({
                'success': True,
                'rule': rule.to_dict()
            })
        else:
            return jsonify({'success': False, 'error': 'Regra não encontrada'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rules/generate', methods=['POST'])
@login_required
def generate_rule():
    """Gera uma regra a partir de linguagem natural usando IA."""
    try:
        user_id = session.get('user_id') # Ensure user_id is fetched
        data = request.json
        text = data.get('text')
        
        if not text:
            return jsonify({'success': False, 'error': 'Texto da regra é obrigatório'}), 400
            
        # Contexto: Campos
        project_fields = []
        ctx = get_analysis_context(user_id)
        if ctx and ctx.get('field_names'):
            project_fields = ctx.get('field_names')
            
        # Contexto: Eventos (Novo)
        project_events = []
        if ctx and ctx.get('project_events'):
            # Extract simple names
            project_events = [e['unique_event_name'] for e in ctx['project_events']]
        
        ai = AIAnalyzer()
        if not ai.is_available:
             return jsonify({'success': False, 'error': 'IA não configurada no servidor (API Key ausente).'}), 503
        
        # Passa ambos os contextos
        result = ai.parse_natural_language_rule(text, project_fields, project_events)
        
        if result['success']:
            return jsonify({
                'success': True,
                'rule': result['rule']
            })
        else:
             return jsonify({
                'success': False, 
                'error': result.get('error', 'Falha ao gerar regra')
            }), 400
            
    except Exception as e:
        print(f"Erro ao gerar regra com IA: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500





@app.route('/api/rules/<rule_id>', methods=['PUT'])
def update_rule(rule_id):
    """Atualiza uma regra existente."""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
            
        data = request.get_json()
        token = session.get('access_token')
        rule = rules_manager.update_rule(rule_id, data, user_id, token)
        
        # Audit Log
        if rule:
             db.log_audit_event(user_id, 'update_rule', 'custom_rules', rule.id, data)
        
        if rule:
            return jsonify({
                'success': True,
                'rule': rule.to_dict(),
                'message': 'Regra atualizada com sucesso'
            })
        return jsonify({'success': False, 'error': 'Regra não encontrada'}), 404
    except Exception as e:
        # Retry logic for JWT Expiration
        if "JWT expired" in str(e) or "PGRST303" in str(e):
             refresh_token = session.get('refresh_token')
             if refresh_token:
                 res = auth_manager.refresh_session(refresh_token)
                 if res.get('success'):
                     try:
                         new_token = res['access_token']
                         rule = rules_manager.update_rule(rule_id, data, user_id, new_token)
                         if rule:
                             db.log_audit_event(user_id, 'update_rule', 'custom_rules', rule.id, data)
                             return jsonify({
                                'success': True,
                                'rule': rule.to_dict(),
                                'message': 'Regra atualizada com sucesso'
                             })
                     except Exception as retry_e:
                         return jsonify({'success': False, 'error': str(retry_e)}), 500
                 else:
                       return jsonify({'success': False, 'error': 'Sessão expirada. Por favor, faça login novamente.'}), 401
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rules/<rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    """Remove uma regra."""
    try:
        user_id = session.get('user_id')
        token = session.get('access_token')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
            
        success = rules_manager.delete_rule(rule_id, user_id, token)
        
        if success:
            db.log_audit_event(user_id, 'delete_rule', 'custom_rules', rule_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Regra removida com sucesso'
            })
        return jsonify({'success': False, 'error': 'Regra não encontrada ou erro ao excluir'}), 404
    except Exception as e:
        # Retry logic for JWT Expiration
        if "JWT expired" in str(e) or "PGRST303" in str(e):
             refresh_token = session.get('refresh_token')
             if refresh_token:
                 res = auth_manager.refresh_session(refresh_token)
                 if res.get('success'):
                     try:
                         new_token = res['access_token']
                         success = rules_manager.delete_rule(rule_id, user_id, new_token)
                         if success:
                             db.log_audit_event(user_id, 'delete_rule', 'custom_rules', rule_id)
                             return jsonify({
                                'success': True,
                                'message': 'Regra removida com sucesso'
                             })
                     except Exception as retry_e:
                         return jsonify({'success': False, 'error': str(retry_e)}), 500
                 else:
                       return jsonify({'success': False, 'error': 'Sessão expirada. Por favor, faça login novamente.'}), 401
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rules/<rule_id>/toggle', methods=['POST'])
def toggle_rule(rule_id):
    """Ativa/desativa uma regra."""
    try:
        user_id = session.get('user_id')
        token = session.get('access_token')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
            
        rule = rules_manager.toggle_rule(rule_id, user_id, token)
        
        if rule:
            status = "ativada" if rule.enabled else "desativada"
            return jsonify({
                'success': True,
                'rule': rule.to_dict(),
                'message': f'Regra {status} com sucesso'
            })
        return jsonify({'success': False, 'error': 'Regra não encontrada'}), 404
    except Exception as e:
        # Retry logic for JWT Expiration
        if "JWT expired" in str(e) or "PGRST303" in str(e):
             refresh_token = session.get('refresh_token')
             if refresh_token:
                 res = auth_manager.refresh_session(refresh_token)
                 if res.get('success'):
                     try:
                         new_token = res['access_token']
                         rule = rules_manager.toggle_rule(rule_id, user_id, new_token)
                         if rule:
                             status = "ativada" if rule.enabled else "desativada"
                             return jsonify({
                                'success': True,
                                'rule': rule.to_dict(),
                                'message': f'Regra {status} com sucesso'
                             })
                     except Exception as retry_e:
                         return jsonify({'success': False, 'error': str(retry_e)}), 500
                 else:
                       return jsonify({'success': False, 'error': 'Sessão expirada. Por favor, faça login novamente.'}), 401
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rules/generate', methods=['POST'])
def generate_rule_from_text():
    """Gera uma regra a partir de texto usando IA."""
    print("DEBUG: Received request for /api/rules/generate")
    try:
        data = request.get_json()
        print(f"DEBUG: Request payload: {data}")
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({'success': False, 'error': 'Texto da regra é obrigatório'}), 400
            

            
        print("DEBUG: Initializing AIAnalyzer")
        ai = AIAnalyzer()
        
        # Get field context from user cache
        user_id = session.get('user_id')
        ctx = get_analysis_context(user_id)
        field_list = ctx.get('field_names') if ctx else []
        
        # Lazy load if missing but client exists
        client = ctx.get('client') if ctx else None
        
        if not field_list and client:
            try:
                print("DEBUG: Lazy loading metadata for AI context...")
                metadata = client.export_metadata()
                field_list = [f.field_name for f in metadata]
                if ctx:
                    ctx['field_names'] = field_list
                    update_analysis_context(user_id, {'field_names': field_list})
                print(f"DEBUG: Loaded {len(field_list)} fields")
            except Exception as e:
                print(f"DEBUG: Failed to lazy load metadata: {e}")
        
        print(f"DEBUG: Parsing rule: {text} with {len(field_list) if field_list else 0} context fields")
        result = ai.parse_natural_language_rule(text, field_list=field_list)
        print(f"DEBUG: AI Result: {result}")
        
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"DEBUG: Exception: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/fields', methods=['GET'])
@login_required
def get_project_fields():
    """Retorna lista de campos do projeto para seleção em regras."""
    try:
        user_id = session.get('user_id')
        ctx = get_analysis_context(user_id)
        
        # Check cached fields with labels first
        if ctx and ctx.get('fields_with_labels'):
            return jsonify({
                'success': True,
                'fields': ctx.get('fields_with_labels')
            })
        
        # Use client from context or reconstruct from session
        client = ctx.get('client') if ctx else None
        
        if not client:
            api_url = session.get('api_url')
            api_token = session.get('api_token')
            if api_url and api_token:
                try:
                    client = REDCapClient(api_url, api_token)
                except Exception as e:
                    print(f"Error reconstructing client: {e}")
            
        if not client:
            return jsonify({'success': False, 'error': 'Conexão não estabelecida ou expirada. Teste a conexão novamente.'}), 400
        
        # Fetch metadata
        metadata = client.export_metadata()
        
        fields = []
        for f in metadata:
            # Clean label (remove HTML tags)
            label = f.field_label or f.field_name
            if label and '<' in label:
                import re
                label = re.sub(r'<[^>]*>', '', label)
            
            fields.append({
                'field_name': f.field_name,
                'field_label': label[:80] if len(label) > 80 else label  # Truncate long labels
            })
            
        # Cache for future use (both formats for compatibility)
        if ctx is None:
            ctx = {}
        ctx['field_names'] = [f['field_name'] for f in fields]
        ctx['fields_with_labels'] = fields
        update_analysis_context(user_id, ctx)
            
        return jsonify({
            'success': True,
            'count': len(fields),
            'fields': fields
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/events', methods=['GET'])
@login_required
def get_project_events():
    """Retorna lista de eventos do projeto para regras Cross-Event."""
    try:
        user_id = session.get('user_id')
        ctx = get_analysis_context(user_id)
        
        # Check cached events first
        if ctx and ctx.get('project_events'):
            return jsonify({
                'success': True,
                'events': ctx.get('project_events')
            })
        
        # Use client from context or reconstruct from session
        client = ctx.get('client') if ctx else None
        
        if not client:
            api_url = session.get('api_url')
            api_token = session.get('api_token')
            if api_url and api_token:
                try:
                    client = REDCapClient(api_url, api_token)
                except Exception as e:
                    print(f"Error reconstructing client: {e}")
            
        if not client:
            return jsonify({'success': False, 'error': 'Conexão não estabelecida. Teste a conexão novamente.'}), 400
        
        # Fetch events (only works for longitudinal projects)
        try:
            events = client.export_events()
            
            events_list = []
            for evt in events:
                if hasattr(evt, 'unique_event_name'):
                    events_list.append({
                        'unique_event_name': evt.unique_event_name,
                        'event_name': getattr(evt, 'event_name', evt.unique_event_name)
                    })
                elif isinstance(evt, dict):
                    events_list.append({
                        'unique_event_name': evt.get('unique_event_name', ''),
                        'event_name': evt.get('event_name', evt.get('unique_event_name', ''))
                    })
            
            # Cache for future use
            if ctx is None:
                ctx = {}
            ctx['project_events'] = events_list
            update_analysis_context(user_id, ctx)
                
            return jsonify({
                'success': True,
                'count': len(events_list),
                'events': events_list
            })
        except Exception as e:
            # Non-longitudinal projects won't have events, return empty list
            print(f"Note: Project may not be longitudinal: {e}")
            return jsonify({
                'success': True,
                'count': 0,
                'events': [],
                'note': 'Project may not be longitudinal or events are not available.'
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/debug/fields', methods=['GET'])
@login_required
def debug_fields():
    """Rota de debug para listar campos do projeto."""
    try:
        user_id = session.get('user_id')
        api_url = session.get('api_url')
        token = session.get('access_token')
        
        if not api_url or not token:
            return jsonify({'success': False, 'error': 'Credenciais não encontradas na sessão'}), 401
            
        from src.redcap_client import REDCapClient
        client = REDCapClient(api_url, token)
        metadata = client.export_metadata()
        
        fields = []
        for f in metadata:
            fields.append({
                'field_name': f.field_name,
                'field_label': f.field_label
            })
            
        return jsonify({
            'success': True,
            'count': len(fields),
            'fields': fields
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/debug/cleanup-duplicates', methods=['GET'])
@login_required
def cleanup_duplicates():
    """Rota de manutenção para limpar regras de sistema duplicadas com IDs incorretos."""
    try:
        user_id = session.get('user_id')
        token = session.get('access_token')
        
        rules = rules_manager.load_rules(user_id, token)
        
        target_names = [
            "Violações de Branching Logic",
            "Campos Obrigatórios Vazios",
            "Formatos Inválidos",
            "Valores Fora do Limite (Range)",
            "Opções Inválidas (Choices)",
            "Análise Temporal (Cronologia)",
            "Análise Clínica (Consistência)",
            "Análise Clínica (Consistência e Fisiologia)", # Nomes podem ter variado
            "Análise Operacional (Logs)"
        ]
        
        deleted_count = 0
        deleted_names = []
        
        for rule in rules:
            # Se o nome está na lista de targets E o ID não começa com sys_
            # então é uma regra de sistema criada incorretamente (como custom)
            if rule.name in target_names and not rule.id.startswith('sys_'):
                if rules_manager.delete_rule(rule.id, user_id, token):
                    deleted_count += 1
                    deleted_names.append(f"{rule.name} ({rule.id})")
        
        return jsonify({
            'success': True,
            'message': f'Limpeza concluída. {deleted_count} regras removidas.',
            'deleted': deleted_names
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  REDCap Data Quality Intelligence Agent - Web Interface")
    print("="*60)
    print("\n  Acesse: http://localhost:5003")
    print("  Para encerrar, pressione Ctrl+C\n")
    app.run(debug=config.DEBUG, port=5003)

