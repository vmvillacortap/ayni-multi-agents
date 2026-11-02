import os
import tkinter as tk
from tkinter import ttk
import base64
import time

def guardar_documento(contenido_texto: str, nombre_archivo: str, subcarpeta: str = ""):
    """Útil para guardar código, análisis o textos generados en un archivo físico dentro del proyecto.
    Proporciona el contenido y el nombre (ej. reporte.md, analisis.txt, script.py)."""
    base_dir = "media"
    target_dir = os.path.join(base_dir, subcarpeta) if subcarpeta else base_dir
    os.makedirs(target_dir, exist_ok=True)
    
    path = os.path.join(target_dir, nombre_archivo)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(contenido_texto)
        return f"✅ Archivo guardado exitosamente en la ruta: {path}"
    except Exception as e:
        return f"❌ Error al guardar el archivo: {str(e)}"

class FileValidatorUI:
    def __init__(self, found_files):
        self.found_files = found_files
        self.selected_files = []
        
        self.root = tk.Tk()
        self.root.title("Ayni - Validación de Archivos Multimodales")
        
        w, h = 500, 350
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = ws - w - 20
        y = hs - h - 60
        self.root.geometry(f'{w}x{h}+{x}+{y}')
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#f4f4f9")
        
        lbl_title = tk.Label(self.root, text="📂 Archivos detectados en 'media/'", font=("Segoe UI", 12, "bold"), bg="#f4f4f9", fg="#333")
        lbl_title.pack(pady=10)
        
        lbl_sub = tk.Label(self.root, text="Selecciona los archivos que deseas enviar al modelo:", bg="#f4f4f9")
        lbl_sub.pack()
        
        # Frame con Scrollbar para los checkboxes
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
            var = tk.BooleanVar(value=False)
            self.check_vars[fpath] = var
            chk = tk.Checkbutton(scrollable_frame, text=fpath, variable=var, bg="white", font=("Segoe UI", 9))
            chk.pack(anchor="w", padx=5, pady=2)
            
        btn_frame = tk.Frame(self.root, bg="#f4f4f9")
        btn_frame.pack(pady=10)
        
        btn_confirm = tk.Button(btn_frame, text="✅ Confirmar y Enviar", font=("Segoe UI", 10, "bold"), bg="#5cb85c", fg="white", command=self.confirm)
        btn_confirm.pack(side=tk.LEFT, padx=10)
        
        btn_cancel = tk.Button(btn_frame, text="Omitir Archivos", font=("Segoe UI", 10), bg="#d9534f", fg="white", command=self.root.destroy)
        btn_cancel.pack(side=tk.LEFT, padx=10)

    def confirm(self):
        self.selected_files = [fpath for fpath, var in self.check_vars.items() if var.get()]
        self.root.destroy()

def scan_media_and_select(prompt):
    """Escanea la carpeta media si el prompt sugiere el uso de archivos."""
    trigger_words = ["archivo", "documento", "imagen", "video", "audio", "pdf", "excel", "word", "csv", "analiza", "revisa"]
    if not any(word in prompt.lower() for word in trigger_words):
        return []
        
    base_dir = "media"
    os.makedirs(base_dir, exist_ok=True)
    
    all_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            all_files.append(os.path.join(root, file))
            
    if not all_files:
        return []
        
    # Mostrar Pop-up
    print("\033[93m[UI] Solicitud de validación de archivos abierta en ventana emergente...\033[0m")
    app = FileValidatorUI(all_files)
    app.root.mainloop()
    return app.selected_files

# --- Utilidades de Procesamiento ---
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
            return f"[Archivo binario {ext} adjuntado. El modelo actual no soporta lectura directa de este formato, solo Gemini lo procesa nativamente.]"
    except Exception as e:
        return f"[Error extrayendo texto de {filepath}: {e}]"
