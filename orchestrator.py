import os
import json
import time
from database.db_manager import DBManager
from clients.gemini_client import GeminiSessionManager
from clients.ollama_client import OllamaFallbackManager
from clients.manus_client import ManusFallbackManager
from clients.fallback_ui import show_model_selector

class AyniOrchestrator:
    def __init__(self, session_id, system_prompt=""):
        self.session_id = session_id
        self.system_prompt = system_prompt
        self.primary_provider = os.environ.get("PRIMARY_PROVIDER", "gemini").lower()
        
        self.db = DBManager()
        if not self.db.Session:
            print("\033[91mNo se pudo conectar a la base de datos. El historial será efímero.\033[0m")
        self.history = self.db.load_history(self.session_id)
        
        self.ollama = OllamaFallbackManager()
        self.manus = ManusFallbackManager()
        self.gemini = None
        
        if self.primary_provider == "gemini":
            try:
                self.gemini = GeminiSessionManager(self.session_id, self.db, self.system_prompt)
            except Exception as e:
                print(f"\033[91m[Error] Falla al inicializar Gemini: {e}\033[0m")
                
    def _sync_history(self, interaction_id, user_msg, model_msg):
        if not self.db.Session: return
        self.db.append_to_history(self.session_id, interaction_id, "user", user_msg)
        self.db.append_to_history(self.session_id, interaction_id, "model", [model_msg])
        self.history = self.db.load_history(self.session_id)
        
    def _trigger_contingency(self, message, attached_files, db_parts, error_msg):
        error_info = {"type": "ManualBypass" if "Bypass" in error_msg else "Exception", "message": error_msg, "fallback": True}
        
        if "Bypass" not in error_msg:
            print(f"\n\033[93m[Alerta] Fallo en motor primario ({error_msg}).\033[0m")
            
        if self.ollama.is_available() or self.manus.is_available():
            print(f"\033[93m[UI] Abriendo Centro de Contingencia Multi-Agente (Pop-up)...\033[0m")
            provider, selected_model = show_model_selector(self.ollama.api_url, self.manus.get_models())
            
            in_tokens = int(len(message.split()) * 1.3)
            if provider == "Ollama":
                resp = self.ollama.generate_response(message, self.system_prompt, self.history, attached_files)
                out_tokens = int(len(resp.split()) * 1.3)
                return resp, selected_model, "Ollama", in_tokens, out_tokens, error_info, db_parts
            elif provider == "Manus":
                resp = self.manus.generate_response(message, self.system_prompt, self.history, selected_model, attached_files)
                out_tokens = int(len(resp.split()) * 1.3)
                return resp, selected_model, "Manus", in_tokens, out_tokens, error_info, db_parts
            else:
                return "Contingencia cancelada por el usuario.", "Ninguno", "UI", 0, 0, error_info, db_parts
        else:
             return f"Error crítico: API falló y no hay respaldo.", "Ninguno", "Error", 0, 0, error_info, db_parts

    def process_request(self, message, attached_files, current_skill):
        start_time = time.time()
        db_parts = [message] + [f"[Archivo Adjunto: {f}]" for f in attached_files]
        
        if self.primary_provider != "gemini" or not self.gemini:
            print(f"\n\033[93m[Ayni] Ejecutando Bypass manual hacia {self.primary_provider}...\033[0m")
            response_text, active_model, provider, in_tokens, out_tokens, error_info, db_parts = self._trigger_contingency(message, attached_files, db_parts, f"Bypass hacia {self.primary_provider}")
        else:
            try:
                response_text, active_model, provider, in_tokens, out_tokens, error_info, db_parts = self.gemini.send_message_sync(message, attached_files)
            except Exception as e:
                response_text, active_model, provider, in_tokens, out_tokens, error_info, db_parts = self._trigger_contingency(message, attached_files, db_parts, str(e))
                
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
            skill_used=current_skill,
            error_data=error_info
        )
        
        if interaction_id:
            self._sync_history(interaction_id, db_parts, response_text)
            
        return response_text, active_model, provider, in_tokens, out_tokens, elapsed_ms
