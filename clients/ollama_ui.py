import tkinter as tk
from tkinter import ttk
import requests
import threading

class OllamaSelectorPopup:
    def __init__(self, api_url):
        self.api_url = api_url.replace("/generate", "").replace("/tags", "")
        if not self.api_url.endswith("/api"):
            self.api_url = "http://localhost:11434/api"
            
        self.selected_model = None
        self.root = tk.Tk()
        self.root.title("NEXO - Fallback a Ollama")
        
        # Dimensiones y posicionamiento inferior derecho
        w, h = 550, 400
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = ws - w - 20
        y = hs - h - 60
        self.root.geometry(f'{w}x{h}+{x}+{y}')
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#f4f4f9")
        
        style = ttk.Style()
        style.theme_use("clam")
        
        # UI Elements
        lbl_title = tk.Label(self.root, text="⚠️ API de Gemini Falló - Intervención Local Requerida", font=("Segoe UI", 12, "bold"), bg="#f4f4f9", fg="#d9534f")
        lbl_title.pack(pady=10)
        
        # Recomendación dinámica
        rec_text = "Recomendación (Tu hardware: 32GB RAM / 8GB VRAM GPU):\nUtiliza modelos de 7B a 13B parámetros.\nPara interacción MULTIMODAL, selecciona 'llava:7b', 'llava:13b' o 'moondream'."
        lbl_rec = tk.Label(self.root, text=rec_text, font=("Segoe UI", 9, "italic"), bg="#e8f4f8", fg="#025aa5", justify=tk.CENTER, relief=tk.GROOVE, padx=10, pady=5)
        lbl_rec.pack(fill=tk.X, padx=20, pady=5)
        
        # Tabla de modelos
        columns = ("modelo", "estado")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=8)
        self.tree.heading("modelo", text="Modelos Instalados")
        self.tree.heading("estado", text="Estado de Memoria")
        self.tree.column("modelo", width=300)
        self.tree.column("estado", width=150, anchor=tk.CENTER)
        self.tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Status
        self.status_var = tk.StringVar()
        self.status_var.set("Consultando instancia local de Ollama...")
        lbl_status = tk.Label(self.root, textvariable=self.status_var, font=("Segoe UI", 9), bg="#f4f4f9", fg="#555555")
        lbl_status.pack(pady=5)
        
        # Botones
        btn_frame = tk.Frame(self.root, bg="#f4f4f9")
        btn_frame.pack(pady=10)
        
        self.btn_select = tk.Button(btn_frame, text="🚀 Seleccionar y Usar Modelo", font=("Segoe UI", 10, "bold"), bg="#5cb85c", fg="white", command=self.on_select, state=tk.DISABLED)
        self.btn_select.pack(side=tk.LEFT, padx=10)
        
        self.btn_cancel = tk.Button(btn_frame, text="Cancelar", font=("Segoe UI", 10), bg="#d9534f", fg="white", command=self.root.destroy)
        self.btn_cancel.pack(side=tk.LEFT, padx=10)
        
        # Iniciar carga de datos
        self.root.after(100, self.load_data)

    def load_data(self):
        try:
            installed = requests.get(f"{self.api_url}/tags", timeout=2).json().get('models', [])
            loaded = requests.get(f"{self.api_url}/ps", timeout=2).json().get('models', [])
            
            installed_names = [m['name'] for m in installed]
            loaded_names = [m['name'] for m in loaded]
            
            for name in installed_names:
                estado = "🟢 Cargado (En Memoria)" if name in loaded_names else "⚪ Descargado"
                self.tree.insert("", tk.END, values=(name, estado))
                
            self.status_var.set("Selecciona un modelo de la lista para continuar.")
            self.btn_select.config(state=tk.NORMAL)
        except Exception as e:
            self.status_var.set("Error: No se pudo conectar a Ollama local.")

    def on_select(self):
        selected_item = self.tree.focus()
        if not selected_item:
            self.status_var.set("⚠️ Por favor, selecciona un modelo de la lista.")
            return
        
        model_name, estado = self.tree.item(selected_item, 'values')
        self.btn_select.config(state=tk.DISABLED)
        
        if "Cargado" in estado:
            self.status_var.set(f"Modelo {model_name} ya está en memoria. Conectando...")
            self.root.update()
            self.selected_model = model_name
            self.root.after(500, self.root.destroy)
        else:
            self.status_var.set(f"⚙️ Liberando memoria y cargando {model_name}... (Por favor espera)")
            self.root.update()
            threading.Thread(target=self.process_loading, args=(model_name,), daemon=True).start()
            
    def process_loading(self, model_name):
        try:
            # 1. Limpiar memoria de otros modelos
            loaded = requests.get(f"{self.api_url}/ps", timeout=2).json().get('models', [])
            for m in loaded:
                if m['name'] != model_name:
                    self.root.after(0, lambda n=m['name']: self.status_var.set(f"🧹 Descargando {n} de la VRAM..."))
                    requests.post(f"{self.api_url}/generate", json={"model": m['name'], "keep_alive": 0}, timeout=10)
            
            # 2. Cargar el nuevo modelo (enviando prompt vacío)
            self.root.after(0, lambda: self.status_var.set(f"⏳ Transfiriendo {model_name} a la GPU..."))
            requests.post(f"{self.api_url}/generate", json={"model": model_name, "keep_alive": "5m"}, timeout=120)
            
            self.selected_model = model_name
            self.root.after(0, self.root.destroy)
        except Exception as e:
            def update_err():
                self.status_var.set(f"❌ Error de carga: {str(e)}")
                self.btn_select.config(state=tk.NORMAL)
            self.root.after(0, update_err)

def show_model_selector(api_url):
    app = OllamaSelectorPopup(api_url)
    app.root.mainloop()
    return app.selected_model
