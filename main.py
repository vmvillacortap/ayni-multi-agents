import sys
from gemini_client import GeminiSessionManager

def main():
    print("=== Terminal de Gemini Pro (Arquitectura Desacoplada) ===")
    print("Escribe 'salir', 'quit' o 'exit' para terminar.\n")
    
    try:
        # Inicialización inyectando el prompt de sistema deseado
        manager = GeminiSessionManager(
            system_prompt="Eres un arquitecto de software y científico de datos senior. Responde siempre con precisión técnica y concisión."
        )
    except Exception as e:
        print(f"\033[91mError de inicialización:\033[0m {e}")
        sys.exit(1)

    while True:
        try:
            user_input = input("\033[92mTú:\033[0m ")
            
            if user_input.lower().strip() in ['salir', 'quit', 'exit']:
                print("\nGuardando historial de sesión...")
                manager.save_history()
                print("Cerrando sesión. Ejecución finalizada.")
                break
                
            if not user_input.strip():
                continue

            print("\033[94mGemini:\033[0m ", end="", flush=True)
            
            # Consumo de la respuesta en streaming
            response_stream = manager.send_message_stream(user_input)
            for chunk in response_stream:
                print(chunk.text, end="", flush=True)
            print("\n")
            
            # Impresión de métricas de la capa de datos
            tokens = manager.get_token_count()
            print(f"\033[90m[Contexto actual: {tokens} tokens]\033[0m\n")
            
        except KeyboardInterrupt:
            print("\nInterrupción detectada. Guardando historial y cerrando forzosamente...")
            manager.save_history()
            break
        except Exception as e:
            print(f"\n\033[91mError de ejecución:\033[0m {str(e)}\n")

if __name__ == "__main__":
    main()