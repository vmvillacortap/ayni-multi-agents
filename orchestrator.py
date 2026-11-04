import os
import json
import time
import importlib.util
from database.db_manager import DBManager
from clients.gemini_client import GeminiSessionManager
from clients.ollama_client import OllamaFallbackManager
from clients.manus_client import ManusFallbackManager
from clients.fallback_ui import show_model_selector

class AyniOrchestrator:
    def __init__(self, session_id, default_system_prompt=""):
        self.session_id = session_id
        self.default_system_prompt = default_system_prompt
        self.primary_provider = os.environ.get("PRIMARY_PROVIDER", "gemini").lower()
        
        self.db = DBManager()
        if not self.db.Session:
            print("\033[91mNo se pudo conectar a la base de datos. El historial será efímero.\033[0m")
        self.history = self.db.load_history(self.session_id)
        
        self.ollama = OllamaFallbackManager()
        self.manus = ManusFallbackManager()
        self.gemini = None
        
        # --- CARGA DINÁMICA DE AGENTES ---
        self.agents_registry = self._discover_agents("agents")
        
        if self.primary_provider == "gemini":
            try:
                self.gemini = GeminiSessionManager(self.session_id, self.db, self.default_system_prompt)
            except Exception as e:
                print(f"\033[91m[Error] Falla al inicializar Gemini: {e}\033[0m")
                
    def _discover_agents(self, agents_dir):
        """Escanea el directorio de agentes y carga su metadata y herramientas."""
        registry = {}
        if not os.path.exists(agents_dir):
            return registry
            
        for agent_name in os.listdir(agents_dir):
            agent_path = os.path.join(agents_dir, agent_name)
            if os.path.isdir(agent_path) and not agent_name.startswith('__'):
                schema_path = os.path.join(agent_path, "schema.json")
                instructions_path = os.path.join(agent_path, "instructions.md")
                tools_path = os.path.join(agent_path, "tools.py")
                
                if os.path.exists(schema_path) and os.path.exists(instructions_path):
                    try:
                        with open(schema_path, 'r', encoding='utf-8') as f:
                            schema = json.load(f)
                        with open(instructions_path, 'r', encoding='utf-8') as f:
                            instructions = f.read()
                            
                        tools_module = None
                        tools_list = []
                        if os.path.exists(tools_path):
                            spec = importlib.util.spec_from_file_location(f"agent_tools_{agent_name}", tools_path)
                            tools_module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(tools_module)
                            # Extraemos solo las funciones públicas del script de herramientas
                            tools_list = [getattr(tools_module, func) for func in dir(tools_module) if callable(getattr(tools_module, func)) and not func.startswith("__")]
                            
                        registry[agent_name] = {
                            "schema": schema,
                            "instructions": instructions,
                            "tools": tools_list
                        }
                    except Exception as e:
                        print(f"\033[91m[Error] No se pudo cargar el agente '{agent_name}': {e}\033[0m")
        
        if registry:
            print(f"\033[92m[Ayni] {len(registry)} agentes autónomos cargados exitosamente.\033[0m")
        return registry

    def _sync_history(self, interaction_id, user_msg, model_msg):
        if not self.db.Session: return
        self.db.append_to_history(self.session_id, interaction_id, "user", user_msg)
        self.db.append_to_history(self.session_id, interaction_id, "model", [model_msg])
        self.history = self.db.load_history(self.session_id)
        
    def _trigger_contingency(self, message, attached_files, db_parts, error_msg, current_prompt):
        error_info = {"type": "ManualBypass" if "Bypass" in error_msg else "Exception", "message": error_msg, "fallback": True}
        
        if "Bypass" not in error_msg:
            print(f"\n\033[93m[Alerta] Fallo en motor primario ({error_msg}).\033[0m")
            
        if self.ollama.is_available() or self.manus.is_available():
            print(f"\033[93m[UI] Abriendo Centro de Contingencia Multi-Agente (Pop-up)...\033[0m")
            provider, selected_model = show_model_selector(self.ollama.api_url, self.manus.get_models())
            
            in_tokens = int(len(message.split()) * 1.3)
            if provider == "Ollama":
                resp = self.ollama.generate_response(message, current_prompt, self.history, attached_files)
                out_tokens = int(len(resp.split()) * 1.3)
                return resp, selected_model, "Ollama", in_tokens, out_tokens, error_info, db_parts
            elif provider == "Manus":
                resp = self.manus.generate_response(message, current_prompt, self.history, selected_model, attached_files)
                out_tokens = int(len(resp.split()) * 1.3)
                return resp, selected_model, "Manus", in_tokens, out_tokens, error_info, db_parts
            else:
                return "Contingencia cancelada por el usuario.", "Ninguno", "UI", 0, 0, error_info, db_parts
        else:
             return f"Error crítico: API falló y no hay respaldo.", "Ninguno", "Error", 0, 0, error_info, db_parts

    def _route_to_agent(self, user_input):
        """Supervisor: Decide si la petición la atiende el sistema general o un agente específico."""
        if not self.agents_registry or not self.gemini:
            return None, self.default_system_prompt, []
            
        # 1. Armar el catálogo de agentes para que el Supervisor elija
        catalog = "\n".join([f"- '{name}': {data['schema'].get('description', '')}" for name, data in self.agents_registry.items()])
        prompt_supervisor = f"""Eres el Supervisor de Ayni. Tu tarea es enrutar la petición del usuario al agente correcto, o manejarla tú mismo si es general.
        Catálogo de Agentes Disponibles:
        {catalog}
        
        Responde ÚNICAMENTE con el nombre exacto del agente (ej. 'investigador_pdf'). Si la petición es general o no requiere un agente especializado, responde 'general'."""
        
        try:
            target_agent = self.gemini._generate_quick_classification(prompt_supervisor, user_input)
            target_agent = target_agent.strip().lower()
            
            if target_agent in self.agents_registry:
                print(f"\033[96m[Supervisor] Derivando tarea al agente: {target_agent}\033[0m")
                agent_data = self.agents_registry[target_agent]
                combined_prompt = f"{self.default_system_prompt}\n\n--- INSTRUCCIONES ESPECÍFICAS DEL AGENTE ({target_agent}) ---\n{agent_data['instructions']}"
                return target_agent, combined_prompt, agent_data['tools']
                
            return None, self.default_system_prompt, []
        except Exception:
            return None, self.default_system_prompt, []

    def process_request(self, message, attached_files, default_skill):
        start_time = time.time()
        db_parts = [message] + [f"[Archivo Adjunto: {f}]" for f in attached_files]
        
        # EL SUPERVISOR DECIDE EL ENRUTAMIENTO Y LAS HERRAMIENTAS A USAR
        agent_name, current_prompt, agent_tools = self._route_to_agent(message)
        skill_used = agent_name if agent_name else default_skill
        
        if self.primary_provider != "gemini" or not self.gemini:
            print(f"\n\033[93m[Ayni] Ejecutando Bypass manual hacia {self.primary_provider}...\033[0m")
            response_text, active_model, provider, in_tokens, out_tokens, error_info, db_parts = self._trigger_contingency(message, attached_files, db_parts, f"Bypass hacia {self.primary_provider}", current_prompt)
        else:
            try:
                # Inyectar dinámicamente las herramientas del agente seleccionado antes de enviar la petición
                response_text, active_model, provider, in_tokens, out_tokens, error_info, db_parts = self.gemini.send_message_sync(message, attached_files, dynamic_prompt=current_prompt, dynamic_tools=agent_tools)
            except Exception as e:
                response_text, active_model, provider, in_tokens, out_tokens, error_info, db_parts = self._trigger_contingency(message, attached_files, db_parts, str(e), current_prompt)
                
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        
        interaction_id = self.db.log_interaction(
            session_id=self.session_id,
            user_input=message,
            response_text=response_text,
            provider=provider,
            model_used=active_model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            response_time_ms=elapsed_ms,
            skill_used=skill_used,
            error_data=error_info
        )
        
        if interaction_id:
            self._sync_history(interaction_id, db_parts, response_text)
            
        # MODIFICACIÓN: Ahora devolvemos explícitamente skill_used para mostrarlo en main.py
        return response_text, active_model, provider, in_tokens, out_tokens, elapsed_ms, skill_used
