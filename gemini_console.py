import os
import sys
import google.generativeai as genai
from dotenv import load_dotenv

def init_gemini():
    # Cargar variables de entorno de forma local
    load_dotenv()
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: No se encontró GEMINI_API_KEY en el archivo .env")
        sys.exit(1)
        
    genai.configure(api_key=api_key)
    # Se recomienda usar gemini-1.5-pro para razonamiento complejo
    model = genai.GenerativeModel('gemini-1.5-pro')
    return model.start_chat(history=[])

def main():
    print("=== Terminal de Gemini Pro ===")
    print("Escribe 'salir', 'quit' o 'exit' para terminar.\n")
    
    try:
        chat_session = init_gemini()
    except Exception as e:
        print(f"Error de inicialización: {e}")
        return

    while True:
        try:
            user_input = input("\033[92mTú:\033[0m ") # Color verde para el usuario
            
            if user_input.lower().strip() in ['salir', 'quit', 'exit']:
                print("Cerrando sesión...")
                break
                
            if not user_input.strip():
                continue

            print("\033[94mGemini:\033[0m ", end="", flush=True) # Color azul para el bot
            
            # Usar streaming mejora drásticamente la UX en consola
            response = chat_session.send_message(user_input, stream=True)
            
            for chunk in response:
                print(chunk.text, end="", flush=True)
            print("\n")
            
        except KeyboardInterrupt:
            print("\nCerrando sesión de forma forzada...")
            break
        except Exception as e:
            print(f"\n\033[91mError de API:\033[0m {str(e)}\n")

if __name__ == "__main__":
    main()