import os
import requests
from duckduckgo_search import DDGS

class AyniSearchEcosystem:
    def __init__(self, db_manager):
        self.db = db_manager
        prioridad_str = os.environ.get("SEARCH_PRIORITY", "exa,tavily,serper,ddgs")
        self.priority_list = [p.strip().lower() for p in prioridad_str.split(",")]

        self.keys = {
            "exa": os.environ.get("EXA_API_KEY"),
            "serper": os.environ.get("SERPER_API_KEY"),
            "tavily": os.environ.get("TAVILY_API_KEY")
        }

    def _search_exa(self, query):
        if not self.keys["exa"]: raise ValueError("Credencial omitida.")
        headers = {"accept": "application/json", "content-type": "application/json", "x-api-key": self.keys["exa"]}
        payload = {"query": query, "useAutoprompt": True, "numResults": 3}
        res = requests.post("https://api.exa.ai/search", json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        results = res.json().get("results", [])
        return "\n".join([f"- {r['title']} ({r.get('url')}): Búsqueda exitosa." for r in results])

    def _search_serper(self, query):
        if not self.keys["serper"]: raise ValueError("Credencial omitida.")
        headers = {"X-API-KEY": self.keys["serper"], "Content-Type": "application/json"}
        payload = {"q": query, "num": 3}
        res = requests.post("https://google.serper.dev/search", json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        results = res.json().get("organic", [])
        return "\n".join([f"- {r.get('title')}: {r.get('snippet')} (URL: {r.get('link')})" for r in results[:3]])

    def _search_tavily(self, query):
        if not self.keys["tavily"]: raise ValueError("Credencial omitida.")
        headers = {"content-type": "application/json"}
        payload = {"api_key": self.keys["tavily"], "query": query, "search_depth": "basic"}
        res = requests.post("https://api.tavily.com/search", json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        results = res.json().get("results", [])
        return "\n".join([f"- {r['title']}: {r['content']} (URL: {r.get('url', 'N/A')})" for r in results[:3]])

    def _search_ddgs(self, query):
        results = DDGS().text(query, max_results=3)
        if not results: raise ValueError("Sin resultados.")
        return "\n".join([f"- {r['title']}: {r['body']} (URL: {r.get('href', 'N/A')})" for r in results])

    def execute_search(self, query):
        print(f"\n\033[96m[Ayni Search] Iniciando consulta para: '{query}'\033[0m")
        
        cached_results, cached_provider = self.db.get_cached_search(query, max_age_hours=1)
        if cached_results:
            print(f"\033[95m[Caché Ayni] Resultados recuperados de PostgreSQL (Originalmente vía {cached_provider.upper()}). ¡Cuota API ahorrada!\033[0m")
            return cached_results

        providers = {
            "exa": self._search_exa,
            "serper": self._search_serper,
            "tavily": self._search_tavily,
            "ddgs": self._search_ddgs
        }

        for provider_name in self.priority_list:
            if provider_name not in providers: continue
            
            # MODIFICADO: Color verde claro ([92m) solo para TAVILY
            if provider_name == 'tavily':
                print(f"\033[92mInvocando proveedor: {provider_name.upper()}...\033[0m", end="\r")
            else:
                print(f"\033[90mInvocando proveedor: {provider_name.upper()}...\033[0m", end="\r")
                
            try:
                resultado = providers[provider_name](query)
                if resultado and resultado.strip():
                    if provider_name == 'tavily':
                        print(f"\033[92m[Equilibrio] El proveedor {provider_name.upper()} completó el trabajo.\033[0m{' ' * 20}")
                    else:
                        print(f"\033[96m[Equilibrio] El proveedor {provider_name.upper()} completó el trabajo.\033[0m{' ' * 20}")
                    self.db.set_cached_search(query, resultado, provider_name)
                    return resultado
            except Exception as e:
                err_msg = str(e).split(":")[-1].strip()[:40]
                if provider_name == 'tavily':
                    print(f"\033[92m[Reciprocidad Ayni] {provider_name.upper()} falló ({err_msg}). Delegando...\033[0m")
                else:
                    print(f"\033[93m[Reciprocidad Ayni] {provider_name.upper()} falló ({err_msg}). Delegando...\033[0m")
                continue
                
        return "Error crítico: Toda la red de proveedores Ayni ha colapsado."
