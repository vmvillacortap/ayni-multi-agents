import os
import json
import time
from google import genai
from google.genai import types
from network.ayni_search import AyniSearchEcosystem
from clients.file_manager import guardar_documento, extract_text_from_doc

def obtener_hora_local():
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def buscar_en_internet(consulta: str) -> str:
    """Busca información en internet utilizando el ecosistema Ayni (múltiples proveedores priorizados)."""
    try:
        # Se asume que db_manager es None aquí porque la herramienta base es estática.
        # En una arquitectura real, se inyectaría la DB para aprovechar el caché.
        search_engine = AyniSearchEcosystem(db_manager=None)
        return search_engine.execute_search(consulta)
    except Exception as e:
        return f"Error crítico en Ayni Search: {str(e)}"

class GeminiSessionManager:
    def __init__(self, session_id, db_manager, system_prompt="Eres un asistente experto."):
        self.session_id = session_id
        self.db = db_manager
        self.system_prompt = system_prompt
        self.base_tools = [obtener_hora_local, buscar_en_internet, guardar_documento]
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Falta GEMINI_API_KEY en el archivo .env")
            
        self.client = genai.Client(api_key=api_key)
        
        self.pools = self._build_dynamic_pools()
        self.history = self.db.load_history(self.session_id)
        
        valid_fast_models = [m for m in self.pools['fast'] if 'tts' not in m]
        self.current_model_name = valid_fast_models[0] if valid_fast_models else 'gemini-1.5-flash'
        
        self.chat_session = None
        self.current_tools = self.base_tools
        self._switch_active_model(self.current_model_name, self.system_prompt, self.current_tools)

    def _build_dynamic_pools(self):
        pools = {'router': [], 'fast': [], 'pro': []}
        try:
            raw_models = [m.name for m in self.client.models.list()]
            chat_models = [m for m in raw_models if 'tts' not in m]
            multimodal_models = [m for m in chat_models if 'embedding' not in m and 'aqa' not in m]
            
            pools['router'] = sorted([m for m in multimodal_models if '8b' in m or 'flash' in m], reverse=True)
            pools['pro'] = sorted([m for m in multimodal_models if 'pro' in m], reverse=True)
            pools['fast'] = sorted([m for m in multimodal_models if 'flash' in m and '8b' not in m], reverse=True)
            
            if not pools['pro']: pools['pro'] = multimodal_models[:1]
            if not pools['fast']: pools['fast'] = multimodal_models[:1]
            if not pools['router']: pools['router'] = pools['fast']
            return pools
        except Exception:
            return {'router': ['gemini-1.5-flash'], 'fast': ['gemini-1.5-flash'], 'pro': ['gemini-1.5-pro']}

    def _switch_active_model(self, model_name, active_prompt, active_tools):
        self.current_model_name = model_name
        self.current_tools = active_tools
        
        formatted_history = []
        for msg in self.history:
            parts = [{"text": str(p)} for p in msg["parts"]]
            role_mapped = "model" if msg["role"] == "model" else "user"
            formatted_history.append(types.Content(role=role_mapped, parts=parts))
        
        self.chat_session = self.client.chats.create(
            model=self.current_model_name,
            config=types.GenerateContentConfig(
                system_instruction=active_prompt,
                tools=self.current_tools
            ),
            history=formatted_history
        )
        
    def _generate_quick_classification(self, prompt, user_input):
        router_model = self.pools['router'][0]
        res = self.client.models.generate_content(
            model=router_model,
            contents=f"{prompt}\n\nPetición Usuario: {user_input}",
            config=types.GenerateContentConfig(temperature=0.0)
        )
        return res.text

    def _analyze_intent(self, prompt, attached_files):
        if attached_files:
            return {"complexity": "high", "is_complaint": False}
            
        sys_prompt = """Clasifica la petición. Responde ÚNICAMENTE con un JSON: {"complexity": "low" | "high", "is_complaint": true | false}"""
        try:
            res_text = self._generate_quick_classification(sys_prompt, prompt)
            return json.loads(res_text)
        except Exception:
            return {"complexity": "low", "is_complaint": False}

    def send_message_sync(self, message, attached_files=None, dynamic_prompt=None, dynamic_tools=None):
        error_info = None
        attached_files = attached_files or []
        db_parts = [message] + [f"[Archivo Adjunto: {f}]" for f in attached_files]
        
        combined_tools = self.base_tools.copy()
        if dynamic_tools:
            combined_tools.extend(dynamic_tools)
            
        active_prompt = dynamic_prompt if dynamic_prompt else self.system_prompt
            
        print("\033[93m[🧠 Enrutador Analizando Complejidad e Intención...]\033[0m", end="\r", flush=True)
        intent = self._analyze_intent(message, attached_files)
        
        target_pool = 'pro' if (intent.get('is_complaint', False) or intent.get('complexity', 'low') == 'high' or attached_files) else 'fast'
        
        if target_pool == 'pro' and not self.pools['pro']:
            print("\n\033[93m[Ayni] Pool PRO agotado. Redirigiendo petición compleja al Pool FAST (Flash)...\033[0m")
            target_pool = 'fast'
            
        if not self.pools[target_pool]:
            raise Exception("Todos los modelos de Gemini aplicables están agotados o deprecados.")
            
        self._switch_active_model(self.pools[target_pool][0], active_prompt, combined_tools)
        
        print(f"\033[93m[⚙️ Ejecutando en pool {target_pool.upper()}: {self.current_model_name}...]     \033[0m", end="\r", flush=True)
        
        try:
            gemini_parts = [message]
            
            if attached_files:
                print("\n\033[90m[Gemini] Procesando archivos adjuntos...\033[0m")
                for file_path in attached_files:
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in ['.txt', '.md', '.csv', '.json', '.py']:
                        file_content = extract_text_from_doc(file_path)
                        gemini_parts.append(f"\n--- Contenido de {os.path.basename(file_path)} ---\n{file_content}\n")
                    else:
                        print(f"\033[90mSubiendo {os.path.basename(file_path)} a la API de Gemini...\033[0m", end="\r")
                        uploaded = self.client.files.upload(file=file_path)
                        gemini_parts.append(uploaded)
                        
                        while uploaded.state.name == "PROCESSING":
                            print("\033[90mProcesando archivo en la nube...\033[0m", end="\r")
                            time.sleep(2)
                            uploaded = self.client.files.get(name=uploaded.name)
                        print(f"\033[90mSubido y procesado: {os.path.basename(file_path)}          \033[0m")
            
            final_content = gemini_parts if len(gemini_parts) > 1 else message
            response = self.chat_session.send_message(final_content)
            
            in_tokens, out_tokens = 0, 0
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                in_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
                out_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)
                
            return response.text, self.current_model_name, "Gemini", in_tokens, out_tokens, error_info, db_parts
            
        except Exception as e:
            error_msg = str(e)
            
            is_quota_or_deprecated = any(err in error_msg.lower() for err in ["429", "quota", "404", "not found", "403"])
            
            if is_quota_or_deprecated:
                print(f"\n\033[93m[Rotación Activada] El modelo {self.current_model_name} falló (Cuota/Deprecado).\033[0m")
                if self.current_model_name in self.pools[target_pool]:
                    self.pools[target_pool].remove(self.current_model_name)
                
                try:
                    return self.send_message_sync(message, attached_files, dynamic_prompt, dynamic_tools)
                except Exception as retry_e:
                    raise Exception(f"Fallo tras rotación: {str(retry_e)}")
            
            raise Exception(error_msg)
