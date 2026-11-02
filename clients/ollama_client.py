import requests

class OllamaFallbackManager:
    """Gestor de fallback local que interactúa con la API de Ollama."""
    def __init__(self, model_name="gemma:2b", api_url="http://localhost:11434/api/generate"):
        self.model_name = model_name
        self.api_url = api_url

    def is_available(self):
        """Verifica si el servicio de Ollama está corriendo."""
        try:
            response = requests.get(self.api_url.replace("/generate", "/tags"), timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def generate_response(self, prompt, system_prompt):
        """Genera una respuesta utilizando el modelo local en Ollama."""
        full_prompt = f"{system_prompt}\n\nUsuario: {prompt}\nAsistente:"
        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False
        }
        try:
            response = requests.post(self.api_url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json().get("response", "Error al procesar la respuesta local.")
        except requests.exceptions.RequestException as e:
            return f"Error crítico en el modelo local (Ollama): {e}"
