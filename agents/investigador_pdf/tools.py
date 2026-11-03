import os
import requests
from network.ayni_search import AyniSearchEcosystem

WORKSPACE_DIR = os.path.join(os.path.dirname(__file__), 'workspace')

def buscar_documentos(tema: str) -> str:
    """Busca enlaces a múltiples PDFs en internet sobre el tema especificado utilizando la red de motores Ayni."""
    try:
        # Instanciamos el ecosistema Ayni Search. 
        # (El agente debería recibir el db_manager para caché, aquí pasamos None por simplicidad estática).
        search_engine = AyniSearchEcosystem(db_manager=None)
        
        # Forzamos la búsqueda de PDFs en la query
        query = f"{tema} filetype:pdf"
        
        # El ecosistema iterará automáticamente por EXA -> TAVILY -> SERPER -> DDGS
        resultados = search_engine.execute_search(query)
        
        # Instrucción adicional para que el LLM del agente seleccione el mejor de la lista devuelta
        if resultados and "Error crítico" not in resultados:
            return f"RESULTADOS DE RED AYNI PARA '{tema}':\n{resultados}\n\n[INSTRUCCIÓN INTERNA]: El orquestador de búsqueda ha devuelto múltiples resultados. Analiza los títulos y URLs provistos, selecciona ÚNICAMENTE los que sean verdaderos PDFs o los más relevantes para la investigación, y procede a descargarlos."
        else:
            return "No se encontraron PDFs relevantes en ningún motor de la red Ayni."
            
    except Exception as e:
        return f"Error crítico en la capa de búsqueda Ayni: {str(e)}"

def descargar_pdf(url: str, nombre_archivo: str) -> str:
    """Descarga un PDF desde una URL y lo guarda en el workspace del agente."""
    if not nombre_archivo.endswith('.pdf'):
        nombre_archivo += '.pdf'
        
    ruta_destino = os.path.join(WORKSPACE_DIR, nombre_archivo)
    
    try:
        response = requests.get(url, stream=True, timeout=15)
        response.raise_for_status()
        
        if 'application/pdf' not in response.headers.get('Content-Type', ''):
            return f"Error: La URL no apunta a un archivo PDF válido. Content-Type: {response.headers.get('Content-Type')}"
            
        with open(ruta_destino, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        ruta_absoluta = os.path.abspath(ruta_destino)
        return f"Éxito: PDF descargado correctamente.\nRuta del archivo guardado: {ruta_absoluta}"
    except Exception as e:
        return f"Error al descargar el PDF: {str(e)}"
