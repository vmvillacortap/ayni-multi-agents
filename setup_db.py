import os
from dotenv import load_dotenv
from database.db_manager import DBManager, SCHEMA_NAME

def init_database():
    print("=== Inicializador de Base de Datos Ayni ===")
    load_dotenv()
    
    print(f"⚙️ Configurando conexión a PostgreSQL...")
    print(f"Host: {os.environ.get('PG_HOST')} | Puerto: {os.environ.get('PG_PORT')}")
    print(f"Base de datos: {os.environ.get('PG_DATABASE')} | Esquema: {SCHEMA_NAME}")
    
    db = DBManager()
    if db.Session:
        print(f"\n✅ ¡Éxito! El esquema '{SCHEMA_NAME}' y las tablas 'interactions' y 'errors' han sido creadas o verificadas correctamente.")
        print("🚀 Ya puedes ejecutar 'python main.py' para iniciar el sistema Ayni.")
    else:
        print("\n❌ Fallo en la configuración. Asegúrate de que el servicio de PostgreSQL esté corriendo y que hayas creado la base de datos vacía primero.")

if __name__ == "__main__":
    init_database()
