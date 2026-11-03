import os
import json
import time
from google import genai
from google.genai import types
from tavily import TavilyClient
from clients.file_manager import guardar_documento, extract_text_from_doc

def obtener_hora_local():
    import datetime
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
        self.session_id = session_id
        self.db = db_manager
        self.system_prompt = system_prompt
        self.tools = [obtener_hora_local, buscar_en_internet, guardar_documento]
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Falta GEMINI_API_KEY en el archivo .env")
            
        # Instancia del nuevo SDK google.genai
        self.client = genai.Client(api_key=api_key)
        
        self.pools = self._build_dynamic_pools()
        self.history = self.db.load_history(self.session_id)
        
        valid_fast_models = [m for m in self.pools['fast'] if 'tts' not in m]
        self.current_model_name = valid_fast_models[0] if valid_fast_models else 'gemini-1.5-flash-latest'
        
        self.model = None
        self.chat_session = None
        self._switch_active_model(self.current_model_name)

    def _build_dynamic_pools(self):
        pools = {'router': [], 'fast': [], 'pro': []}
        try:
            # En el nuevo SDK client.models.list() devuelve objetos con atributo name
            raw_models = [m.name for m in self.client.models.list()]
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
            return {'router': ['gemini-1.5-flash-latest'], 'fast': ['gemini-1.5-flash-latest'], 'pro': ['gemini-1.5-pro-latest']}

    def _switch_active_model(self, model_name):
        if self.current_model_name != model_name or self.chat_session is None:
            self.current_model_name = model_name
            
            # El historial de la DB debe mapearse para evitar problemas con la validación tipada estricta
            formatted_history = []
            for msg in self.history:
                parts = [{"text": p} for p in msg["parts"]]
                formatted_history.append({"role": msg["role"], "parts": parts})
            
            # Inicialización de sesión de chat bajo el nuevo SDK
            self.chat_session = self.client.chats.create(
                model=self.current_model_name,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    tools=self.tools
                ),
                history=formatted_history
            )

    def _analyze_intent(self, prompt, attached_files):
        if attached_files:
            return {"complexity": "high", "is_complaint": False}
            
        router_model = self.pools['router'][0]
        
        sys_prompt = """Clasifica la petición. Responde ÚNICAMENTE con un JSON: {"complexity": "low" | "high", "is_complaint": true | false}"""
        try:
            # Generación atómica bajo el nuevo SDK (sin inicializar chat)
            res = self.client.models.generate_content(
                model=router_model,
                contents=f"{sys_prompt}\n\nPetición: {prompt}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", 
                    temperature=0.0
                )
            )
            return json.loads(res.text)
        except Exception:
            return {"complexity": "low", "is_complaint": False}

    def send_message_sync(self, message, attached_files=None):
        error_info = None
        attached_files = attached_files or []
        db_parts = [message] + [f"[Archivo Adjunto: {f}]" for f in attached_files]
            
        print("\033[93m[🧠 Enrutador Analizando Complejidad e Intención...]\033[0m", end="\r", flush=True)
        intent = self._analyze_intent(message, attached_files)
        
        target_pool = 'pro' if (intent.get('is_complaint', False) or intent.get('complexity', 'low') == 'high' or attached_files) else 'fast'
        
        if target_pool == 'pro' and not self.pools['pro']:
            print("\n\033[93m[Ayni] Pool PRO agotado. Redirigiendo petición compleja al Pool FAST (Flash)...\033[0m")
            target_pool = 'fast'
            
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
                        # Nuevo File API Upload
                        uploaded = self.client.files.upload(file=file_path)
                        gemini_parts.append(uploaded)
                        
                        while uploaded.state.name == "PROCESSING":
                            print("\033[90mProcesando archivo en la nube...\033[0m", end="\r")
                            time.sleep(2)
                            uploaded = self.client.files.get(name=uploaded.name)
                        print(f"\033[90mSubido y procesado: {os.path.basename(file_path)}          \033[0m")
            
            response = self.chat_session.send_message(gemini_parts)
            
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
                    return self.send_message_sync(message, attached_files)
                except Exception as retry_e:
                    raise Exception(f"Fallo tras rotación: {str(retry_e)}")
            
            raise Exception(error_msg)