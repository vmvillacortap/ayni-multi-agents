import requests

class OllamaFallbackManager:
    """Gestor de fallback local que interactúa con la API de Ollama y auto-descubre modelos."""
    def __init__(self, preferred_models=None, api_url="http://localhost:11434/api"):
        if preferred_models is None:
            # Lista de modelos por defecto. 
            # NOTA: Para multimodalidad se recomienda 'llava'
            preferred_models = ["llava:7b", "gemma:2b", "llama3", "deepseek-r1:8b"]
            
        self.api_url = api_url
        self.model_name = self._auto_select_model(preferred_models)

    def _auto_select_model(self, preferences):
        """Consulta a Ollama para listar los modelos instalados y elige el mejor."""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=2)
            if response.status_code == 200:
                installed_models = [model['name'] for model in response.json().get('models', [])]
                if not installed_models:
                    return None
                for pref in preferences:
                    if pref in installed_models:
                        return pref
                return installed_models[0]
        except requests.exceptions.RequestException:
            return None
        return None

    def is_available(self):
        """Verifica si el servicio de Ollama está corriendo."""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def generate_response(self, prompt, system_prompt):
        """Genera una respuesta utilizando el modelo local en Ollama."""
        if not self.model_name:
            return "Error: No hay modelo local configurado."
            
        full_prompt = f"{system_prompt}\n\nUsuario: {prompt}\nAsistente:"
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
