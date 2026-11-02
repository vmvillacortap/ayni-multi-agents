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
from clients.file_manager import guardar_documento

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
        load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No se encontró GEMINI_API_KEY en el archivo .env")
            
        genai.configure(api_key=api_key)
        self.session_id = session_id
        self.db = db_manager
        self.system_prompt = system_prompt
        # Inyectamos la nueva herramienta para guardar archivos
        self.tools = [obtener_hora_local, buscar_en_internet, guardar_documento]
        
        self.ollama_fallback = OllamaFallbackManager() 
        self.manus_fallback = ManusFallbackManager()
        
        self.pools = self._build_dynamic_pools()
        self.history = self.db.load_history(self.session_id)
        
        self.current_model_name = self.pools['fast'][0] if self.pools['fast'] else 'models/gemini-1.5-flash-latest'
        self.model = None
        self.chat_session = None
        self._switch_active_model(self.current_model_name)

    def _build_dynamic_pools(self):
        pools = {'router': [], 'fast': [], 'pro': []}
        try:
            raw_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            multimodal_models = [m for m in raw_models if ('1.5' in m or '2.' in m or '3.' in m or 'vision' in m) and 'embedding' not in m and 'aqa' not in m]
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
        self._switch_active_model(self.pools[target_pool][0])
        
        print(f"\033[93m[⚙️ Ejecutando en pool {target_pool.upper()}: {self.current_model_name}...]\033[0m", end="\r", flush=True)
        
        # Procesamiento Multimodal para Gemini
        gemini_parts = [message]
        uploaded_gemini_files = []
        
        if attached_files:
            print("\n\033[90m[Gemini] Subiendo archivos a la nube para análisis multimodal...\033[0m")
            for file_path in attached_files:
                uploaded = genai.upload_file(file_path)
                uploaded_gemini_files.append(uploaded)
                gemini_parts.append(uploaded)
                
                # Esperar procesamiento si es video o pdf pesado
                while uploaded.state.name == "PROCESSING":
                    print("\033[90mProcesando archivo...\033[0m", end="\r")
                    time.sleep(2)
                    uploaded = genai.get_file(uploaded.name)
        
        try:
            # Enviamos tanto el texto como los objetos binarios subidos
            response = self.chat_session.send_message(gemini_parts, request_options={"timeout": 60})
            
            in_tokens, out_tokens = 0, 0
            if hasattr(response, 'usage_metadata'):
                in_tokens = response.usage_metadata.prompt_token_count
                out_tokens = response.usage_metadata.candidates_token_count
            
            # Formatear parts para la DB (solo los nombres de archivo)
            db_parts = [message] + [f"[Archivo Adjunto: {f}]" for f in attached_files]
                
            return response.text, self.current_model_name, "Gemini", in_tokens, out_tokens, error_info, db_parts
            
        except Exception as e:
            error_msg = str(e)
            
            # --- ESTRATEGIA DE MITIGACIÓN PARA ERROR 429 ---
            if "429" in error_msg and "quota" in error_msg.lower():
                print(f"\n\033[93m[Cuota Agotada] El modelo {self.current_model_name} agotó su cuota.\033[0m")
                if self.current_model_name in self.pools[target_pool]:
                    self.pools[target_pool].remove(self.current_model_name)
                
                if self.pools[target_pool]:
                    nuevo_modelo = self.pools[target_pool][0]
                    print(f"\033[92m[Rotación Dinámica] Cambiando a {nuevo_modelo}...\033[0m")
                    self._switch_active_model(nuevo_modelo)
                    try:
                        return self.send_message_sync(message, attached_files)
                    except Exception as retry_e:
                        print(f"\n\033[91m[Error en Reintento]: {retry_e}\033[0m")
            
            # --- CONTINGENCIA (POP-UP) ---
            error_info = {"type": type(e).__name__, "message": error_msg, "fallback": True}
            print(f"\n\033[93m[Alerta] Falla en API de Gemini ({e}).\033[0m")
            
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
