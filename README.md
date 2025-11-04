# 📊 Daily Operacional — Dashboard de Performance

Aplicação **Streamlit** interativa para monitoramento diário de indicadores operacionais regionais.  
Permite acompanhar resultados acumulados, metas, penalidades e tendências de desempenho em tempo real.

---

## 🚀 **Funcionalidades**

- 📅 Filtro dinâmico de datas (com limites automáticos)
- 🧭 Filtro por núcleo, setor e tipo de penalidade
- 🔴 Indicadores com cores automáticas (verde, amarelo, vermelho e branco)
- 🧮 Cálculo automático de médias e metas
- 📈 Tabelas interativas com `AgGrid` (ordenar, filtrar, exportar)
- ⚙️ Conexão com base de dados SQL Server via `pyodbc`
- 🗂️ Integração com planilhas Excel (`openpyxl`)

---

## 🧩 **Tecnologias Utilizadas**

| Biblioteca | Função principal |
|-------------|------------------|
| `streamlit` | Interface web interativa |
| `pandas` | Manipulação e análise de dados |
| `st-aggrid` | Tabelas interativas e dinâmicas |
| `pyodbc` | Conexão com bancos de dados SQL Server |
| `openpyxl` | Leitura e escrita de arquivos Excel |
| `unidecode` | Normalização de textos |
| `rapidfuzz` | Comparação de similaridade de strings |

---

## ⚙️ **Como executar localmente**

1️⃣ Instale as dependências:
```bash
pip install -r requirements.txt
