import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()
SCHEMA_NAME = os.environ.get("PG_SCHEMA", "agentes_ia")

class Interaction(Base):
    __tablename__ = 'interactions'
    __table_args__ = {'schema': SCHEMA_NAME}
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    user_input = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    provider = Column(String(50))
    model_used = Column(String(100))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    response_time_ms = Column(Float)
    skill_used = Column(String(100))
    
    errors = relationship("ErrorLog", back_populates="interaction", cascade="all, delete-orphan")
    history_entries = relationship("ChatHistory", back_populates="interaction", cascade="all, delete-orphan")

class ErrorLog(Base):
    __tablename__ = 'errors'
    __table_args__ = {'schema': SCHEMA_NAME}
    
    id = Column(Integer, primary_key=True)
    interaction_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.interactions.id'))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    error_type = Column(String(100))
    error_message = Column(Text)
    fallback_triggered = Column(Boolean, default=False)

    interaction = relationship("Interaction", back_populates="errors")

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    __table_args__ = {'schema': SCHEMA_NAME}
    
    id = Column(Integer, primary_key=True)
    interaction_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.interactions.id'))
    session_id = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    role = Column(String(20), nullable=False) # 'user' o 'model'
    parts = Column(Text, nullable=False) # Almacenado como JSONB idealmente, pero TEXT con JSON.dumps asegura compatibilidad
    
    interaction = relationship("Interaction", back_populates="history_entries")

class DBManager:
    def __init__(self):
        pg_user = os.environ.get("PG_USER", "postgres")
        pg_pass = os.environ.get("PG_PASSWORD", "Kendal_postgres29")
        pg_host = os.environ.get("PG_HOST", "localhost")
        pg_port = os.environ.get("PG_PORT", "5432")
        pg_db = os.environ.get("PG_DATABASE", "ayni_agents_db")
        
        db_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
        
        try:
            self.engine = create_engine(db_url)
            with self.engine.connect() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
                conn.commit()
                
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
        except Exception as e:
            print(f"\n\033[91m[Base de Datos] Advertencia: No se pudo conectar a PostgreSQL. Verifica que la BD '{pg_db}' exista.\nError: {e}\033[0m")
            self.Session = None

    def log_interaction(self, session_id, user_input, response_text, provider, model_used, input_tokens, output_tokens, response_time_ms, skill_used, error_data=None):
        if not self.Session:
            return None
            
        session = self.Session()
        try:
            interaction = Interaction(
                session_id=session_id,
                user_input=user_input,
                response_text=response_text,
                provider=provider,
                model_used=model_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_time_ms=response_time_ms,
                skill_used=skill_used
            )
            session.add(interaction)
            session.flush()
            interaction_id = interaction.id
            
            if error_data:
                error_log = ErrorLog(
                    interaction_id=interaction_id,
                    error_type=error_data.get('type', 'Unknown'),
                    error_message=error_data.get('message', ''),
                    fallback_triggered=error_data.get('fallback', False)
                )
                session.add(error_log)
                
            session.commit()
            return interaction_id
        except Exception as e:
            print(f"\033[91m[DB Error]: No se pudo guardar la métrica. {e}\033[0m")
            session.rollback()
            return None
        finally:
            session.close()

    def load_history(self, session_id):
        """Recupera el historial de chat para una sesión específica, formateado para Gemini."""
        if not self.Session:
            return []
            
        session = self.Session()
        formatted_history = []
        try:
            entries = session.query(ChatHistory).filter_by(session_id=session_id).order_by(ChatHistory.timestamp).all()
            for entry in entries:
                import json
                try:
                    parts = json.loads(entry.parts)
                except:
                    parts = [entry.parts]
                formatted_history.append({
                    "role": entry.role,
                    "parts": parts
                })
            return formatted_history
        except Exception as e:
            print(f"\033[91m[DB Error]: No se pudo cargar el historial. {e}\033[0m")
            return []
        finally:
            session.close()

    def append_to_history(self, session_id, interaction_id, role, parts):
        """Guarda un único mensaje (user o model) en el historial persistente de PostgreSQL."""
        if not self.Session:
            return
            
        session = self.Session()
        import json
        try:
            history_entry = ChatHistory(
                interaction_id=interaction_id,
                session_id=session_id,
                role=role,
                parts=json.dumps(parts, ensure_ascii=False)
            )
            session.add(history_entry)
            session.commit()
        except Exception as e:
            print(f"\033[91m[DB Error]: No se pudo agregar al historial. {e}\033[0m")
            session.rollback()
        finally:
            session.close()
