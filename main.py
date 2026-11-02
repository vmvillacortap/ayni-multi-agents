import sys
import time
import os
import uuid
from clients.gemini_client import GeminiSessionManager
from database.db_manager import DBManager
from clients.file_manager import scan_media_and_select

default_system_prompt = """
Eres un asistente experimentado en brindar soluciones rápidas y atinadas a un publico exigente que siempre se le ocurre nuevos pedidos y confian en ti para ayudarles o dejarles claro las limitaciones en pro de poder obtener resultados excepcionales, para ello tienes equipado un sistema multiagente con la filosofia Ayni y estas dispuesto a adaptarlo y mejorarlo en busqueda de cada vez dar mejores soluciones.

REGLAS DE ARCHIVOS (Escritura y Subcarpetas):
1. Solo usa la herramienta `guardar_documento` si se te pide explícitamente generar o guardar un archivo.
2. Para el parámetro `subcarpeta`: 
   - Si analizaste un archivo que YA estaba dentro de una subcarpeta en `media/` (ej. `media/proyecto_x/doc.txt`), DEBES reutilizar ese mismo nombre de subcarpeta (ej. `proyecto_x`).
   - ÚNICAMENTE crearás un nuevo nombre de subcarpeta temática si el archivo analizado NO estaba en `media/` o si la petición no incluyó ningún archivo de entrada.
3. El sistema antepondrá la fecha actual (YYYYMMDD_) al nombre del archivo de forma automática, no lo hagas tú.
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
    print("=== Terminal Modular Ayni (Escáner de Proyecto Integral) ===")
    
    os.makedirs("media", exist_ok=True)
    db = DBManager()
    if not db.Session:
        print("\033[91mNo se pudo conectar a la base de datos. Historial será efímero.\033[0m")
    
    session_id = "SESION_PRUEBA_AYNI_003" 
    current_skill = "AGENTS.md"
    
    print("Escribe 'salir', 'quit' o 'exit' para terminar.\n")
    system_instructions = load_system_prompt(current_skill)
    
    try:
        manager = GeminiSessionManager(session_id=session_id, db_manager=db, system_prompt=system_instructions)
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
                print(f"\033[96m[Archivos a enviar]: {', '.join([os.path.basename(f) for f in archivos_seleccionados])}\033[0m")

            start_time = time.time()
            response_text, active_model, provider, in_tokens, out_tokens, error_info, db_parts = manager.send_message_sync(user_input, archivos_seleccionados)
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            
            interaction_id = db.log_interaction(
                session_id=session_id,
                user_input=user_input,
                response_text=response_text,
                provider=provider,
                model_used=active_model,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                response_time_ms=elapsed_ms,
                skill_used=current_skill,
                error_data=error_info
            )
            
            if interaction_id:
                manager._sync_history_to_db(interaction_id, db_parts, response_text)
            
            if provider == "Ollama":
                 print(f"\033[35m{active_model}: [0m {response_text}\n")
            elif provider == "Manus":
                 print(f"\033[36m{active_model}: [0m {response_text}\n")
            else:
                 print(f"\033[94mGemini ({active_model}): [0m {response_text}\n")
            
            print(f"\033[90m[Metricas DB] Motor: {active_model} | Tokens In: {in_tokens} Out: {out_tokens} | Tiempo: {elapsed_ms}ms\033[0m")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n\033[91mError de ejecución:\033[0m {str(e)}\n")

if __name__ == "__main__":
    main()
