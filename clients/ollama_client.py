import requests

class OllamaFallbackManager:
    def __init__(self, preferred_models=None, api_url="http://localhost:11434/api"):
        if preferred_models is None:
            preferred_models = ["llava:7b", "gemma:2b", "llama3", "deepseek-r1:8b"]
        self.api_url = api_url
        self.model_name = self._auto_select_model(preferred_models)

    def _auto_select_model(self, preferences):
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=2)
            if response.status_code == 200:
                installed_models = [model['name'] for model in response.json().get('models', [])]
                if not installed_models: return None
                for pref in preferences:
                    if pref in installed_models: return pref
                return installed_models[0]
        except requests.exceptions.RequestException: return None
        return None

    def is_available(self):
        try:
            return requests.get(f"{self.api_url}/tags", timeout=2).status_code == 200
        except requests.exceptions.RequestException:
            return False

    def generate_response(self, prompt, system_prompt, history=None):
        if not self.model_name: return "Error: No hay modelo local configurado."
        
        # Construimos el texto del historial para Ollama (endpoint /generate)
        history_text = ""
        if history:
            for msg in history:
                role_name = "Usuario" if msg["role"] == "user" else "Asistente"
                content = msg["parts"][0] if isinstance(msg["parts"], list) else str(msg["parts"])
                history_text += f"{role_name}: {content}\n"
                
        full_prompt = f"{system_prompt}\n\n{history_text}Usuario: {prompt}\nAsistente:"
        
        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False
        }
        try:
            response = requests.post(f"{self.api_url}/generate", json=payload, timeout=120)
            response.raise_for_status()
            return response.json().get("response", "Error al procesar la respuesta local.")
        except requests.exceptions.RequestException as e:
            return f"Error crítico en el modelo local (Ollama): {e}"
