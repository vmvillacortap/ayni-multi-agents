import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

class GeminiSessionManager:
    def __init__(self, history_file="chat_history.json", system_prompt="Eres un asistente experto."):
        load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No se encontró GEMINI_API_KEY en el archivo .env")
        
        genai.configure(api_key=api_key)
        self.history_file = history_file
        
        # Inyección de sistema (System Instructions)
        self.model = genai.GenerativeModel(
            model_name='gemini-1.5-flash', # Alias actualizado
            system_instruction=system_prompt
        )
                
        # Persistencia de contexto: Carga inicial
        self.history = self._load_history()
        self.chat_session = self.model.start_chat(history=self.history)

    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Advertencia: No se pudo leer el historial local ({e}). Iniciando nueva sesión.")
                return []
        return []

    def save_history(self):
        # Serialización del historial para guardado local
        formatted_history = []
        for message in self.chat_session.history:
            formatted_history.append({
                "role": message.role,
                "parts": [part.text for part in message.parts]
            })
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(formatted_history, f, indent=4, ensure_ascii=False)

    def get_token_count(self):
        # Manejo y monitoreo de tokens
        if not self.chat_session.history:
            return 0
        return self.model.count_tokens(self.chat_session.history).total_tokens

    def send_message_stream(self, message):
        return self.chat_session.send_message(message, stream=True)