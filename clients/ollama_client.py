import requests
import os
import re
import time
from clients.file_manager import encode_image_base64, extract_text_from_doc, guardar_documento

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
            
    def _parse_and_execute_tools(self, response_text):
        """Interceptor Regex Híbrido: Captura el tag estricto o hace auto-recovery de bloques de código sueltos."""
        # 1. Intento principal: Etiqueta estricta [GUARDAR_COMO: ...]
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
            
        # 2. Heurística de Auto-Recovery para modelos pequeños (Qwen/Gemma) que olvidan la etiqueta
        # Busca bloques de código markdown clásicos de formatos visuales/código
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
                
                # Anexamos la confirmación al final sin borrar su explicación
                modified_response += f"\n\n[Auto-Recovery Ayni]: Detecté el código y lo guardé por ti. {result}\n"
                
        return modified_response

    def generate_response(self, prompt, system_prompt, history=None, attached_files=None):
        if not self.model_name: return "Error: No hay modelo local configurado."
        
        # INYECCIÓN: One-Shot Prompting (Los modelos pequeños necesitan ejemplos visuales de cómo comportarse)
        local_system_prompt = system_prompt + """
        \n\n[REGLA ESTRICTA DE HERRAMIENTAS - EJEMPLO REQUERIDO]
        No tienes acceso a funciones ejecutables nativas. Para generar infografías, SVG, HTML o archivos, DEBES usar exactamente este bloque de etiquetas en tu respuesta:
        
        [GUARDAR_COMO: diagrama.svg | infografias]
        <svg width="100" height="100"><circle cx="50" cy="50" r="40" /></svg>
        [/GUARDAR]
        """
        
        history_text = ""
        if history:
            for msg in history:
                role_name = "Usuario" if msg["role"] == "user" else "Asistente"
                content = msg["parts"][0] if isinstance(msg["parts"], list) else str(msg["parts"])
                history_text += f"{role_name}: {content}\n"
                
        images_b64 = []
        docs_text = ""
        if attached_files:
            for fpath in attached_files:
                ext = os.path.splitext(fpath)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    images_b64.append(encode_image_base64(fpath))
                else:
                    docs_text += f"\n--- Contenido de {os.path.basename(fpath)} ---\n"
                    docs_text += extract_text_from_doc(fpath) + "\n"
        
        full_prompt = f"{local_system_prompt}\n\n{history_text}Usuario: {docs_text}\n{prompt}\nAsistente:"
        
        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False
        }
        
        if images_b64:
            payload["images"] = images_b64
            
        try:
            response = requests.post(f"{self.api_url}/generate", json=payload, timeout=120)
            response.raise_for_status()
            raw_text = response.json().get("response", "Error al procesar.")
            return self._parse_and_execute_tools(raw_text)
        except requests.exceptions.RequestException as e:
            return f"Error crítico en el modelo local (Ollama): {e}"
