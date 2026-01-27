"""
REDCap Data Quality Intelligence Agent - Configuration

Configuração centralizada para o agente de qualidade de dados.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# === REDCap API Configuration ===
REDCAP_API_URL = os.getenv("REDCAP_API_URL", "")
REDCAP_API_TOKEN = os.getenv("REDCAP_API_TOKEN", "")
REDCAP_TIMEOUT = int(os.getenv("REDCAP_TIMEOUT", "120"))

# === AI Configuration ===
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").lower() # 'anthropic' or 'openai'
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# === Authentication Configuration ===
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

# === Debug Mode ===
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# === Paths ===
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# === Clinical Validation Limits ===
# Limites fisiológicos padrão (podem ser sobrescritos por protocolo)
CLINICAL_LIMITS = {
    # Sinais vitais
    "systolic_bp": {"min": 50, "max": 250, "unit": "mmHg"},
    "diastolic_bp": {"min": 30, "max": 150, "unit": "mmHg"},
    "heart_rate": {"min": 30, "max": 220, "unit": "bpm"},
    "respiratory_rate": {"min": 8, "max": 40, "unit": "rpm"},
    "temperature": {"min": 32, "max": 42, "unit": "°C"},
    "oxygen_saturation": {"min": 50, "max": 100, "unit": "%"},
    
    # Antropometria
    "weight": {"min": 0.5, "max": 300, "unit": "kg"},
    "height": {"min": 30, "max": 250, "unit": "cm"},
    "age": {"min": 0, "max": 120, "unit": "anos"},
    
    # Laboratório (valores gerais)
    "glucose": {"min": 20, "max": 1000, "unit": "mg/dL"},
    "hemoglobin": {"min": 3, "max": 20, "unit": "g/dL"},
    "creatinine": {"min": 0.1, "max": 30, "unit": "mg/dL"},
    "potassium": {"min": 1.5, "max": 10, "unit": "mEq/L"},
    "sodium": {"min": 100, "max": 180, "unit": "mEq/L"},
}

# === Query Priority Definitions ===
PRIORITY_LEVELS = {
    "Alta": [
        "Riscos para integridade do estudo",
        "Segurança do participante",
        "Desfechos incorretos",
        "Datas críticas",
        "Erros graves de lógica",
        "Critérios de inclusão/exclusão violados",
    ],
    "Média": [
        "Campos inconsistentes sem afetar segurança",
        "Campos sem afetar endpoints primários",
        "Valores fora de ranges não críticos",
    ],
    "Baixa": [
        "Problemas cosméticos",
        "Informações complementares",
        "Campos opcionais inconsistentes",
    ],
}

# === Issue Types ===
ISSUE_TYPES = {
    # Estruturais
    "required_field_empty": "Campo obrigatório vazio",
    "value_out_of_range": "Valor fora do range permitido",
    "invalid_format": "Formato inválido",
    "invalid_choice": "Código fora da lista de opções",
    "calculated_field_mismatch": "Campo calculado inconsistente",
    "branching_logic_violated": "Branching logic violada",
    "field_should_be_empty": "Campo preenchido quando deveria estar vazio",
    "field_should_have_value": "Campo vazio quando deveria ter valor",
    
    # Temporais
    "date_out_of_order": "Data fora de ordem cronológica",
    "followup_before_baseline": "Follow-up anterior à baseline",
    "event_out_of_timeline": "Evento fora da linha do tempo",
    "death_date_inconsistent": "Data de óbito inconsistente com visitas",
    "repeating_sequence_broken": "Sequência de repeating instrument quebrada",
    
    # Clínicos
    "physiologically_impossible": "Valor fisiologicamente impossível",
    "inclusion_criteria_violated": "Critério de inclusão violado",
    "exclusion_criteria_violated": "Critério de exclusão violado",
    "clinical_classification_mismatch": "Classificação clínica incorreta",
    
    # Operacionais
    "suspicious_edit_pattern": "Padrão de edição suspeito",
    "edit_after_closure": "Alteração após encerramento",
    "high_edit_volume": "Alto volume de edições",
}

# === Validation Settings ===
DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
]

# Campos que tipicamente são datas de referência
BASELINE_DATE_FIELDS = [
    "enrollment_date",
    "baseline_date",
    "consent_date",
    "study_start_date",
    "data_inclusao",
    "data_baseline",
]

# Campos que tipicamente são datas finais
CRITICAL_DATE_FIELDS = [
    "death_date",
    "data_obito",
    "withdrawal_date",
    "data_saida",
]
