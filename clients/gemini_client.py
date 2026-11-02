import os
import json
import datetime
import google.generativeai as genai
from dotenv import load_dotenv
from tavily import TavilyClient

from clients.ollama_client import OllamaFallbackManager
from clients.manus_client import ManusFallbackManager
from clients.fallback_ui import show_model_selector

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
    def __init__(self, history_file="chat_history.json", system_prompt="Eres un asistente experto."):
        load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No se encontró GEMINI_API_KEY en el archivo .env")
            
        genai.configure(api_key=api_key)
        self.history_file = history_file
        self.system_prompt = system_prompt
        self.tools = [obtener_hora_local, buscar_en_internet]
        
        self.ollama_fallback = OllamaFallbackManager() 
        self.manus_fallback = ManusFallbackManager()
        
        self.current_model_name = self._get_best_available_model()
        self.model = genai.GenerativeModel(
            model_name=self.current_model_name, 
            system_instruction=self.system_prompt,
            tools=self.tools
        )
        self.history = self._load_history()
        self.chat_session = self.model.start_chat(
            history=self.history,
            enable_automatic_function_calling=True
        )

    def _get_best_available_model(self):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            preferences = ['models/gemini-3.8-flash', 'models/gemini-3.7-flash', 'models/gemini-3.5-flash', 'models/gemini-2.5-flash', 'models/gemini-1.5-flash-latest']
            for pref in preferences:
                if pref in available_models: return pref
            if available_models: return available_models[0]
            raise ValueError("No hay modelos generateContent disponibles.")
        except Exception:
            return 'models/gemini-1.5-flash-latest'

    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f: return json.load(f)
            except Exception: return []
        return []

    def save_history(self):
        formatted_history = []
        for message in self.chat_session.history:
            try:
                formatted_history.append({"role": message.role, "parts": [part.text for part in message.parts]})
            except AttributeError: pass
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(formatted_history, f, indent=4, ensure_ascii=False)

    def send_message_sync(self, message):
        error_info = None
        try:
            response = self.chat_session.send_message(message, request_options={"timeout": 15})
            
            in_tokens, out_tokens = 0, 0
            if hasattr(response, 'usage_metadata'):
                in_tokens = response.usage_metadata.prompt_token_count
                out_tokens = response.usage_metadata.candidates_token_count
                
            return response.text, self.current_model_name, "Gemini", in_tokens, out_tokens, error_info
        except Exception as e:
            error_info = {"type": type(e).__name__, "message": str(e), "fallback": True}
            print(f"\n\033[93m[Alerta] Falla en API de Gemini ({e}). Evaluando alternativas...\033[0m")
            
            if self.ollama_fallback.is_available() or self.manus_fallback.is_available():
                print(f"\033[93m[UI] Abriendo Centro de Contingencia Multi-Agente (Pop-up)...\033[0m")
                provider, selected_model = show_model_selector(self.ollama_fallback.api_url, self.manus_fallback.get_models())
                
                # Estimación aproximada de tokens para motores que no devuelven métricas en crudo
                in_tokens = int(len(message.split()) * 1.3)
                
                if provider == "Ollama":
                    resp = self.ollama_fallback.generate_response(message, self.system_prompt)
                    out_tokens = int(len(resp.split()) * 1.3)
                    return resp, selected_model, "Ollama", in_tokens, out_tokens, error_info
                elif provider == "Manus":
                    resp = self.manus_fallback.generate_response(message, self.system_prompt, selected_model)
                    out_tokens = int(len(resp.split()) * 1.3)
                    return resp, selected_model, "Manus", in_tokens, out_tokens, error_info
                else:
                    return "Contingencia cancelada por el usuario.", "Ninguno", "UI", 0, 0, error_info
            else:
                 return f"Error crítico: API Gemini falló y no hay respaldo.", "Ninguno", "Error", 0, 0, error_info
