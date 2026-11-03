import os
import json
import datetime
import time
import google.generativeai as genai
from dotenv import load_dotenv
from tavily import TavilyClient

from clients.ollama_client import OllamaFallbackManager
from clients.manus_client import ManusFallbackManager
from clients.fallback_ui import show_model_selector
from database.db_manager import DBManager
from clients.file_manager import guardar_documento, extract_text_from_doc

def obtener_hora_local():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def buscar_en_internet(consulta: str):
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        return "Error interno: Falta configurar TAVILY_API_KEY en el entorno."
    try:
        client = TavilyClient(api_key=tavily_key)
        respuesta = client.search(consulta, search_depth="basic", max_results=3)
        resultados = [f"- {res['title']}: {res['content']}" for res in respuesta.get('results', [])]
        return "\n".join(resultados) if resultados else "No se encontraron resultados relevantes."
    except Exception as e:
        return f"Error en la búsqueda web: {str(e)}"

class GeminiSessionManager:
    def __init__(self, session_id, db_manager, system_prompt="Eres un asistente experto."):
        load_dotenv(override=True)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No se encontró GEMINI_API_KEY en el archivo .env")
            
        os.environ["GOOGLE_API_KEY"] = api_key
        genai.configure(api_key=api_key)
        
        self.session_id = session_id
        self.db = db_manager
        self.system_prompt = system_prompt
        self.tools = [obtener_hora_local, buscar_en_internet, guardar_documento]
        
        self.ollama_fallback = OllamaFallbackManager() 
        self.manus_fallback = ManusFallbackManager()
        
        self.pools = self._build_dynamic_pools()
        self.history = self.db.load_history(self.session_id)
        
        valid_fast_models = [m for m in self.pools['fast'] if 'tts' not in m]
        self.current_model_name = valid_fast_models[0] if valid_fast_models else 'models/gemini-1.5-flash-latest'
        
        self.model = None
        self.chat_session = None
        self._switch_active_model(self.current_model_name)

    def _build_dynamic_pools(self):
        pools = {'router': [], 'fast': [], 'pro': []}
        try:
            raw_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            chat_models = [m for m in raw_models if 'tts' not in m]
            multimodal_models = [m for m in chat_models if ('1.5' in m or '2.' in m or '3.' in m or 'vision' in m) and 'embedding' not in m and 'aqa' not in m]
            
            pools['router'] = sorted([m for m in multimodal_models if '8b' in m or 'flash' in m], reverse=True)
            pools['pro'] = sorted([m for m in multimodal_models if 'pro' in m], reverse=True)
            pools['fast'] = sorted([m for m in multimodal_models if 'flash' in m and '8b' not in m], reverse=True)
            
            if not pools['pro']: pools['pro'] = multimodal_models[:1]
            if not pools['fast']: pools['fast'] = multimodal_models[:1]
            if not pools['router']: pools['router'] = pools['fast']
            return pools
        except Exception as e:
            return {'router': ['models/gemini-1.5-flash-latest'], 'fast': ['models/gemini-1.5-flash-latest'], 'pro': ['models/gemini-1.5-pro-latest']}

    def _switch_active_model(self, model_name):
        if self.current_model_name != model_name or self.chat_session is None:
            self.current_model_name = model_name
            self.model = genai.GenerativeModel(
                model_name=self.current_model_name, 
                system_instruction=self.system_prompt,
                tools=self.tools
            )
            self.chat_session = self.model.start_chat(
                history=self.history,
                enable_automatic_function_calling=True
            )

    def _analyze_intent(self, prompt, attached_files):
        if attached_files:
            return {"complexity": "high", "is_complaint": False}
            
        router_model = self.pools['router'][0]
        analyzer = genai.GenerativeModel(model_name=router_model)
        
        sys_prompt = """Clasifica la petición. Responde ÚNICAMENTE con un JSON: {"complexity": "low" | "high", "is_complaint": true | false}"""
        try:
            res = analyzer.generate_content(
                f"{sys_prompt}\n\nPetición: {prompt}",
                generation_config=genai.types.GenerationConfig(response_mime_type="application/json", temperature=0.0)
            )
            return json.loads(res.text)
        except Exception:
            return {"complexity": "low", "is_complaint": False}

    def _sync_history_to_db(self, interaction_id, new_user_msg, new_model_msg):
        if not self.db: return
        self.db.append_to_history(self.session_id, interaction_id, "user", new_user_msg)
        self.db.append_to_history(self.session_id, interaction_id, "model", [new_model_msg])
        self.history = self.db.load_history(self.session_id)

    def send_message_sync(self, message, attached_files=None):
        error_info = None
        attached_files = attached_files or []
        
        print("\033[93m[🧠 Enrutador Analizando Complejidad e Intención...]\033[0m", end="\r", flush=True)
        intent = self._analyze_intent(message, attached_files)
        
        target_pool = 'pro' if (intent.get('is_complaint', False) or intent.get('complexity', 'low') == 'high' or attached_files) else 'fast'
        
        # --- MEJORA: ESCALADO INVERSO ---
        # Si el enrutador elige PRO, pero la familia PRO está agotada (ej. modelos deprecados o sin cuota), 
        # delegamos el trabajo a la familia FAST antes de rendirnos y saltar a Ollama/Manus.
        if target_pool == 'pro' and not self.pools['pro']:
            print("\n\033[93m[Ayni] Pool PRO agotado. Redirigiendo petición compleja al Pool FAST (Flash)...\033[0m")
            target_pool = 'fast'
            
        # Si definitivamente no quedan modelos en el pool objetivo, forzamos la contingencia manual.
        if not self.pools[target_pool]:
            raise Exception("Todos los modelos de Gemini aplicables están agotados o deprecados.")
            
        self._switch_active_model(self.pools[target_pool][0])
        
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
                        uploaded = genai.upload_file(file_path)
                        gemini_parts.append(uploaded)
                        
                        while uploaded.state.name == "PROCESSING":
                            print("\033[90mProcesando archivo en la nube...\033[0m", end="\r")
                            time.sleep(2)
                            uploaded = genai.get_file(uploaded.name)
                        print(f"\033[90mSubido y procesado: {os.path.basename(file_path)}          \033[0m")
            
            response = self.chat_session.send_message(gemini_parts, request_options={"timeout": 60})
            
            in_tokens, out_tokens = 0, 0
            if hasattr(response, 'usage_metadata'):
                in_tokens = response.usage_metadata.prompt_token_count
                out_tokens = response.usage_metadata.candidates_token_count
            
            db_parts = [message] + [f"[Archivo Adjunto: {f}]" for f in attached_files]
                
            return response.text, self.current_model_name, "Gemini", in_tokens, out_tokens, error_info, db_parts
            
        except Exception as e:
            error_msg = str(e)
            
            # Comprobación de errores tratables (Cuota o Deprecados)
            is_quota_or_deprecated = any(err in error_msg.lower() for err in ["429", "quota", "404", "not found", "403"])
            
            if is_quota_or_deprecated:
                print(f"\n\033[93m[Rotación Activada] El modelo {self.current_model_name} falló (Cuota/Deprecado).\033[0m")
                if self.current_model_name in self.pools[target_pool]:
                    self.pools[target_pool].remove(self.current_model_name)
                
                # REINTENTO RECURSIVO: Si el pool PRO se vació en la línea anterior, 
                # la nueva llamada activará el "Escalado Inverso" y pasará al pool FAST.
                try:
                    return self.send_message_sync(message, attached_files)
                except Exception as retry_e:
                    error_msg = str(retry_e)
            
            error_info = {"type": type(e).__name__, "message": error_msg, "fallback": True}
            print(f"\n\033[93m[Alerta] Falla en la cascada de Gemini ({error_msg}).\033[0m")
            
            if self.ollama_fallback.is_available() or self.manus_fallback.is_available():
                print(f"\033[93m[UI] Abriendo Centro de Contingencia Multi-Agente (Pop-up)...\033[0m")
                provider, selected_model = show_model_selector(self.ollama_fallback.api_url, self.manus_fallback.get_models())
                
                in_tokens = int(len(message.split()) * 1.3)
                db_parts = [message] + [f"[Archivo Adjunto: {f}]" for f in attached_files]
                
                if provider == "Ollama":
                    resp = self.ollama_fallback.generate_response(message, self.system_prompt, self.history, attached_files)
                    out_tokens = int(len(resp.split()) * 1.3)
                    return resp, selected_model, "Ollama", in_tokens, out_tokens, error_info, db_parts
                elif provider == "Manus":
                    resp = self.manus_fallback.generate_response(message, self.system_prompt, self.history, selected_model, attached_files)
                    out_tokens = int(len(resp.split()) * 1.3)
                    return resp, selected_model, "Manus", in_tokens, out_tokens, error_info, db_parts
                else:
                    return "Contingencia cancelada por el usuario.", "Ninguno", "UI", 0, 0, error_info, db_parts
            else:
                 return f"Error crítico: API falló y no hay respaldo.", "Ninguno", "Error", 0, 0, error_info, [message]
