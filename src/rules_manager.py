"""
REDCap Data Quality Intelligence Agent - Rules Manager

Gerenciador de regras customizadas para validação de dados.
"""

import uuid
from typing import Optional
from datetime import datetime
from datetime import datetime
from src.db_manager import db
import config


class CustomRule:
    """Representa uma regra customizada de validação."""
    
    def __init__(
        self,
        id: str,
        name: str,
        rule_type: str,
        field: str,
        operator: str,
        value: any,
        priority: str = "Média",
        message: str = "",
        enabled: bool = True,
        field2: Optional[str] = None,
        event1: Optional[str] = None,
        event2: Optional[str] = None,
        form1: Optional[str] = None,
        form2: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.id = id
        self.name = name
        self.rule_type = rule_type  # range, comparison, cross_field, regex, condition
        self.field = field
        self.operator = operator  # =, !=, <, >, <=, >=, between, contains, matches
        self.value = value
        self.priority = priority
        self.message = message
        self.enabled = enabled
        self.field2 = field2  # Para regras cross_field
        self.event1 = event1  # Evento do campo 1 (para cross_event)
        self.event2 = event2  # Evento do campo 2 (para cross_event)
        self.form1 = form1    # Formulário do campo 1
        self.form2 = form2    # Formulário do campo 2
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "name": self.name,
            "rule_type": self.rule_type,
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
            "priority": self.priority,
            "message": self.message,
            "enabled": self.enabled,
            "field2": self.field2,
            "event1": self.event1,
            "event2": self.event2,
            "form1": self.form1,
            "form2": self.form2,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CustomRule":
        """Cria instância a partir de dicionário."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            rule_type=data.get("rule_type", "comparison"),
            field=data.get("field", ""),
            operator=data.get("operator", "="),
            value=data.get("value"),
            priority=data.get("priority", "Média"),
            message=data.get("message", ""),
            enabled=data.get("enabled", True),
            field2=data.get("field2"),
            event1=data.get("event1"),
            event2=data.get("event2"),
            form1=data.get("form1"),
            form2=data.get("form2"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


class RulesManager:
    """Gerenciador CRUD para regras customizadas (Persistência via DB)."""
    
    def __init__(self):
        pass
    
    def load_rules(self, user_id=None, token=None) -> list[CustomRule]:
        """Carrega todas as regras do banco de dados."""
        if not user_id:
             # Retorna lista vazia ou regras globais se implementar cache/fallback
             return []
             
        data = db.get_custom_rules(user_id, token)
        
        data = db.get_custom_rules(user_id, token)
        
        # Garante que todas as regras de sistema existam
        self._ensure_system_rules(user_id, token, data)
        
        # Recarrega para incluir as recém-criadas
        data = db.get_custom_rules(user_id, token)
        
        # FILTRO DE LIMPEZA VISUAL (Remove duplicatas legadas)
        # Remove regras que têm nome de sistema mas ID incorreto (não começam com sys_)
        system_names = {
            "Violações de Branching Logic",
            "Campos Obrigatórios Vazios", 
            "Formatos Inválidos",
            "Valores Fora do Limite (Range)",
            "Opções Inválidas (Choices)",
            "Análise Temporal (Cronologia)",
            "Análise Clínica (Consistência)",
            "Análise Operacional (Logs)"
        }
        
        cleaned_data = []
        for r in data:
            # Se for um nome de sistema e ID não for sys_, ignora (é duplicata velha)
            if r['name'] in system_names and not str(r['id']).startswith('sys_'):
                # Opcional: Tenta deletar silenciosamente do banco para não voltar
                # self.delete_rule(r['id'], user_id, token) 
                continue
            cleaned_data.append(r)
            
        custom_rules = [CustomRule.from_dict(r) for r in cleaned_data]
        
        # Adiciona regras de sistema (hardcoded analyzers) para visualização
        system_rules = self.get_system_rules()
        
        return custom_rules + system_rules

    def _ensure_system_rules(self, user_id, token, existing_rules_data):
        """Garante que as regras de sistema existam no banco."""
        existing_ids = {r.get('id') for r in existing_rules_data}
        
        system_rules_definitions = [
            # Estruturais
            # Estruturais (Legacy removed)
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "name": "Branching Logic (Campos Ocultos)",
                "message": "Campo não deveria ter valor pois a lógica de branching o oculta",
                "rule_type": "system",
                "field": "branching_check", "operator": "check", "value": "Active", "priority": "Média", "enabled": True
            },
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "name": "Campos Obrigatórios (Missing)",
                "message": "Campo obrigatório está vazio",
                "rule_type": "system",
                "field": "missing_check", "operator": "check", "value": "Active", "priority": "Alta", "enabled": True
            },
            {
                "id": "00000000-0000-0000-0000-000000000005",
                "name": "Formatos Inválidos",
                "message": "Valor não corresponde ao formato do campo (data, email, etc)",
                "rule_type": "system",
                "field": "format_check", "operator": "check", "value": "Active", "priority": "Média", "enabled": True
            },
            {
                "id": "00000000-0000-0000-0000-000000000006",
                "name": "Valores Fora do Limite (Range)",
                "message": "Valor numérico fora dos limites min/max definidos",
                "rule_type": "system",
                "field": "range_check", "operator": "check", "value": "Active", "priority": "Alta", "enabled": False
            },
            {
                "id": "00000000-0000-0000-0000-000000000007",
                "name": "Opções Inválidas (Choices)",
                "message": "Valor selecionado não existe na lista de opções",
                "rule_type": "system",
                "field": "choice_check", "operator": "check", "value": "Active", "priority": "Média", "enabled": False
            },
            {
                "id": "00000000-0000-0000-0000-000000000003",
                "name": "Análise Clínica (Consistência)",
                "message": "Inconsistência médica (Ex: Sistólica < Diastólica, IMC, Idade)",
                "rule_type": "system",
                "field": "clinical_check", "operator": "check", "value": "Active", "priority": "Alta", "enabled": False
            },
            {
                "id": "00000000-0000-0000-0000-000000000004",
                "name": "Análise Operacional (Logs)",
                "message": "Padrão suspeito de edição ou performance",
                "rule_type": "system",
                "field": "operational_check", "operator": "check", "value": "Active", "priority": "Baixa", "enabled": False
            }
        ]

        try:
            for rule_def in system_rules_definitions:
                if rule_def['id'] not in existing_ids:
                    print(f"Seeding missing system rule: {rule_def['id']}")
                    self.add_rule(rule_def, user_id, token)
        except Exception as e:
            print(f"Erro ao garantir regras de sistema: {e}")

    def _seed_default_rules(self, user_id, token):
        # Deprecated by _ensure_system_rules
        pass

    def get_system_rules(self) -> list[CustomRule]:
        """
        Retorna regras de sistema. 
        Agora elas são persistidas no DB na criação do usuário, então retorna vazio aqui
        para não duplicar na visualização (já virão pelo load_rules normal).
        """
        return []
    
    def get_enabled_rules(self, user_id=None, token=None) -> list[CustomRule]:
        """Retorna apenas regras habilitadas."""
        if not user_id:
            return []
        return [r for r in self.load_rules(user_id, token) if r.enabled]
    
    def get_rule(self, rule_id: str, user_id=None, token=None) -> Optional[CustomRule]:
        """Obtém uma regra por ID."""
        if not user_id:
            return None
            
        # Inefficient to load all, ideally DBManager has get_rule_by_id
        # But keeping it robust for now
        rules = self.load_rules(user_id, token)
        for rule in rules:
            if rule.id == rule_id:
                return rule
        return None
    
    def add_rule(self, rule_data: dict, user_id=None, token=None) -> Optional[CustomRule]:
        """Adiciona uma nova regra."""
        if not user_id:
            raise ValueError("user_id required for adding rules")
            
        # Generate ID if missing (DB might ignore if it generates one, but good for object state)
        if "id" not in rule_data:
            # Must be a valid UUID for the DB
            rule_data["id"] = str(uuid.uuid4())
            
        saved_data = db.create_custom_rule(user_id, rule_data, token)
        
        if saved_data:
            return CustomRule.from_dict(saved_data)
        return None
    
    def update_rule(self, rule_id: str, rule_data: dict, user_id=None, token=None) -> Optional[CustomRule]:
        """Atualiza uma regra existente."""
        if not user_id:
            return None
            
        updated_data = db.update_custom_rule(rule_id, user_id, rule_data, token)
        
        if updated_data:
            return CustomRule.from_dict(updated_data)
        return None
    
    def delete_rule(self, rule_id: str, user_id=None, token=None) -> bool:
        """Remove uma regra."""
        if not user_id:
            return False
            
        result = db.delete_custom_rule(rule_id, user_id, token)
        return result
    
    def toggle_rule(self, rule_id: str, user_id=None, token=None) -> Optional[CustomRule]:
        """Alterna o estado enabled/disabled de uma regra."""
        rule = self.get_rule(rule_id, user_id, token)
        
        if rule:
            new_state = not rule.enabled
            return self.update_rule(rule_id, {"enabled": new_state}, user_id, token)
        return None


# Instância global para uso na aplicação
rules_manager = RulesManager()

