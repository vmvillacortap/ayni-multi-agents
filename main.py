import sys
import os
from dotenv import load_dotenv
from orchestrator import AyniOrchestrator
from clients.file_manager import scan_media_and_select

default_system_prompt = """
Eres un asistente experimentado en brindar soluciones rápidas y atinadas a un publico exigente que siempre se le ocurre nuevos pedidos y confian en ti para ayudarles o dejarles claro las limitaciones en pro de poder obtener resultados excepcionales, para ello tienes equipado un sistema multiagente con la filosofia Ayni y estas dispuesto a adaptarlo y mejorarlo en busqueda de cada vez dar mejores soluciones.

REGLAS DE ARCHIVOS Y GENERACIÓN VISUAL:
1. Solo usa la herramienta `guardar_documento` si se te pide explícitamente generar o guardar un archivo.
2. Si te piden INFOGRAFÍAS, DIAGRAMAS o IMÁGENES: Dado que no puedes generar píxeles directamente (PNG/JPG), DEBES programar la visualización utilizando código **SVG**, **HTML interactivo** o Markdown con **Mermaid.js**, y guardarlo obligatoriamente en disco mediante tu herramienta.
3. Para el parámetro `subcarpeta`: 
   - Si analizaste un archivo que YA estaba dentro de una subcarpeta en `media/` (ej. `media/proyecto_x/doc.txt`), DEBES reutilizar ese mismo nombre de subcarpeta (ej. `proyecto_x`).
   - ÚNICAMENTE crearás un nuevo nombre de subcarpeta temática (ej. `infografias`) si el archivo analizado NO estaba en `media/` o si la petición no incluyó ningún archivo de entrada.
4. El sistema antepondrá la fecha actual (YYYYMMDD_) al nombre del archivo de forma automática, no lo hagas tú.
"""

def load_system_prompt(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f: return f.read().strip()
    try:
        with open(filepath, 'w', encoding='utf-8') as f: f.write(default_system_prompt)
        print(f"\033[93m[Info] Archivo {filepath} creado con prompt por defecto.\033[0m")
    except Exception as e: print(f"\033[91m[Error] No se pudo crear {filepath}: {e}\033[0m")
    return default_system_prompt

def main():
    load_dotenv(override=True)
    print("=== Terminal Modular Ayni (Supervisor de Agentes) ===")
    
    os.makedirs("media", exist_ok=True)
    os.makedirs("agents", exist_ok=True)
    
    session_id = "SESION_PRUEBA_AYNI_005" 
    current_skill = "AGENTS.md"
    
    print("Escribe 'salir', 'quit' o 'exit' para terminar.\n")
    system_instructions = load_system_prompt(current_skill)
    
    try:
        orchestrator = AyniOrchestrator(session_id=session_id, default_system_prompt=system_instructions)
    except Exception as e:
        print(f"\033[91mError de inicialización:\033[0m {e}")
        sys.exit(1)

    while True:
        try:
            user_input = input("\n\033[92mTú:\033[0m ")
            if user_input.lower().strip() in ['salir', 'quit', 'exit']:
                print("\nHistorial consolidado en PostgreSQL. Cerrando sesión.")
                break
            if not user_input.strip(): continue

            archivos_seleccionados = scan_media_and_select(user_input)
            if archivos_seleccionados:
                print(f"\033[36m[Archivos a enviar]: {', '.join([os.path.basename(f) for f in archivos_seleccionados])}\033[0m")

            # MODIFICACIÓN: Desempaquetamos el 7mo valor (skill_used)
            response_text, active_model, provider, in_tokens, out_tokens, elapsed_ms, skill_used = orchestrator.process_request(user_input, archivos_seleccionados, current_skill)
            
            # Formateamos el tag del agente si se usó uno específico
            agent_info = f" [Agente: {skill_used}]" if skill_used != current_skill else ""
            
            if provider == "Ollama":
                 # FIX: Añadido el escape ANSI faltante (\033[0m)
                 print(f"\033[35m{active_model}{agent_info}: \033[0m {response_text}\n")
            elif provider == "Manus":
                 print(f"\033[36m{active_model}{agent_info}: \033[0m {response_text}\n")
            else:
                 print(f"\033[96mGemini ({active_model}){agent_info}: \033[0m {response_text}\n")
            
            print(f"\033[90m[Metricas DB] Motor: {active_model} | Tokens In: {in_tokens} Out: {out_tokens} | Tiempo: {elapsed_ms}ms\033[0m")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n\033[91mError de ejecución:\033[0m {str(e)}")

if __name__ == "__main__":
    main()
