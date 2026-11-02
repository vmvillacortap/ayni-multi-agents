import os
import json
import datetime
import google.generativeai as genai
from dotenv import load_dotenv
from tavily import TavilyClient

from clients.ollama_client import OllamaFallbackManager
# Importamos la nueva UI para selección de modelos
from clients.ollama_ui import show_model_selector

def obtener_hora_local():
    """Útil para saber la hora, fecha o día actual del sistema."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def buscar_en_internet(consulta: str):
    """Útil para buscar información actualizada, noticias, clima o datos externos en internet."""
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
            preferences = [
                'models/gemini-3.8-flash', 'models/gemini-3.7-flash',
                'models/gemini-3.5-flash', 'models/gemini-2.5-flash',
                'models/gemini-1.5-flash-latest'
            ]
            for pref in preferences:
                if pref in available_models:
                    return pref
            if available_models:
                return available_models[0]
            raise ValueError("No hay modelos generateContent disponibles.")
        except Exception as e:
            return 'models/gemini-1.5-flash-latest'

    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_history(self):
        formatted_history = []
        for message in self.chat_session.history:
            try:
                parts_text = [part.text for part in message.parts]
                formatted_history.append({"role": message.role, "parts": parts_text})
            except AttributeError:
                 pass
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(formatted_history, f, indent=4, ensure_ascii=False)

    def get_token_count(self):
        if not self.chat_session.history:
            return 0
        try:
            return self.model.count_tokens(self.chat_session.history).total_tokens
        except Exception:
            return 0

    def send_message_sync(self, message):
        try:
            response = self.chat_session.send_message(message, request_options={"timeout": 15})
            return response.text, self.current_model_name
        except Exception as e:
            print(f"\n\033[93m[Alerta] Falla en API de Gemini ({e}).\033[0m")
            
            if self.ollama_fallback.is_available():
                print(f"\033[93m[UI] Abriendo selector de Ollama local (Pop-up)...\033[0m")
                
                # Desplegar interfaz gráfica
                selected_model = show_model_selector(self.ollama_fallback.api_url)
                
                if selected_model:
                    print(f"\033[90m[Ollama] Conectando con modelo '{selected_model}'...\033[0m")
                    self.ollama_fallback.model_name = selected_model
                    response_text = self.ollama_fallback.generate_response(message, self.system_prompt)
                    return response_text, f"OllamaLocal ({selected_model})"
                else:
                    return "El usuario canceló la selección de modelo local en el Pop-up.", "Sistema Cancelado"
            else:
                 return f"Error crítico: API falló y Ollama no responde. Detalle: {e}", "Sistema Fallido"
