import sys
import time
import os
from clients.gemini_client import GeminiSessionManager
from database.db_manager import DBManager

default_system_prompt = """
Eres un asistente experimentado en brindar soluciones rápidas y atinadas a un publico exigente que siempre se le ocurre nuevos pedidos y confian en ti para ayudarles o dejarles claro las limitaciones en pro de poder obtener resultados excepcionales, para ello tienes equipado un sistema multiagente con la filosofia Ayni y estas dispuesto a adaptarlo y mejorarlo en busqueda de cada vez dar mejores soluciones.
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
    print("=== Terminal Modular Ayni (Historial Persistente en DB) ===")
    
    db = DBManager()
    if not db.Session:
        print("\033[91mNo se pudo conectar a la base de datos. Historial será efímero.\033[0m")
    
    # Podrías generar un UUID nuevo cada vez, o reutilizar uno para mantener una sesión de prueba activa
    session_id = "SESION_PRUEBA_AYNI_001" 
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

            print("\033[93m[⚙️ Procesando intención y enrutando...]\033[0m", end="\r", flush=True)
            
            start_time = time.time()
            response_text, active_model, provider, in_tokens, out_tokens, error_info = manager.send_message_sync(user_input)
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            
            print("\033[K", end="") 
            
            # Logueo de métricas principales y captura del ID
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
            
            # Sincronizamos explícitamente el turno de chat en la BD y actualizamos memoria local
            if interaction_id:
                manager._sync_history_to_db(interaction_id, user_input, response_text)
            
            if provider == "Ollama":
                 print(f"\033[35m{active_model}:\033[0m {response_text}\n")
            elif provider == "Manus":
                 print(f"\033[36m{active_model}:\033[0m {response_text}\n")
            else:
                 print(f"\033[94mGemini ({active_model}):\033[0m {response_text}\n")
            
            print(f"\033[90m[Metricas DB] Motor: {active_model} | Tokens In: {in_tokens} Out: {out_tokens} | Tiempo: {elapsed_ms}ms\033[0m")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n\033[91mError de ejecución:\033[0m {str(e)}\n")

if __name__ == "__main__":
    main()
