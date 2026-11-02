import os
import google.generativeai as genai
from dotenv import load_dotenv

def listar_modelos():
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("Error: No se encontró la API Key.")
        return

    genai.configure(api_key=api_key)
    
    print("Modelos disponibles para chat (generateContent):\n")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
    except Exception as e:
        print(f"Error al conectar con la API: {e}")

if __name__ == "__main__":
    listar_modelos()