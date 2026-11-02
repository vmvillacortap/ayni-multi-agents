import tkinter as tk
from tkinter import ttk
import requests
import threading

class FallbackSelectorPopup:
    def __init__(self, ollama_url, manus_models):
        self.ollama_url = ollama_url.replace("/generate", "").replace("/tags", "")
        if not self.ollama_url.endswith("/api"):
            self.ollama_url = "http://localhost:11434/api"
        
        self.manus_models = manus_models
        self.selected_provider = None
        self.selected_model = None
        
        self.root = tk.Tk()
        self.root.title("Ayni - Centro de Contingencia Multi-Agente")
        
        w, h = 650, 420
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = ws - w - 20
        y = hs - h - 60
        self.root.geometry(f'{w}x{h}+{x}+{y}')
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#f4f4f9")
        
        style = ttk.Style()
        style.theme_use("clam")
        
        lbl_title = tk.Label(self.root, text="⚠️ API de Gemini Falló - Seleccione Motor de Respaldo", font=("Segoe UI", 12, "bold"), bg="#f4f4f9", fg="#d9534f")
        lbl_title.pack(pady=10)
        
        rec_text = "NUBE (Manus AI): Procesamiento remoto de alta capacidad.\nLOCAL (Ollama): Requiere hardware (32GB RAM / 8GB VRAM). Usa 'llava' para multimodal."
        lbl_rec = tk.Label(self.root, text=rec_text, font=("Segoe UI", 9, "italic"), bg="#e8f4f8", fg="#025aa5", justify=tk.CENTER, relief=tk.GROOVE, padx=10, pady=5)
        lbl_rec.pack(fill=tk.X, padx=20, pady=5)
        
        columns = ("proveedor", "modelo", "estado")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=8)
        self.tree.heading("proveedor", text="Entorno / Proveedor")
        self.tree.heading("modelo", text="Modelo")
        self.tree.heading("estado", text="Estado de Memoria/Red")
        
        self.tree.column("proveedor", width=160, anchor=tk.CENTER)
        self.tree.column("modelo", width=180)
        self.tree.column("estado", width=160, anchor=tk.CENTER)
        self.tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        self.tree.tag_configure('cloud', background='#e6f2ff')
        self.tree.tag_configure('local', background='#e6ffe6')
        
        self.status_var = tk.StringVar()
        self.status_var.set("Consultando motores disponibles...")
        lbl_status = tk.Label(self.root, textvariable=self.status_var, font=("Segoe UI", 9), bg="#f4f4f9", fg="#555555")
        lbl_status.pack(pady=5)
        
        btn_frame = tk.Frame(self.root, bg="#f4f4f9")
        btn_frame.pack(pady=10)
        
        self.btn_select = tk.Button(btn_frame, text="🚀 Iniciar Contingencia", font=("Segoe UI", 10, "bold"), bg="#5cb85c", fg="white", command=self.on_select, state=tk.DISABLED)
        self.btn_select.pack(side=tk.LEFT, padx=10)
        
        self.btn_cancel = tk.Button(btn_frame, text="Cancelar", font=("Segoe UI", 10), bg="#d9534f", fg="white", command=self.root.destroy)
        self.btn_cancel.pack(side=tk.LEFT, padx=10)
        
        self.root.after(100, self.load_data)

    def load_data(self):
        if self.manus_models:
            for m in self.manus_models:
                self.tree.insert("", tk.END, values=("☁️ Manus AI (Nube)", m, "🟢 API Disponible"), tags=('cloud',))
        try:
            installed = requests.get(f"{self.ollama_url}/tags", timeout=2).json().get('models', [])
            loaded = requests.get(f"{self.ollama_url}/ps", timeout=2).json().get('models', [])
            installed_names = [m['name'] for m in installed]
            loaded_names = [m['name'] for m in loaded]
            for name in installed_names:
                estado = "🟢 Cargado (En VRAM)" if name in loaded_names else "⚪ Descargado"
                self.tree.insert("", tk.END, values=("🖥️ Ollama (Local)", name, estado), tags=('local',))
        except Exception:
            pass
            
        self.status_var.set("Seleccione un modelo para continuar la ejecución.")
        self.btn_select.config(state=tk.NORMAL)

    def on_select(self):
        selected_item = self.tree.focus()
        if not selected_item:
            self.status_var.set("⚠️ Por favor, seleccione un modelo de la lista.")
            return
        
        proveedor, model_name, estado = self.tree.item(selected_item, 'values')
        self.btn_select.config(state=tk.DISABLED)
        provider_id = "Manus" if "Manus" in proveedor else "Ollama"
        
        if provider_id == "Manus":
            self.status_var.set(f"☁️ Conectando a {model_name} en Manus AI...")
            self.root.update()
            self.selected_provider = provider_id
            self.selected_model = model_name
            self.root.after(500, self.root.destroy)
        else:
            if "Cargado" in estado:
                self.status_var.set(f"🖥️ Modelo local {model_name} listo. Conectando...")
                self.root.update()
                self.selected_provider = provider_id
                self.selected_model = model_name
                self.root.after(500, self.root.destroy)
            else:
                self.status_var.set(f"⚙️ Liberando memoria y cargando {model_name}... (Espere)")
                self.root.update()
                threading.Thread(target=self.process_loading, args=(model_name,), daemon=True).start()
            
    def process_loading(self, model_name):
        try:
            loaded = requests.get(f"{self.ollama_url}/ps", timeout=2).json().get('models', [])
            for m in loaded:
                if m['name'] != model_name:
                    self.root.after(0, lambda n=m['name']: self.status_var.set(f"🧹 Descargando {n} de la VRAM..."))
                    requests.post(f"{self.ollama_url}/generate", json={"model": m['name'], "keep_alive": 0}, timeout=10)
            
            self.root.after(0, lambda: self.status_var.set(f"⏳ Transfiriendo {model_name} a la GPU..."))
            requests.post(f"{self.ollama_url}/generate", json={"model": model_name, "keep_alive": "5m"}, timeout=120)
            
            self.selected_provider = "Ollama"
            self.selected_model = model_name
            self.root.after(0, self.root.destroy)
        except Exception as e:
            def update_err():
                self.status_var.set(f"❌ Error de carga local: {str(e)}")
                self.btn_select.config(state=tk.NORMAL)
            self.root.after(0, update_err)

def show_model_selector(ollama_url, manus_models):
    app = FallbackSelectorPopup(ollama_url, manus_models)
    app.root.mainloop()
    return app.selected_provider, app.selected_model
