import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
import math
import json
import io
import os  # <--- FALTAVA ISSO
from google.oauth2 import service_account  # <--- FALTAVA ISSO
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import re # Adicione no topo do arquivo junto com os outros imports

def limpar_nome_coluna(coluna):
    # Procura por texto dentro de colchetes: [Nome] -> Nome
    match = re.search(r'\[(.*?)\]', str(coluna))
    return match.group(1) if match else str(coluna)

def encontrar_tables(obj):
    # Busca recursiva pela chave 'tables' (igual ao seu encontrarTables em JS)
    if isinstance(obj, dict):
        if 'tables' in obj and isinstance(obj['tables'], list):
            return obj['tables']
        for key, value in obj.items():
            resultado = encontrar_tables(value)
            if resultado: return resultado
    elif isinstance(obj, list):
        for item in obj:
            resultado = encontrar_tables(item)
            if resultado: return resultado
    return None

@st.cache_data(ttl=86400, show_spinner="Consolidando dados do Drive...") # Aumentado para 24h
def carregar_jsons_drive_privado(folder_id):
    env_name = "GOOGLE_APPLICATION_CREDENTIALS_JSON"
    if env_name not in os.environ:
        return pd.DataFrame()

    service_account_info = json.loads(os.environ[env_name])
    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=creds)

    # OTIMIZAÇÃO: Listar arquivos ordenados por data de modificação (os mais recentes primeiro)
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id, name, mimeType)",
        orderBy="modifiedTime desc",
        pageSize=100 # Limite para os 100 arquivos mais recentes para evitar 503
    ).execute()
    
    files = results.get("files", [])
    dfs = []

    for f in files:
        if "json" in f["mimeType"] or f["name"].endswith(".json"):
            try:
                request = service.files().get_media(fileId=f["id"])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

                fh.seek(0)
                data = json.load(fh)
                
                # Use a mesma lógica de busca profunda 'encontrar_tables' que discutimos
                tables = encontrar_tables(data) 
                if not tables: continue

                for table in tables:
                    if "rows" in table:
                        df_temp = pd.DataFrame(table["rows"])
                        # Limpeza de colunas e preenchimento de data conforme seu código
                        dfs.append(df_temp)
            except Exception:
                continue

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

@st.cache_data(ttl=86400, show_spinner="Consolidando dados... Por favor, aguarde.")
def preparar_dataframe_final(folder_id):
    # 1. Carrega os JSONs do Drive (usa o cache da função original)
    df_raw = carregar_jsons_drive_privado(folder_id)
    
    if df_raw.empty:
        return pd.DataFrame()

    # 2. Carrega a planilha de núcleos
    df_n = carregar_nucleos_google()

    # 3. Processamento que antes ficava "solto" e lento
    df_raw["Data"] = pd.to_datetime(df_raw["Data"], errors="coerce")
    
    # 4. Merge
    df_final = df_raw.merge(
        df_n[["Chave", "Nucleo", "Regional", "Setor"]],
        left_on="Chave2", right_on="Chave", how="left"
    )
    
    # 5. Limpeza de colunas e conversão numérica
    if "Chave" in df_final.columns:
        df_final.drop(columns=["Chave"], inplace=True)
        
    df_final["Contagem"] = pd.to_numeric(df_final["Contagem"], errors='coerce').astype(float)
    
    # 6. Mapeamento de Tema (usa o INDICADOR_TEMA_MAP que está no seu código)
    df_final["Tema"] = df_final["Penalidades"].map(INDICADOR_TEMA_MAP).fillna("Outros")
    
    return df_final

# ===============================
# CONFIGURAÇÃO DA PÁGINA
# ===============================
st.set_page_config(
    layout="wide",
    page_title="📊 Daily Operacional",
    initial_sidebar_state="collapsed",
)
hoje = date.today()

# ===============================
# ESTILO FIXO
# ===============================
st.markdown("""
        <style>
        .fixed-header {
            position: fixed;
            top: 0; left: 0; right: 0;
            width: 100%;
            background-color: white;
            z-index: 9999;
            padding: 1rem 2rem 0.5rem 2rem; 
            border-bottom: 2px solid #ddd;
            box-shadow: 0 2px 5px rgbaa(0,0,0,0.05);
        }
        .content { margin-top: 30px; } 
        .block-container {
            padding: 1rem !important;
            max-width: 100% !important;
            margin: 0 auto !important;
        }
        h3 {
            margin-top: 0rem !important;
            margin-bottom: 0rem !important;
        }
        div[data-testid*="stVerticalBlock"] > div:last-child {
            margin-bottom: 0rem !important; 
        }
        div[data-testid*="stVerticalBlock"] > div > div.ag-root-wrapper {
            margin-bottom: 0rem !important;
        }
        hr {
            display: none;
        }
        </style>
    """, unsafe_allow_html=True)

# ===============================
# CABEÇALHO FIXO
# ===============================
st.markdown('<div class="fixed-header">', unsafe_allow_html=True)
st.title("📊 Daily Operacional")
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<div class="content">', unsafe_allow_html=True)


# ===============================
# FUNÇÕES AUXILIARES
# ===============================
def converter_data_robusta(x):
    if pd.isna(x) or x in ["", None]:
        return pd.NaT
    x = str(x).strip().replace("-", "/")
    if ":" not in x:
        x = x + " 00:00:00"
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return pd.to_datetime(x, format=fmt)
        except:
            continue
    return pd.to_datetime(x, dayfirst=True, errors="coerce")


# @st.cache_data(ttl=3600, show_spinner=False)
# def carregar_daily_google(gids, url_base):
#     abas = []
#     for gid in gids:
#         url_csv = f"{url_base}pub?gid={gid}&single=true&output=csv"
#         try:
#             df = pd.read_csv(url_csv, encoding="utf-8")
#             df.columns = df.columns.str.strip()
#             if "Data" in df.columns:
#                 df["Data"] = df["Data"].apply(converter_data_robusta)
#             if "Contagem" in df.columns:
#                 df["Contagem"] = pd.to_numeric(
#                     df["Contagem"].astype(str).str.replace(",", ".", regex=False),
#                     errors="coerce"
#                 )
#             abas.append(df)
#         except Exception as e:
#             st.error(f"Erro ao carregar aba {gid}: {e}")
#     if abas:
#         return pd.concat(abas, ignore_index=True)
#     else:
#         return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_nucleos_google():
    status_placeholder = st.sidebar.empty()
    try:
        sheet_id = "1N2C-g4RSV4nOaPOwqp_u85395p6xv0OiBs-akfxLTfk"
        gid = "0"
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        status_placeholder.info("Carregando dados dos Núcleos...")
        df_nuc = pd.read_csv(url)
        df_nuc.columns = df_nuc.columns.str.strip()
        colunas_necessarias = ['Empresa', 'Setor', 'Nucleo', 'Regional']
        colunas_faltantes = [col for col in colunas_necessarias if col not in df_nuc.columns]
        if colunas_faltantes:
            status_placeholder.error(f"❌ Colunas faltantes na planilha de Núcleos: {colunas_faltantes}")
            return pd.DataFrame()
        df_nuc["Chave"] = df_nuc["Empresa"].astype(str) + df_nuc["Setor"].astype(str)
        status_placeholder.success("✅ Dados dos núcleos carregados!")
        status_placeholder.empty()
        return df_nuc
    except Exception as e:
        status_placeholder.error(f"❌ Erro ao carregar dados dos núcleos: {str(e)}")
        return pd.DataFrame()


def _format_label(dt):
    label = f"Daily - {dt.strftime('%B/%Y')}".replace(
        'January', 'Janeiro').replace('February', 'Fevereiro').replace(
        'March', 'Março').replace('April', 'Abril').replace(
        'May', 'Maio').replace('June', 'Junho').replace(
        'July', 'Julho').replace('August', 'Agosto').replace(
        'September', 'Setembro').replace('October', 'Outubro').replace(
        'November', 'Novembro').replace('December', 'Dezembro')
    return label


def generate_monthly_periods(min_date: date, today: date, max_data_date: date):
    periods = {}
    current_dt = datetime(min_date.year, min_date.month, 1)
    end_loop_dt = datetime(today.year, today.month, 1)
    while current_dt <= end_loop_dt:
        month_start = current_dt.date()
        is_current_month = (current_dt.date().year == today.year and current_dt.date().month == today.month)
        if is_current_month:
            month_end = min(today, max_data_date)
        else:
            month_end = (current_dt + relativedelta(months=1) - timedelta(days=1)).date()
        if month_start <= month_end:
            label = _format_label(current_dt)
            periods[label] = (month_start, month_end)
        current_dt += relativedelta(months=1)
    return periods


PERCENTUAIS_LIST = {"Meta VPML", "VPML", "Pontual%", "ControleEmbarque",
                    "AcadDDS", "AcadFixo", "Identificacao%", "TripulacaoEscalada%", "BaixaConducao%",
                    "MetaRecl%", "MetaAcid%", "VPML%", "Deslocamento%", "MetaTransito%", "%DesviodeEscala"}
INTEIROS_LIST = {"DocsPendentes", "DocsVencidBloq", "Reclamacoes", "Acidentes"}
DECIMAIS_LIST = {"NotaConducao", "EventosExcessos", "BaixaConducao", "Excessos Não Identificados"}
MOEDA_LIST = {"MultasRegulatorias", "Multas Transito"}
# Lista de indicadores onde "MENOR é MELHOR" (Exceder a meta é ruim/vermelho)
LOWER_IS_BETTER_LIST = {"BaixaConducao%", "MultasRegulatorias", "DocsPendentes", "DocsVencidBloq",
                        "Reclamacoes", "Acidentes", "VPML", "EventosExcessos", "Excessos Não Identificados", "Multas Transito", "%DesviodeEscala"}


def calcular_acum_ultimo_dia(df, penalidade):
    cols_datas = [c for c in df.columns if c not in ["Regional", "Nucleo", "Setor", "Meta", "Acum"]]
    if cols_datas:
        ultimo_col = cols_datas[-1]
        df["Acum"] = df[ultimo_col]
    else:
        df["Acum"] = pd.NA
    cols = df.columns.tolist()
    if "Acum" in cols:
        cols.remove("Acum")
        insert_pos = 3 if len(cols) >= 3 else len(cols)
        cols.insert(insert_pos, "Acum")
        df = df[cols]
    return df


def _to_float_or_none(x):
    try:
        if isinstance(x, str):
            x = x.replace("%", "").replace(",", ".")
        return float(x)
    except:
        return None


def get_dot_color(penalidade, acum, meta):
    def _to_float_or_none_local(x):
        try:
            val = float(x)
            if math.isnan(val): return None
            return val
        except (TypeError, ValueError):
            return None

    acum_val = _to_float_or_none_local(acum)
    meta_val = _to_float_or_none_local(meta)

    if meta_val is None: return "⚫"
    if acum_val is not None and meta_val == 0 and acum_val == 0: return "🟢"
    if acum_val is None: return "⚪"

    if penalidade in LOWER_IS_BETTER_LIST:
        if acum_val < meta_val:
            return "🟢"
        elif acum_val == meta_val:
            return "🟡"
        else:
            return "🔴"
    else:
        if acum_val > meta_val:
            return "🟢"
        elif acum_val == meta_val:
            return "🟡"
        else:
            return "🔴"


nome_indicador = {
    "DocsVencidBloq": "Documento Vencidos/Bloqueados",
    "DocsPendentes": "Documento Pendentes",
    "ControleEmbarque": "Controle de Embarque",
    "VPML": "Veículo Parado com o Motor Ligado",
    "NotaConducao": "Nota Condução",
    "BaixaConducao%": "% Baixa Condução",
    "AcadDDS": "DDS",
    "AcadFixo": "Cursos Fixos",
    "EventosExcessos": "Excessos de Velocidade",
    "Pontual%": "Pontualidade",
    "MultasRegulatorias": "Multas Regulatórias",
    "TripulacaoEscalada%": "Escala de Tripulantes - OPTZ",
    "Identificacao%": "Identificação de Condutor",
    "Reclamacoes": "Reclamações",
    "Acidentes": "Sinistros",
    "PendIdentificacao": "Pendência de Identificacao",
    "Multas Transito": "Multas de Trânsito",
    "Excessos Não Identificados": "Excessos Não Identificados",
    "Deslocamento%": "Deslocamento Identificado",
    "%DesviodeEscala": "Desvio de Escala Programada",
}

INDICADOR_TEMA_MAP = {
    "DocsVencidBloq": "Documentação",
    "DocsPendentes": "Documentação",
    "PenalDocsVencidBloq": "Documentação",
    "PenalDocsPendentes": "Documentação",
    "PenalDocs": "Documentação",
    "ControleEmbarque": "Controle de Embarque",
    "PenalControleEmbarque": "Controle de Embarque",
    "VPML": "Veículo Parado com o Motor Ligado",
    "PenalVPML": "Veículo Parado com o Motor Ligado",
    "Meta VPML": "Veículo Parado com o Motor Ligado",
    "VPML%": "Veículo Parado com o Motor Ligado",
    "NotaConducao": "Histórico de Condução",
    "PenalConducao": "Histórico de Condução",
    "PenalNotaConducao": "Histórico de Condução",
    "PenalBaixaConducao": "Histórico de Condução",
    "BaixaConducao": "Histórico de Condução",
    "BaixaConducao%": "Histórico de Condução",
    "PenalAcadDDS": "Treinamentos EAD",
    "AcadDDS": "Treinamentos EAD",
    "PenalAcadFixo": "Treinamentos EAD",
    "AcadFixo": "Treinamentos EAD",
    "PenalAcademia": "Treinamentos EAD",
    "EventosExcessos": "Excessos de Velocidade",
    "PenalExcessos": "Excessos de Velocidade",
    "PenalPontualidade": "Pontualidade",
    "Pontual%": "Pontualidade",
    "MetaReg%": "Multas Regulatórias",
    "MultasRegulatorias": "Multas Regulatórias",
    "MetaMultasReg": "Multas Regulatórias",
    "PenalMultasReg": "Multas Regulatórias",
    "PenalTripulacao": "Escala de Tripulantes - OPTZ",
    "TripulacaoEscalada%": "Escala de Tripulantes - OPTZ",
    "PenalIdentificacao": "Identificação de Condutor",
    "PenalIdentCondutor": "Identificação de Condutor",
    "Identificacao%": "Identificação de Condutor",
    "PendIdentificacao": "Identificação de Condutor",
    "Reclamacoes": "Reclamações",
    "MetaReclamacoes": "Reclamações",
    "MetaRecl%": "Reclamações",
    "PenalReclamacoes": "Reclamações",
    "Acidentes": "Sinistros",
    "PenalAcidentes": "Sinistros",
    "MetaAcidentes": "Sinistros",
    "MetaAcid%": "Sinistros",
    "MotsAtivos": "Geral",
    "KmRodado": "Geral",
    "ViagensProg": "Geral",
    "Vendas": "Geral",
    "Multas Transito": "Multas de Trânsito",
    "PenalMultastransito": "Multas de Trânsito",
    "MetaTransito%": "Multas de Trânsito",
    "Meta_MultasTransito": "Multas de Trânsito",
    "Excessos Não Identificados": "Excessos de Velocidade",
    "PenalExcessosNãoIdentificados": "Excessos de Velocidade",
    "Deslocamento%": "Identificação de Condutor",
    "PenalDeslocamento": "Identificação de Condutor",
    "%DesviodeEscala": "Escala de Tripulantes - OPTZ",
    "PenalDesviodeEscala": "Escala de Tripulantes - OPTZ",
}

# =======================================================
# NOVO DICIONÁRIO DE ÍCONES POR TEMA
# =======================================================
TEMA_ICONE_MAP = {
    "Documentação": "📄",
    "Controle de Embarque": "🚦",
    "Veículo Parado com o Motor Ligado": "⛽",
    "Histórico de Condução": "🚌",
    "Treinamentos EAD": "🎓",
    "Excessos de Velocidade": "🚨",
    "Pontualidade": "⏱️",
    "Multas Regulatórias": "⚠️💵",
    "Multas de Trânsito": "🚦🧾🚗",
    "Escala de Tripulantes - OPTZ": "👥",
    "Identificação de Condutor": "👤",
    "Reclamações": "🗣️",
    "Sinistros": "💥",
    "Geral": "⚙️",
    "Outros": "❓",
}

# ===============================
# CARREGAR DADOS (CENTRALIZADO COM CACHE)
# ===============================
ID_PASTA_DRIVE = "1kQ0Hs1A_6JKUOXleBScT1C1ehpWM5_Vp"

# Agora chamamos a função unificada
df_merged = preparar_dataframe_final(ID_PASTA_DRIVE)

if df_merged.empty:
    st.error("Erro: Nenhum dado disponível ou falha na conexão com o Drive.")
    st.stop()
# ===============================
# FILTROS
# ===============================
penalidades_ocultas = {
    "Meta VPML", "MetaReclamacoes", "MetaAcidentes", "MetaMultasReg",
    "MetaAcid%", "VPML%", "MetaReg%", "MetaRecl%", "ViagensProg",
    "MotsAtivos", "KmRodado", "Vendas", "BaixaConducao", "MetaTransito%", "Meta_MultasTransito"
}
df_exib = df_merged[~df_merged["Penalidades"].str.startswith("Penal", na=False)]
df_exib = df_exib[~df_exib["Penalidades"].isin(penalidades_ocultas)]
df_exib["Setor"] = df_exib["Setor"].fillna("-")

with st.sidebar:
    st.header("🔍 Filtros")
    if df_exib.empty:
        st.warning("Nenhum dado disponível para filtros.")
        st.stop()

    temas_visiveis = sorted(df_exib["Tema"].dropna().unique())
    # Adicione o parâmetro placeholder em cada multiselect
    tema_sel = st.multiselect(
        "Tema",
        temas_visiveis,
        key="tema_sel_key",
        placeholder="Selecione uma opção"
    )

    penalidades_visiveis = sorted(df_exib["Penalidades"].dropna().unique())
    penalidades_sel = st.multiselect(
        "Penalidades",
        penalidades_visiveis,
        key="penalidades_sel_key",
        placeholder="Selecione uma opção"
    )

    regional_sel = st.multiselect(
        "Regional",
        sorted(df_exib["Regional"].dropna().unique()),
        key="regional_sel_key",
        placeholder="Selecione uma opção"
    )

    nucleo_sel = st.multiselect(
        "Núcleo",
        sorted(df_exib["Nucleo"].dropna().unique()),
        key="nucleo_sel_key",
        placeholder="Selecione uma opção"
    )

    setor_sel = st.multiselect(
        "Setor",
        sorted(df_exib["Setor"].dropna().unique()),
        key="setor_sel_key",
        placeholder="Selecione uma opção"
    )
    try:
        min_data_dt = df_exib["Data"].min().to_pydatetime()
        min_period_date = min_data_dt.date()
        max_data_date = df_exib["Data"].max().to_pydatetime().date()
        period_map = generate_monthly_periods(min_period_date, hoje, max_data_date)
        if not period_map:
            st.warning("⚠️ Não foi possível gerar os períodos mensais.")
            st.stop()
        period_labels = list(period_map.keys())
        default_index = len(period_labels) - 1
        periodo_sel = st.selectbox("Selecione o Período", options=period_labels, index=default_index,
                                   key="periodo_sel_key")
        start_date, end_date = period_map[periodo_sel]
        st.caption(f"De: **{start_date.strftime('%d/%m/%Y')}** a **{end_date.strftime('%d/%m/%Y')}**")
    except Exception as e:
        st.error(f"Erro ao processar datas: {e}")
        start_date, end_date = date(1900, 1, 1), date(1900, 1, 1)

try:
    # Convertemos para string para garantir estabilidade do hash
    filter_tuple = (
        str(tema_sel), str(penalidades_sel), str(regional_sel), str(nucleo_sel), str(setor_sel), str(periodo_sel))
    filter_hash = hash(filter_tuple)
except:
    filter_hash = "static_hash_fallback"  # Valor fixo para não quebrar a renderização

df_filt = df_exib.copy()
if tema_sel: df_filt = df_filt[df_filt["Tema"].isin(tema_sel)]
if penalidades_sel: df_filt = df_filt[df_filt["Penalidades"].isin(penalidades_sel)]
if nucleo_sel: df_filt = df_filt[df_filt["Nucleo"].isin(nucleo_sel)]
if regional_sel: df_filt = df_filt[df_filt["Regional"].isin(regional_sel)]
if setor_sel: df_filt = df_filt[df_filt["Setor"].isin(setor_sel)]
df_filt = df_filt[(df_filt["Data"].dt.date >= start_date) & (df_filt["Data"].dt.date <= end_date)]

if df_filt.empty or df_filt["Penalidades"].dropna().empty:
    st.warning("⚠️ Nenhum dado encontrado para os filtros e período selecionados.")
    st.stop()

# ===============================
# METAS DINÂMICAS
# ===============================
metas_dinamicas = {
    "VPML": "Meta VPML", "Reclamacoes": "MetaReclamacoes",
    "Acidentes": "MetaAcidentes", "MultasRegulatorias": "MetaMultasReg", "Multas Transito": "Meta_MultasTransito"
}
metas_por_setor = {}
for pen, nome_meta in metas_dinamicas.items():
    df_meta = df_merged[df_merged["Penalidades"] == nome_meta].copy()
    nucleos_visiveis = df_exib["Nucleo"].unique().tolist()
    setores_visiveis = df_exib["Setor"].unique().tolist()
    df_meta = df_meta[df_meta["Nucleo"].isin(nucleos_visiveis) & df_meta["Setor"].isin(setores_visiveis)]
    df_meta["Data"] = pd.to_datetime(df_meta["Data"], errors="coerce")
    df_meta = df_meta[(df_meta["Data"].dt.date >= start_date) & (df_meta["Data"].dt.date <= end_date)]
    if df_meta.empty: continue

    if pen == "VPML":
        df_meta_agg = df_meta.groupby(["Nucleo", "Setor", "Data"], as_index=False)["Contagem"].mean()
    else:
        df_meta_agg = df_meta.groupby(["Nucleo", "Setor", "Data"], as_index=False)["Contagem"].sum()

    ultima_data_periodo = df_meta_agg["Data"].max()
    df_meta_ult = df_meta_agg[df_meta_agg["Data"] == ultima_data_periodo]
    df_meta_ult["Chave_Setor"] = df_meta_ult["Nucleo"].astype(str) + "_" + df_meta_ult["Setor"].astype(str)
    metas_por_setor[pen] = df_meta_ult.set_index("Chave_Setor")["Contagem"].to_dict()

penalidades_media = {
    "Meta VPML", "VPML", "VPML%", "MetaAcid%", "MetaRecl%", "MetaReg%",
    "Pontual%", "ControleEmbarque", "AcadDDS", "AcadFixo", "Identificacao%",
    "TripulacaoEscalada%", "BaixaConducao%", "NotaConducao", "BaixaConducao", "EventosExcessos", "Excessos Não Identificados", "Deslocamento%", "%DesviodeEscala"
}

# =======================================================
# ORDEM FIXA DOS INDICADORES
# =======================================================

# 1. Definir uma lista mestra de indicadores a serem exibidos com ordem estável
penalidades_candidatas = [
    p for p in INDICADOR_TEMA_MAP.keys()
    if not p.startswith("Penal") and p not in penalidades_ocultas
]
# Ordena por nome de exibição para uma ordem estável
penalidades_ordem_fixa = sorted(penalidades_candidatas, key=lambda p: nome_indicador.get(p, p))

# 2. Identificar quais indicadores da lista fixa estão presentes no DF filtrado
penalidades_no_df_filtrado = set(df_filt["Penalidades"].dropna().unique())
penalidades_para_exibir = [
    p for p in penalidades_ordem_fixa if p in penalidades_no_df_filtrado
]

# =======================================================
# LOOP PRINCIPAL (TABELAS) - AGRUPADO POR TEMA E COM ÍCONES
# =======================================================

# 1. Agrupar as penalidades por Tema, mantendo a ordem fixa.
indicadores_por_tema = {}
for pen in penalidades_para_exibir:
    tema = INDICADOR_TEMA_MAP.get(pen, "Outros")
    if tema not in indicadores_por_tema:
        indicadores_por_tema[tema] = []
    indicadores_por_tema[tema].append(pen)

# 2. Definir a ordem dos Temas
temas_a_exibir = [INDICADOR_TEMA_MAP.get(p, "Outros") for p in penalidades_para_exibir]
ordem_temas_fixa = sorted(list(set(temas_a_exibir)))

# 3. Iterar sobre os Temas e seus Indicadores
for tema in ordem_temas_fixa:
    indicadores_do_tema = indicadores_por_tema.get(tema, [])
    if not indicadores_do_tema:
        continue

    # Busca o ícone correspondente ao tema
    icone_tema = TEMA_ICONE_MAP.get(tema, "❓")

    # =======================================================
    # <<< MUDANÇA AQUI: Deixar o expander do TEMA aberto >>>
    # =======================================================
    # Cria um expander principal para o TEMA.
    with st.expander(f"## {icone_tema} **{tema}**", expanded=False):  # <-- MUDANÇA AQUI

        # Loop para CADA INDICADOR
        for i, pen in enumerate(indicadores_do_tema):

            # --- A LÓGICA DE PREPARAÇÃO DE DADOS COMEÇA AQUI ---
            # (Exatamente como estava no seu código original)

            sub = df_filt[df_filt["Penalidades"] == pen].copy()
            if sub.empty: continue

            aggfunc = "mean" if pen in penalidades_media else "sum"
            try:
                pivot = sub.pivot_table(
                    index=["Regional", "Nucleo", "Setor"],
                    columns="Data", values="Contagem", aggfunc=aggfunc, fill_value=pd.NA
                ).sort_index(axis=1)
                if "Data" in pivot.columns: pivot = pivot.drop(columns=["Data"])
                pivot.columns = [col.strftime("%d/%m") for col in pivot.columns]
                df_data_raw = pivot.reset_index()
                if "Data" in df_data_raw.columns: df_data_raw = df_data_raw.drop(columns=["Data"])
                colunas_duplicadas = [c for c in df_data_raw.columns if c.lower().strip() == "data"]
                if colunas_duplicadas: df_data_raw = df_data_raw.drop(columns=colunas_duplicadas)
                df_data_raw = df_data_raw.loc[:, ~df_data_raw.columns.duplicated()]
                df_data_raw = df_data_raw[
                    [c for c in df_data_raw.columns if not ("00:00" in str(c) or "Data" in str(c))]]
            except Exception as e:
                st.error(f"Erro pivot {pen}: {e}")
                continue

            cols_data_in_pivot = [c for c in df_data_raw.columns if c not in ["Regional", "Nucleo", "Setor"]]
            for c in cols_data_in_pivot: df_data_raw[c] = pd.to_numeric(df_data_raw[c], errors='coerce')

            if pen in penalidades_media:
                cols_to_fill_mean = [c for c in cols_data_in_pivot if c not in ["Meta", "Acum"]]
                for c in cols_to_fill_mean: df_data_raw[c] = df_data_raw[c].mask(pd.isna(df_data_raw[c]), None)
            else:
                cols_to_fill = [c for c in df_data_raw.columns if c not in ["Regional", "Nucleo", "Setor"]]
                for c in cols_to_fill: df_data_raw[c] = df_data_raw[c].fillna(0.0)

            df_data_raw = calcular_acum_ultimo_dia(df_data_raw, pen)
            df_data_raw["Chave_Setor"] = df_data_raw["Nucleo"].astype(str) + "_" + df_data_raw["Setor"].astype(str)

            if pen in metas_por_setor:
                df_data_raw["Meta"] = df_data_raw["Chave_Setor"].map(metas_por_setor.get(pen, {})).fillna(pd.NA)
            else:
                metas_fixas = {
                    "Pontual%": 0.8, "ControleEmbarque": 0.95, "AcadDDS": 0.98, "AcadFixo": 0.9,
                    "BaixaConducao%": 0.1, "DocsPendentes": 0, "DocsVencidBloq": 0,
                    "EventosExcessos": 0.02, "Identificacao%": 0.98, "TripulacaoEscalada%": 0.96,
                    "NotaConducao": 70.0, "Deslocamento%": 0.90, "%DesviodeEscala": 0.15, "Excessos Não Identificados": 0.25
                }
                df_data_raw["Meta"] = metas_fixas.get(pen, pd.NA)

            df_data_raw["Meta"] = pd.to_numeric(df_data_raw["Meta"], errors='coerce')
            df_data_raw.drop(columns=["Chave_Setor"], inplace=True)

            cols_data_to_check = [c for c in df_data_raw.columns if c not in ["Regional", "Nucleo", "Setor"]]
            df_data_raw['has_data'] = df_data_raw[cols_data_to_check].notna().any(axis=1)
            df_data_raw = df_data_raw[df_data_raw['has_data']].drop(columns=['has_data'])

            if df_data_raw.empty:
                continue

            # Cálculo GERAL
            cols_data_in_pivot_geral = [c for c in df_data_raw.columns if
                                        c not in ["Regional", "Nucleo", "Setor", "Meta", "Acum"]]
            if pen in penalidades_media:
                geral_vals = df_data_raw[cols_data_in_pivot_geral].apply(
                    lambda col: col[col.notna()].mean() if len(col[col.notna()]) > 0 else pd.NA, axis=0)
            else:
                geral_vals = df_data_raw[cols_data_in_pivot_geral].apply(lambda col: col.sum(), axis=0)

            geral = pd.DataFrame([geral_vals]).astype(float)
            geral["Regional"] = "GERAL"
            geral["Nucleo"] = "-"
            geral["Setor"] = "-"
            geral = geral[["Regional", "Nucleo", "Setor"] + geral_vals.index.tolist()]

            if pen in metas_dinamicas:
                df_meta_geral = df_merged[df_merged["Penalidades"] == metas_dinamicas.get(pen, "")].copy()
                df_meta_geral["Data"] = pd.to_datetime(df_meta_geral["Data"], errors="coerce")
                if not df_meta_geral.empty:
                    nucleos_visiveis = df_data_raw["Nucleo"].unique().tolist()
                    df_meta_geral = df_meta_geral[df_meta_geral["Nucleo"].isin(nucleos_visiveis)]
                    df_meta_geral = df_meta_geral[
                        (df_meta_geral["Data"].dt.date >= start_date) & (df_meta_geral["Data"].dt.date <= end_date)]
                    if not df_meta_geral.empty:
                        ultima_data = df_meta_geral["Data"].max()
                        df_meta_geral = df_meta_geral[df_meta_geral["Data"] == ultima_data]
                        meta_geral = df_meta_geral["Contagem"].mean() if pen == "VPML" else df_meta_geral[
                            "Contagem"].sum()
                    else:
                        meta_geral = pd.NA
                else:
                    meta_geral = pd.NA
            else:
                meta_geral = metas_fixas.get(pen, pd.NA)

            geral["Meta"] = meta_geral
            cols_datas_geral = [c for c in geral.columns if c not in ["Regional", "Nucleo", "Setor", "Meta"]]
            geral["Acum"] = geral[cols_datas_geral[-1]] if cols_datas_geral else pd.NA

            cols = geral.columns.tolist()
            for col in ["Meta", "Acum"]:
                if col in cols: cols.remove(col)
            cols.insert(3, "Acum")
            cols.insert(4, "Meta")
            geral = geral[cols]

            geral_aggrid_raw = geral.copy()
            for col in geral_aggrid_raw.columns:
                geral_aggrid_raw[col] = geral_aggrid_raw[col].mask(pd.isna(geral_aggrid_raw[col]), None)

            media_acum = geral["Acum"].apply(_to_float_or_none).dropna().mean()
            media_meta = geral["Meta"].apply(_to_float_or_none).dropna().mean()
            cor = get_dot_color(pen, media_acum, media_meta)
            display_pen = nome_indicador.get(pen, pen)

            # Expander para o Indicador/Penalidade
            with st.expander(f"{cor} {display_pen}", expanded=False):

                percentuais_js = json.dumps(list(PERCENTUAIS_LIST))
                inteiros_js = json.dumps(list(INTEIROS_LIST))
                decimais_js = json.dumps(list(DECIMAIS_LIST))
                moeda_js = json.dumps(list(MOEDA_LIST))
                lower_is_better_js = json.dumps(list(LOWER_IS_BETTER_LIST))

                # NOVO: JsCode para forçar o redimensionamento
                onGridReady_js = JsCode("""
                                    function(params) {
                                        // Força o grid a recalcular seu tamanho assim que é renderizado
                                        params.api.sizeColumnsToFit();
                                    }
                                """)

                formatter_js = f"""
                                    function(params) {{
                                        var value = params.value; 
                                        var penalidade = "{pen}".trim();
                                        var num_value;
                                        if (value === null || value === undefined) return ""; 
                                        try {{ num_value = parseFloat(String(value)); }} catch (e) {{ return ""; }}
                                        if (isNaN(num_value)) return ""; 
                                        var percentuais = {percentuais_js};
                                        var inteiros = {inteiros_js};
                                        var decimais = {decimais_js};
                                        var moedas = {moeda_js}; 

                                        if (moedas.includes(penalidade)) {{
                                            return num_value.toLocaleString('pt-BR', {{ style: 'currency', currency: 'BRL' }});
                                        }}
                                        if (percentuais.includes(penalidade)) {{
                                            return (num_value * 100).toFixed(2).replace(/0+$/, '').replace(/\.$/, '') + "%";
                                        }}
                                        if (inteiros.includes(penalidade)) return Math.round(num_value).toString();
                                        var str = decimais.includes(penalidade) ? num_value.toFixed(2) : num_value.toFixed(3);
                                        if (num_value !== 0 && str.indexOf('.') > -1) {{
                                            str = str.replace(/0+$/, '').replace(/\.$/, '');
                                        }}
                                        if (num_value === 0) return "0";
                                        return str;
                                    }}
                                    """

                cell_style_js = f"""
                                    function(params) {{
                                        var penalidade = "{pen}".trim();
                                        var lowerIsBetter = {lower_is_better_js};

                                        function parseVal(v) {{
                                            if (v === null || v === undefined) return null;
                                            if (typeof v === 'number') return v;
                                            return parseFloat(String(v).replace(',', '.').replace('%', ''));
                                        }}

                                        var acum = parseVal(params.value);

                                        var meta = null;
                                        if (params.node && params.node.aggData && params.node.aggData.Meta !== undefined) {{
                                             meta = parseVal(params.node.aggData.Meta);
                                        }} else if (params.data && params.data.Meta !== undefined) {{
                                             meta = parseVal(params.data.Meta);
                                        }}

                                        if (acum === null || meta === null) return null;

                                        if (lowerIsBetter.includes(penalidade)) {{
                                            if (acum > meta) {{
                                                return {{'color': '#FF6868', 'fontWeight': 'bold'}}; 
                                            }}
                                        }} else {{
                                            if (acum < meta) {{
                                                return {{'color': '#FF6868', 'fontWeight': 'bold'}};
                                            }}
                                        }}

                                        return null;
                                    }}
                                    """

                getRowId_js = JsCode("""
                                        function(params) {
                                            if (params.data.Setor) return params.data.Regional + params.data.Nucleo + params.data.Setor;
                                            if (params.data.Regional === 'GERAL') return 'GERAL_ROW';
                                            return Math.random().toString();
                                        }
                                    """)

                data_agg_func = "avg" if pen in penalidades_media else "sum"
                meta_agg_func = "avg" if pen in penalidades_media else "sum"
                suppressAggFuncInHeader = True

                gb = GridOptionsBuilder.from_dataframe(df_data_raw)
                gb.configure_default_column(
                    resizable=True, suppressSizeToFit=False, wrapHeaderText=True, autoHeaderHeight=True
                )
                gb.configure_column("Regional", rowGroup=True, hide=True, width=120)
                gb.configure_column("Nucleo", rowGroup=True, hide=True, width=120)
                gb.configure_column("Setor", rowGroup=False, hide=True, width=120)

                gb.configure_column(
                    "Meta", headerName="Meta", pinned="left", width=110, minWidth=110, suppressSizeToFit=True,
                    aggFunc=meta_agg_func, valueFormatter=JsCode(formatter_js), type=['numericColumn', 'rightAligned']
                )

                gb.configure_column(
                    "Acum", headerName="Acum", pinned="left", width=110, minWidth=110, suppressSizeToFit=True,
                    aggFunc=data_agg_func, valueFormatter=JsCode(formatter_js), type=['numericColumn', 'rightAligned'],
                    cellStyle=JsCode(cell_style_js)
                )

                cols_data_in_pivot_aggrid = [c for c in df_data_raw.columns if
                                             c not in ["Regional", "Nucleo", "Setor", "Meta", "Acum"]]
                for col in cols_data_in_pivot_aggrid:
                    gb.configure_column(
                        col, headerName=col, width=85, minWidth=80, maxWidth=100, suppressSizeToFit=False,
                        aggFunc=data_agg_func, valueFormatter=JsCode(formatter_js),
                        type=['numericColumn', 'rightAligned'],
                        cellStyle=JsCode(cell_style_js)
                    )

                autoGroupColumnDef = {
                    "headerName": "Regional / Núcleo / Setor", "pinned": "left", "width": 280,
                    "minWidth": 250, "maxWidth": 350,
                    "field": "Setor",  # <--- ADICIONE ESTA LINHA!
                    "cellRendererParams": {"suppressCount": True, "suppressLeafAfterColumns": False},
                    "wrapHeaderText": False, "autoHeaderHeight": False
                }
                gb.configure_grid_options(
                    autoGroupColumnDef=autoGroupColumnDef, pinnedBottomRowData=geral_aggrid_raw.to_dict('records'),
                    groupDefaultExpanded=0, suppressAggFuncInHeader=suppressAggFuncInHeader, rangeSelection=True,
                    getRowId=getRowId_js, allow_unsafe_jscode=True, suppressSizeToFit=False, ensureDomOrder=True,
                    groupSuppressGroupRows=False, groupIncludeFooter=False, groupSuppressBlankAndFloatingRow=True,
                    suppressAggAtRoot=True, suppressColumnVirtualisation=True, rowBuffer=20,
                    domLayout='autoHeight'  # <--- ADICIONE ESTA LINHA
                )
                grid_options = gb.build()
                try:
                    AgGrid(
                        df_data_raw,
                        gridOptions=grid_options,
                        # height=400,
                        fit_columns_on_grid_load=True,  # <--- MUDANÇA: de False para True (ajuda no trigger)
                        enable_enterprise_modules=True,
                        key=f"grid_{pen}_{filter_hash}",
                        allow_unsafe_jscode=True,
                    )
                except Exception as e:
                    st.error(f"Erro tabela {pen}: {e}")
                    continue

# A tag </div> final do seu arquivo
st.markdown('</div>', unsafe_allow_html=True)







