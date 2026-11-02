import sys
import time
import os
from clients.gemini_client import GeminiSessionManager

default_system_prompt = """
Eres un asistente experimentado en brindar soluciones rápidas y atinadas a un publico exigente que siempre se le ocurre nuevos pedidos y confian en ti para ayudarles o dejarles claro las limitaciones en pro de poder obtener resultados excepcionales, para ello tienes equipado un sistema multiagente con la filosofia Ayni y estas dispuesto a adaptarlo y mejorarlo en busqueda de cada vez dar mejores soluciones.
"""

def load_system_prompt(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read().strip()
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(default_system_prompt)
        print(f"\033[93m[Info] Archivo {filepath} creado con prompt por defecto.\033[0m")
    except Exception as e:
        print(f"\033[91m[Error] No se pudo crear {filepath}: {e}\033[0m")
    return default_system_prompt

def main():
    print("=== Terminal Modular NEXO (Gemini + Ollama) ===")
    print("Escribe 'salir', 'quit' o 'exit' para terminar.\n")
    
    prompt_file = "AGENTS.md"
    system_instructions = load_system_prompt(prompt_file)
    
    try:
        manager = GeminiSessionManager(system_prompt=system_instructions)
    except Exception as e:
        print(f"\033[91mError de inicialización:\033[0m {e}")
        sys.exit(1)

    while True:
        try:
            user_input = input("\n\033[92mTú:\033[0m ")
            
            if user_input.lower().strip() in ['salir', 'quit', 'exit']:
                print("\nGuardando historial de sesión...")
                manager.save_history()
                print("Cerrando sesión.")
                break
                
            if not user_input.strip():
                continue

            print("\033[93m[⚙️ Procesando intención, herramientas y respuesta...]\033[0m", end="\r", flush=True)
            
            start_time = time.time()
            response_text, active_model = manager.send_message_sync(user_input)
            
            print("\033[K", end="") 
            
            model_display = active_model.split('/')[-1]
            
            if "Ollama" in active_model:
                 print(f"\033[35m{model_display}:\033[0m {response_text}\n")
            else:
                 print(f"\033[94mGemini ({model_display}):\033[0m {response_text}\n")
            
            elapsed_time = round(time.time() - start_time, 2)
            
            if "Ollama" not in active_model:
                tokens = manager.get_token_count()
                print(f"\033[90m[Contexto: {tokens} tokens | Engine: {model_display} | Tiempo: {elapsed_time}s]\033[0m")
            else:
                 print(f"\033[90m[Engine: {model_display} | Tiempo: {elapsed_time}s]\033[0m")
            
        except KeyboardInterrupt:
            print("\nInterrupción detectada. Guardando historial...")
            manager.save_history()
            break
        except Exception as e:
            print(f"\n\033[91mError de ejecución:\033[0m {str(e)}\n")

if __name__ == "__main__":
    main()
