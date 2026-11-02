import os
import requests

class ManusFallbackManager:
    def __init__(self, api_key=None, api_url="https://api.manus.ai/v1/chat/completions"):
        self.api_key = api_key or os.environ.get("MANUS_API_KEY")
        self.api_url = api_url
        self.available_models = ["manus-1", "manus-pro", "manus-vision"]

    def is_available(self):
        return bool(self.api_key)

    def get_models(self):
        return self.available_models if self.is_available() else []

    def generate_response(self, prompt, system_prompt, model_name="manus-1"):
        if not self.api_key:
            return "Error: MANUS_API_KEY no está configurada en el entorno."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error crítico en la API de Manus AI: {e}"
