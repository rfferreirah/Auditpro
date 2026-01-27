import os
from datetime import datetime
from supabase import create_client, Client

class DBManager:
    def __init__(self):
        self.url: str = os.getenv("SUPABASE_URL")
        self.key: str = os.getenv("SUPABASE_KEY")
        self.client: Client = None
        
        if self.url and self.key:
            try:
                self.client = create_client(self.url, self.key)
            except Exception as e:
                print(f"Error initializing Supabase client in DBManager: {e}")

    def get_client(self, token=None):
        """
        Returns a supabase client.
        If token is provided, returns a client authenticated with that token (for RLS).
        Otherwise returns the default (service/anon) client.
        """
        if token:
            # Create a localized client for this request to respect RLS
            # Using headers to pass the JWT
            from supabase.lib.client_options import ClientOptions
            return create_client(
                self.url, 
                self.key, 
                options=ClientOptions(headers={"Authorization": f"Bearer {token}"})
            )
        return self.client

    def save_project(self, user_id, project_title, api_url, redcap_project_id=None, is_longitudinal=False, token=None):
        """
        Saves or updates a project for the user.
        Checks if a project with the same API URL already exists for this user.
        """
        client = self.get_client(token)
        if not client:
            return None

        try:
            # Check if exists
            response = client.table('projects').select('id').eq('user_id', user_id).eq('api_url', api_url).execute()
            
            data = {
                'user_id': user_id,
                'project_title': project_title,
                'api_url': api_url,
                'redcap_project_id': redcap_project_id,
                'is_longitudinal': is_longitudinal,
                'updated_at': datetime.now().isoformat()
            }

            if response.data:
                # Update
                project_id = response.data[0]['id']
                client.table('projects').update(data).eq('id', project_id).execute()
                return project_id
            else:
                # Insert
                response = client.table('projects').insert(data).execute()
                if response.data:
                    return response.data[0]['id']
            return None
        except Exception as e:
            print(f"Error saving project: {e}")
            return None

    def save_analysis(self, user_id, project_id, report, ai_analysis_used=False, duration_ms=None, token=None, project_title=None):
        """
        Saves analysis history.
        """
        client = self.get_client(token)
        if not client:
            return None

        try:
            # Count priorities
            high = 0
            medium = 0
            low = 0
            
            # Assuming report object structure or dict
            # If report is QualityReport object
            total_records = 0
            total_queries = 0
            
            # Handle if report is dict or object
            if isinstance(report, dict):
                # If it's a dict (from to_dict())
                summary = report.get('project_summary', {})
                total_records = summary.get('total_records', 0)
                total_queries = summary.get('total_queries_generated', 0)
            else:
                # Object
                total_records = report.project_summary.total_records
                total_queries = report.project_summary.total_queries_generated
            
            # Insert analysis record
            data = {
                'project_id': project_id,
                'user_id': user_id,
                'project_title': project_title, # Added field
                'total_records': total_records,
                'total_queries': total_queries,
                # 'high_priority_count': high, # We need these passed in ideally
                # 'medium_priority_count': medium,
                # 'low_priority_count': low,
                'analysis_duration_ms': duration_ms,
                'ai_analysis_used': ai_analysis_used,
                'created_at': datetime.now().isoformat()
            }
            
            response = client.table('analysis_history').insert(data).execute()
            return response.data[0]['id'] if response.data else None
            
        except Exception as e:
            print(f"Error saving analysis: {e}")
            return None

    def update_analysis_counts(self, analysis_id, high, medium, low, token=None):
        """Updates priority counts for an analysis"""
        client = self.get_client(token)
        if not client or not analysis_id:
            return
            
        try:
            client.table('analysis_history').update({
                'high_priority_count': high,
                'medium_priority_count': medium,
                'low_priority_count': low
            }).eq('id', analysis_id).execute()
        except Exception as e:
            print(f"Error updating analysis counts: {e}")

    # ==================== SAVED QUERIES ====================

    def save_query_issue(self, user_id, project_id, query_data):
        """Saves a query issue/bookmark"""
        if not self.client:
            return None
            
        try:
            # Ensure required fields
            data = {
                'user_id': user_id,
                'project_id': project_id,
                'record_id': str(query_data.get('record_id', '')),
                'field_name': query_data.get('field', ''),
                'field_label': query_data.get('field_label', ''),
                'current_value': str(query_data.get('value', ''))[:255], # Truncate if too long
                'priority': query_data.get('priority', 'Média'),
                'issue_type': query_data.get('issue_type', ''),
                'description': query_data.get('explanation', ''),
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            }
            
            response = self.client.table('saved_queries').insert(data).execute()
            return response.data[0]['id'] if response.data else None
            
        except Exception as e:
            print(f"Error saving query: {e}")
            return None

    def save_query_issues_bulk(self, user_id, project_id, queries_list, field_labels=None):
        """Saves multiple queries at once"""
        if not self.client or not queries_list:
            return None
            
        if field_labels is None:
            field_labels = {}
            
        try:
            bulk_data = []
            now_iso = datetime.now().isoformat()
            
            for q in queries_list:
                # Handle if q is dict or object
                if isinstance(q, dict):
                     # Already dict (maybe from frontend)
                     rec_id = str(q.get('record_id', ''))
                     field = q.get('field', '')
                     val = str(q.get('value', ''))
                     prio = q.get('priority', 'Média')
                     issue = q.get('issue_type', '')
                     desc = q.get('explanation', '')
                else:
                    # Object from QueryGenerator
                     rec_id = str(q.record_id)
                     field = q.field
                     val = str(q.value_found)
                     prio = q.priority
                     issue = q.issue_type
                     desc = q.explanation
                
                label = field_labels.get(field, '')
                
                bulk_data.append({
                    'user_id': user_id,
                    'project_id': project_id,
                    'record_id': rec_id,
                    'field_name': field,
                    'field_label': label,
                    'current_value': val[:255], 
                    'priority': prio,
                    'issue_type': issue,
                    'description': desc,
                    'status': 'pending',
                    'created_at': now_iso
                })
            
            # Chunking prevents request size limits
            chunk_size = 100
            for i in range(0, len(bulk_data), chunk_size):
                chunk = bulk_data[i:i + chunk_size]
                self.client.table('saved_queries').insert(chunk).execute()
                
            return True
            
        except Exception as e:
            print(f"Error bulk saving queries: {e}")
            return False

    def get_saved_queries(self, user_id, project_id=None):
        """Get saved queries for a user/project"""
        if not self.client:
            return []
            
        try:
            query = self.client.table('saved_queries').select('*').eq('user_id', user_id)
            
            if project_id:
                query = query.eq('project_id', project_id)
                
            response = query.order('created_at', desc=True).execute()
            return response.data
        except Exception as e:
            print(f"Error getting saved queries: {e}")
            return []

    # ==================== CUSTOM RULES ====================

    def create_custom_rule(self, user_id, rule_data, token=None):
        """Create a custom rule in Supabase"""
        client = self.get_client(token)
        if not client:
            return None
            
        try:
            # Validate rule_type against schema constraints
            rt = rule_data.get('rule_type', 'custom')
            valid_types = ['required_if', 'range_check', 'date_comparison', 'cross_field', 'regex', 'custom', 'system', 'uniqueness', 'condition', 'comparison']
            if rt not in valid_types:
                # Map common invalid types or default to custom
                if rt == 'comparison':
                     rt = 'custom' 
                else:
                     rt = 'custom'
            
            # Default operator for uniqueness if not provided
            op = rule_data.get('operator')
            if rt == 'uniqueness' and not op:
                op = 'unique'
            
            # Map valid internal types to DB allowed types (to avoid constraint violations)
            db_allowed_types = ['required_if', 'range_check', 'date_comparison', 'cross_field', 'regex', 'custom']
            db_rt = rt if rt in db_allowed_types else 'custom'
            
            # Map operator to safe value if needed
            db_op = op or rule_data.get('operator')
            if db_op == 'unique':
                db_op = '='
            
            # Prepare data mapping from internal object to DB schema
            db_data = {
                'user_id': user_id,
                'name': rule_data.get('name'),
                'description': rule_data.get('message', ''), 
                'rule_type': db_rt,
                'field': rule_data.get('field'),
                'operator': db_op,
                'value': str(rule_data.get('value', '')),
                'rule_config': rule_data, 
                'priority': rule_data.get('priority', 'Média'),
                'is_active': rule_data.get('enabled', True),
                'is_global': False,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # If explicit ID provided (e.g. system rules), use it
            if rule_data.get('id'):
                db_data['id'] = rule_data.get('id')
            
            response = client.table('custom_rules').insert(db_data).execute()
            if response.data:
                # Return the ID and add it to the rule data
                rule_data['id'] = response.data[0]['id']
                return rule_data
            else:
                print(f"Warning: Supabase insert passed but returned no data. Response: {response}")
                return None
            
        except Exception as e:
            print(f"Error creating custom rule: {str(e)}")
            raise e

    def get_custom_rules(self, user_id, token=None):
        """Get all custom rules for user (and global/public ones if implemented)"""
        client = self.get_client(token)
        if not client:
            return []
            
        try:
            # Select own rules OR global rules (RLS handles this usually via policies, 
            # but explicit OR helps if policy allows viewing others' global rules)
            response = client.table('custom_rules').select('*').is_('deleted_at', 'null').execute()
            
            rules = []
            for row in response.data:
                # Reconstruct rule object from DB row + JSONB config
                # We prioritize the rule_config as it holds the complete original data
                # But ensure we respect DB columns if they were updated independently
                rule_config = row.get('rule_config') or {}
                
                # Merge DB columns back into config to ensure consistency
                rule_config['id'] = row['id']
                rule_config['name'] = row['name']
                rule_config['message'] = row.get('description')
                rule_config['priority'] = row.get('priority')
                rule_config['enabled'] = row['is_active']
                
                # Only sync field from DB if not in config (preserve JSON config values)
                if row.get('field') and not rule_config.get('field'):
                    rule_config['field'] = row['field']
                # DO NOT overwrite operator, value, rule_type from DB columns
                # They are mapped to safe values for DB constraints but JSON has the true values
                
                rule_config['created_at'] = row['created_at']
                rule_config['updated_at'] = row['updated_at']
                
                rules.append(rule_config)
                
            return rules
        except Exception as e:
            print(f"Error getting custom rules: {e}")
            return []

    def update_custom_rule(self, rule_id, user_id, rule_data, token=None):
        """Update part of a custom rule"""
        client = self.get_client(token)
        if not client:
            return None
            
        try:
            # Map fields safely
            # Map fields safely
            update_data = {}
            
            # Map valid internal types to DB allowed types
            rt = rule_data.get('rule_type')
            if rt:
                db_allowed_types = ['required_if', 'range_check', 'date_comparison', 'cross_field', 'regex', 'custom']
                db_rt = rt if rt in db_allowed_types else 'custom'
                update_data['rule_type'] = db_rt
                
            # Map operator
            op = rule_data.get('operator')
            if op:
                if op == 'unique':
                    update_data['operator'] = '='
                else:
                    update_data['operator'] = op
            
            if 'name' in rule_data: update_data['name'] = rule_data['name']
            if 'message' in rule_data: update_data['description'] = rule_data['message']
            if 'enabled' in rule_data: update_data['is_active'] = rule_data['enabled']
            if 'field' in rule_data: update_data['field'] = rule_data['field']
            if 'value' in rule_data: update_data['value'] = str(rule_data['value'])
            if 'priority' in rule_data: update_data['priority'] = rule_data.get('priority')
            
            # Update the JSON config as well to keep everything in sync
            # First, we need to merge with existing config if not provided fully
            # But usually rule_data here is the full object from frontend
            update_data['rule_config'] = rule_data
            
            # Helper: Get current config to merge or just overwrite partially
            # Ideally we might want to fetch current, update config dict, and save back
            # But specific columns are easier if schema supports them
            
            update_data['updated_at'] = datetime.now().isoformat()
            
            response = client.table('custom_rules').update(update_data).eq('id', rule_id).eq('user_id', user_id).execute()
            if response.data:
                # Need to convert back to internal format to return full object?
                # For responsiveness we might just return the merged dict or the db row
                return self._map_db_rule_to_internal(response.data[0])
            return None
        except Exception as e:
            print(f"Error updating rule: {e}")
            return None

    def delete_custom_rule(self, rule_id, user_id, token=None):
        """Soft delete custom rule"""
        client = self.get_client(token)
        if not client:
            return False
            
        try:
            # Soft delete instead of hard delete
            cleaned_at = datetime.now().isoformat()
            client.table('custom_rules').update({'deleted_at': cleaned_at}).eq('id', rule_id).eq('user_id', user_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting custom rule: {e}")
            return False

    # ==================== AUDIT LOG ====================

    def log_audit_event(self, user_id, action, entity_type, entity_id=None, details=None):
        """Log user action asynchronously"""
        if not self.client or not user_id:
            return
            
        try:
            data = {
                'user_id': user_id,
                'action': action,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'new_values': details or {}, # mapping details to jsonb
                'created_at': datetime.now().isoformat()
            }
            # Fire and forget using background thread
            import threading
            thread = threading.Thread(target=self._log_audit_worker, args=(data,))
            thread.daemon = True
            thread.start()
        except Exception as e:
            print(f"Error initiating audit log: {e}")

    def _log_audit_worker(self, data):
        """Worker thread for audit logging"""
        try:
            self.client.table('audit_log').insert(data).execute()
        except Exception as e:
            print(f"Error processing audit log (async): {e}")

    def _map_db_rule_to_internal(self, row):
        """Maps DB row to internal rule dictionary"""
        rule_config = row.get('rule_config') or {}
        
        # Merge DB columns back into config
        rule_config['id'] = row['id']
        rule_config['name'] = row['name']
        rule_config['message'] = row.get('description')
        rule_config['priority'] = row.get('priority')
        rule_config['enabled'] = row.get('is_active')
        
        # Sync field from DB column if not in config
        if row.get('field') and not rule_config.get('field'):
            rule_config['field'] = row.get('field')
        
        # DO NOT overwrite operator and rule_type from DB columns!
        # The rule_config JSON preserves the original values (e.g., 'unique', 'uniqueness')
        # while DB columns may have mapped values (e.g., '=', 'custom') for constraint compliance.
        
        rule_config['created_at'] = row.get('created_at')
        rule_config['updated_at'] = row.get('updated_at')
        
        return rule_config

# Singleton
db = DBManager()
