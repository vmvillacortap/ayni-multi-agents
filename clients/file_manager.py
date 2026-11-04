import os
import re
import tkinter as tk
from tkinter import ttk
import base64
import time
from datetime import datetime

def guardar_documento(contenido_texto: str, nombre_archivo: str, subcarpeta: str = ""):
    """Útil para guardar código, análisis o textos generados en un archivo físico.
    REGLA PARA SUBCARPETA:
    - Si el archivo analizado ya estaba dentro de una subcarpeta de media/ (ej. media/mi_proyecto/), DEBES usar ese mismo nombre de subcarpeta.
    - ÚNICAMENTE inventa un nuevo nombre temático (ej. 'reportes') si el archivo venía de fuera de media/ o no hubo archivo de entrada.
    Siempre se guardará dentro de media/ y se le agregará la fecha actual automáticamente al archivo."""
    base_dir = "media"
    subcarpeta = subcarpeta.strip("/\\ ")
    target_dir = os.path.join(base_dir, subcarpeta) if subcarpeta else base_dir
    os.makedirs(target_dir, exist_ok=True)
    
    fecha_str = datetime.now().strftime("%Y%m%d")
    if not nombre_archivo.startswith(fecha_str):
        nombre_archivo = f"{fecha_str}_{nombre_archivo}"
        
    path = os.path.join(target_dir, nombre_archivo)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(contenido_texto)
        return f"✅ Archivo guardado exitosamente en la ruta local: {path}"
    except Exception as e:
        return f"❌ Error al guardar el archivo: {str(e)}"

# --- ANÁLISIS DE INTENCIÓN Y FILTRADO ---
def _intent_is_local_read(prompt: str) -> bool:
    """Determina si el usuario realmente quiere leer un archivo local (evita falsos positivos de descargas)."""
    prompt_lower = prompt.lower()
    
    # 1. Filtro Excluyente: Si pide descargar o buscar, NO es lectura local.
    if re.search(r'\b(descarga|descargar|b[úu]sca|buscar|encuentra|trae)\b.*\b(pdf|archivo|documento|web|internet)\b', prompt_lower):
        return False
        
    # 2. Trigger Inclusivo explícito: Si menciona verbos de lectura/análisis
    if re.search(r'\b(lee|leer|analiza|analizar|revisa|revisar|abre|abrir|adjunt[oa]|este)\b.*\b(archivo|pdf|csv|txt|documento|carpeta)\b', prompt_lower):
        return True
        
    # 3. Trigger Inclusivo por extensión directa (ej: "resume reporte.pdf")
    if re.search(r'\b\w+\.(pdf|txt|csv|md|json|py)\b', prompt_lower):
        return True
        
    # 4. Palabras clave generales (como en el original, pero solo si pasamos el filtro excluyente)
    trigger_words = ["archivo", "documento", "imagen", "video", "audio", "pdf", "excel", "word", "csv", "analiza", "lee", ".py", ".md", ".json", ".txt"]
    if any(word in prompt_lower for word in trigger_words):
        return True
        
    return False

def _filter_relevant_files(prompt: str, all_files: list) -> list:
    """Reduce la lista de archivos basándose en el contexto del prompt del usuario."""
    prompt_lower = prompt.lower()
    
    # 1. Si el usuario especificó una carpeta (ej: "en la carpeta reportes")
    folder_match = re.search(r'carpeta\s+([a-zA-Z0-9_-]+)', prompt_lower)
    if folder_match:
        folder_name = folder_match.group(1)
        filtered = [f for f in all_files if f"/{folder_name}/" in f.lower() or f"\\{folder_name}\\" in f.lower()]
        if filtered: return filtered # Si encontró la carpeta, restringe solo a eso
        
    # 2. Extraer palabras clave útiles del prompt (ignorando preposiciones)
    stopwords = {'para', 'como', 'sobre', 'este', 'esta', 'del', 'los', 'las', 'con', 'una', 'uno', 'que', 'quiero', 'necesito'}
    words = [w for w in re.findall(r'\b\w+\b', prompt_lower) if len(w) > 3 and w not in stopwords]
    
    if not words: return all_files # Si no hay pistas, muestra todo
    
    # 3. Coincidencia Parcial (Fuzzy): Busca nombres de archivo que contengan alguna palabra clave
    relevant_files = set()
    for f in all_files:
        fname = os.path.basename(f).lower()
        for w in words:
            if w in fname:
                relevant_files.add(f)
                
    # Si la coincidencia funciona, devuelve la lista corta. Si fue muy estricta y dio vacío, devuelve todo por seguridad.
    return list(relevant_files) if relevant_files else all_files

class FileValidatorUI:
    def __init__(self, found_files, prompt=""):
        self.found_files = found_files
        self.selected_files = []
        
        self.root = tk.Tk()
        self.root.title("Ayni - Escáner de Archivos")
        
        w, h = 600, 400
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = ws - w - 20
        y = hs - h - 60
        self.root.geometry(f'{w}x{h}+{x}+{y}')
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#f4f4f9")
        
        lbl_title = tk.Label(self.root, text=f"📂 {len(found_files)} Archivos Contextuales Detectados", font=("Segoe UI", 12, "bold"), bg="#f4f4f9", fg="#333")
        lbl_title.pack(pady=10)
        
        lbl_sub = tk.Label(self.root, text="Selecciona qué archivos adjuntar a la petición:", bg="#f4f4f9")
        lbl_sub.pack()
        
        frame = tk.Frame(self.root, bg="white", bd=2, relief=tk.SUNKEN)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        canvas = tk.Canvas(frame, bg="white")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="white")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.check_vars = {}
        for fpath in self.found_files:
            filename = os.path.basename(fpath)
            # Marcar automáticamente si el nombre del archivo se menciona explicitamente en el prompt
            is_mentioned = filename.lower() in prompt.lower()
            var = tk.BooleanVar(value=is_mentioned)
            self.check_vars[fpath] = var
            
            fg_color = "#005a9e" if is_mentioned else "#333"
            font_weight = "bold" if is_mentioned else "normal"
            
            chk = tk.Checkbutton(scrollable_frame, text=fpath, variable=var, bg="white", fg=fg_color, font=("Segoe UI", 9, font_weight))
            chk.pack(anchor="w", padx=5, pady=2)
            
        btn_frame = tk.Frame(self.root, bg="#f4f4f9")
        btn_frame.pack(pady=10)
        
        btn_confirm = tk.Button(btn_frame, text="✅ Confirmar y Enviar", font=("Segoe UI", 10, "bold"), bg="#5cb85c", fg="white", command=self.confirm)
        btn_confirm.pack(side=tk.LEFT, padx=10)
        
        btn_cancel = tk.Button(btn_frame, text="Omitir Todos", font=("Segoe UI", 10), bg="#d9534f", fg="white", command=self.root.destroy)
        btn_cancel.pack(side=tk.LEFT, padx=10)

    def confirm(self):
        self.selected_files = [fpath for fpath, var in self.check_vars.items() if var.get()]
        self.root.destroy()

def scan_media_and_select(prompt):
    # 1. EVALUAR INTENCIÓN: Si pide descargar o buscar en web, abortamos el escaneo local.
    if not _intent_is_local_read(prompt):
        return []
        
    all_files = []
    ignore_dirs = {'.git', '__pycache__', 'venv', '.venv', 'env', '.idea', 'node_modules'}
    
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        for file in files:
            if not file.startswith('.') and not file.endswith(('.pyc', '.zip')):
                fpath = os.path.normpath(os.path.join(root, file))
                all_files.append(fpath)
                
    if not all_files:
        return []
        
    # 2. FILTRAR RESULTADOS: Reducir la lista masiva a solo archivos/carpetas relevantes
    filtered_files = _filter_relevant_files(prompt, all_files)
    
    # 3. ORDENAR Y MOSTRAR
    filtered_files.sort()
    print("\033[93m[UI] Solicitud de validación de archivos abierta en ventana emergente...\033[0m")
    app = FileValidatorUI(filtered_files, prompt)
    app.root.mainloop()
    return app.selected_files

def encode_image_base64(filepath):
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def extract_text_from_doc(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == '.pdf':
            import fitz
            doc = fitz.open(filepath)
            return "\n".join([page.get_text() for page in doc])
        elif ext in ['.docx']:
            import docx
            doc = docx.Document(filepath)
            return "\n".join([p.text for p in doc.paragraphs])
        elif ext in ['.txt', '.md', '.csv', '.json', '.py']:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return f"[Archivo binario {ext} adjuntado. El modelo actual de contingencia no procesa directamente este formato, pero se notificó su existencia.]"
    except Exception as e:
        return f"[Error extrayendo texto de {filepath}: {e}]"
