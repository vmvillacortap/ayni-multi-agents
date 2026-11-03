import os
import datetime
import json
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
    role = Column(String(20), nullable=False)
    parts = Column(Text, nullable=False)
    
    interaction = relationship("Interaction", back_populates="history_entries")

# --- NUEVA TABLA: CACHING DE BÚSQUEDA ---
class SearchCache(Base):
    __tablename__ = 'search_cache'
    __table_args__ = {'schema': SCHEMA_NAME}
    
    query = Column(String(500), primary_key=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    results = Column(Text, nullable=False)
    provider = Column(String(50), nullable=False)

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
            print(f"\n\033[91m[Base de Datos] Advertencia: No se pudo conectar a PostgreSQL.\nError: {e}\033[0m")
            self.Session = None

    # --- NUEVOS MÉTODOS DE CACHING ---
    def get_cached_search(self, query, max_age_hours=1):
        """Recupera una búsqueda cacheada si no es más antigua que max_age_hours."""
        if not self.Session:
            return None, None
            
        session = self.Session()
        try:
            cache_entry = session.query(SearchCache).filter_by(query=query).first()
            if cache_entry:
                age = datetime.datetime.utcnow() - cache_entry.timestamp
                if age.total_seconds() <= (max_age_hours * 3600):
                    return cache_entry.results, cache_entry.provider
                else:
                    # Auto-limpieza en lectura
                    session.delete(cache_entry)
                    session.commit()
            return None, None
        except Exception:
            return None, None
        finally:
            session.close()

    def set_cached_search(self, query, results, provider):
        """Guarda o actualiza el resultado de una búsqueda en la caché de PostgreSQL."""
        if not self.Session:
            return
            
        session = self.Session()
        try:
            # Upsert básico (funciona universalmente en SQLAlchemy)
            cache_entry = session.query(SearchCache).filter_by(query=query).first()
            if cache_entry:
                cache_entry.results = results
                cache_entry.provider = provider
                cache_entry.timestamp = datetime.datetime.utcnow()
            else:
                cache_entry = SearchCache(query=query, results=results, provider=provider)
                session.add(cache_entry)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    # --- MÉTODOS ORIGINALES MANTENIDOS INTACTOS ---
    def log_interaction(self, session_id, user_input, response_text, provider, model_used, input_tokens, output_tokens, response_time_ms, skill_used, error_data=None):
        if not self.Session:
            return None
            
        session = self.Session()
        try:
            interaction = Interaction(
                session_id=session_id, user_input=user_input, response_text=response_text,
                provider=provider, model_used=model_used, input_tokens=input_tokens,
                output_tokens=output_tokens, response_time_ms=response_time_ms, skill_used=skill_used
            )
            session.add(interaction)
            session.flush()
            interaction_id = interaction.id
            
            if error_data:
                error_log = ErrorLog(
                    interaction_id=interaction_id, error_type=error_data.get('type', 'Unknown'),
                    error_message=error_data.get('message', ''), fallback_triggered=error_data.get('fallback', False)
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
        if not self.Session: return []
        session = self.Session()
        formatted_history = []
        try:
            entries = session.query(ChatHistory).filter_by(session_id=session_id).order_by(ChatHistory.timestamp).all()
            for entry in entries:
                try: parts = json.loads(entry.parts)
                except: parts = [entry.parts]
                formatted_history.append({"role": entry.role, "parts": parts})
            return formatted_history
        except Exception:
            return []
        finally:
            session.close()

    def append_to_history(self, session_id, interaction_id, role, parts):
        if not self.Session: return
        session = self.Session()
        try:
            history_entry = ChatHistory(
                interaction_id=interaction_id, session_id=session_id,
                role=role, parts=json.dumps(parts, ensure_ascii=False)
            )
            session.add(history_entry)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
