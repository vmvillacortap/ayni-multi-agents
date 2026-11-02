import os
import requests
from clients.file_manager import encode_image_base64, extract_text_from_doc

class ManusFallbackManager:
    def __init__(self, api_key=None, api_url="https://api.manus.ai/v1/chat/completions"):
        self.api_key = api_key or os.environ.get("MANUS_API_KEY")
        self.api_url = api_url
        self.available_models = ["manus-1", "manus-pro", "manus-vision"]

    def is_available(self):
        return bool(self.api_key)

    def get_models(self):
        return self.available_models if self.is_available() else []

    def generate_response(self, prompt, system_prompt, history=None, model_name="manus-1", attached_files=None):
        if not self.api_key:
            return "Error: MANUS_API_KEY no está configurada en el entorno."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "assistant"
                content = msg["parts"][0] if isinstance(msg["parts"], list) else str(msg["parts"])
                messages.append({"role": role, "content": content})
                
        # Estructurar mensaje multimodal OpenAi-like
        content_list = []
        docs_text = ""
        
        if attached_files:
            for fpath in attached_files:
                ext = os.path.splitext(fpath)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    b64_image = encode_image_base64(fpath)
                    content_list.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}
                    })
                else:
                    docs_text += f"\n--- Contenido de {os.path.basename(fpath)} ---\n"
                    docs_text += extract_text_from_doc(fpath) + "\n"
        
        final_prompt_text = docs_text + prompt
        content_list.insert(0, {"type": "text", "text": final_prompt_text})
        
        messages.append({"role": "user", "content": content_list})
        
        payload = {
            "model": model_name,
            "messages": messages
        }
        
        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error crítico en la API de Manus AI: {e}"
