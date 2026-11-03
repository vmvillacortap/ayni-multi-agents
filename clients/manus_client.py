import os
import requests
import re
import time
from clients.file_manager import encode_image_base64, extract_text_from_doc, guardar_documento

class ManusFallbackManager:
    def __init__(self, api_key=None, api_url="https://api.manus.ai/v1/chat/completions"):
        self.api_key = api_key or os.environ.get("MANUS_API_KEY")
        self.api_url = api_url
        self.available_models = ["manus-1", "manus-pro", "manus-vision"]

    def is_available(self):
        return bool(self.api_key)

    def get_models(self):
        return self.available_models if self.is_available() else []
        
    def _parse_and_execute_tools(self, response_text):
        """Interceptor Regex Híbrido: Captura el tag estricto o hace auto-recovery de bloques de código sueltos."""
        pattern = r"\[GUARDAR_COMO:\s*([^|]+?)\s*\|\s*([^\]]+?)\](.*?)\[/GUARDAR\]"
        matches = list(re.finditer(pattern, response_text, re.DOTALL))
        
        modified_response = response_text
        if matches:
            for match in matches:
                filename = match.group(1).strip()
                folder = match.group(2).strip()
                content = match.group(3).strip()
                
                result = guardar_documento(content, filename, folder)
                modified_response = modified_response.replace(match.group(0), f"\n\n{result}\n\n")
            return modified_response
            
        # Heurística de Auto-Recovery para modelos que olvidan la etiqueta
        fallback_pattern = r"```(svg|html|mermaid|python|py|md|json)\s*\n(.*?)\n```"
        fallback_matches = list(re.finditer(fallback_pattern, response_text, re.DOTALL))
        
        if fallback_matches:
            for i, match in enumerate(fallback_matches):
                ext = match.group(1).strip().lower()
                content = match.group(2).strip()
                
                if ext in ['python', 'py']:
                    ext = "py"
                    folder = "scripts"
                elif ext == "mermaid":
                    content = f"```mermaid\n{content}\n```"
                    ext = "md"
                    folder = "infografias"
                elif ext in ["svg", "html"]:
                    folder = "infografias"
                else:
                    folder = "general"
                    
                filename = f"auto_generado_{int(time.time())}_{i}.{ext}"
                result = guardar_documento(content, filename, folder)
                
                modified_response += f"\n\n[Auto-Recovery Ayni]: Detecté el código y lo guardé por ti. {result}\n"
                
        return modified_response

    def generate_response(self, prompt, system_prompt, history=None, model_name="manus-1", attached_files=None):
        if not self.api_key:
            return "Error: MANUS_API_KEY no está configurada en el entorno."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # INYECCIÓN: One-Shot Prompting
        local_system_prompt = system_prompt + """
        \n\n[REGLA ESTRICTA DE HERRAMIENTAS - EJEMPLO REQUERIDO]
        No tienes acceso a funciones ejecutables nativas. Para generar infografías, SVG, HTML o archivos, DEBES usar exactamente este bloque de etiquetas en tu respuesta:
        
        [GUARDAR_COMO: diagrama.svg | infografias]
        <svg width="100" height="100"><circle cx="50" cy="50" r="40" /></svg>
        [/GUARDAR]
        """
        
        messages = [{"role": "system", "content": local_system_prompt}]
        
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "assistant"
                content = msg["parts"][0] if isinstance(msg["parts"], list) else str(msg["parts"])
                messages.append({"role": role, "content": content})
                
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
            raw_text = response.json()["choices"][0]["message"]["content"]
            return self._parse_and_execute_tools(raw_text)
        except Exception as e:
            return f"Error crítico en la API de Manus AI: {e}"
