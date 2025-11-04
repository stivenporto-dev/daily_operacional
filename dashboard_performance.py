import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder
from datetime import date, timedelta
import math


# ===============================
# CONFIGURAÇÃO DA PÁGINA
# ===============================
st.set_page_config(layout="wide", page_title="📊 Daily Operacional")
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
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .content { margin-top: 100px; }
    .block-container {
        padding: 0rem !important;
        max-width: 100% !important;
        margin: 0 auto !important;
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

@st.cache_data(ttl=3600, show_spinner=False)
def carregar_daily_google(gids, url_base):
    abas = []
    for gid in gids:
        url_csv = f"{url_base}pub?gid={gid}&single=true&output=csv"
        df = pd.read_csv(url_csv, encoding="utf-8")
        df.columns = df.columns.str.strip()
        if "Data" in df.columns:
            df["Data"] = df["Data"].apply(converter_data_robusta)
        if "Contagem" in df.columns:
            df["Contagem"] = pd.to_numeric(
                df["Contagem"].astype(str).str.replace(",", ".", regex=False),
                errors="coerce"
            )
        abas.append(df)
    return pd.concat(abas, ignore_index=True)

@st.cache_data(ttl=3600, show_spinner=False)
def carregar_nucleos(xls_path):
    df_nuc = pd.read_excel(xls_path)
    df_nuc["Chave"] = df_nuc["Empresa"].astype(str) + df_nuc["Setor"].astype(str)
    return df_nuc

def formatar_contagem(valor, tipo):
    if pd.isna(valor):
        return ""
    percentuais = {"Meta VPML", "VPML", "Pontual%", "ControleEmbarque",
                   "AcadDDS", "AcadFixo", "Identificacao%", "TripulacaoEscalada%", "BaixaConducao%",
                   "MetaRecl%", "MetaAcid%", "VPML%"}
    inteiros = {"DocsPendentes", "DocsVencidBloq", "Reclamacoes", "Acidentes"}
    decimais = {"NotaConducao", "EventosExcessos", "BaixaConducao", "MultasRegulatorias"}
    if tipo in percentuais:
        try:
            return f"{valor * 100:.1f}%"
        except:
            return ""
    if tipo in inteiros:
        try:
            return str(int(round(valor)))
        except:
            return ""
    if tipo in decimais:
        try:
            return f"{valor:.2f}".rstrip("0").rstrip(".")
        except:
            return str(valor)
    if isinstance(valor, (int, float)):
        return f"{valor:.3f}".rstrip("0").rstrip(".")
    return str(valor)

def calcular_acum_ultimo_dia(df, penalidade):
    # identifica colunas de data (exclui colunas fixas)
    cols_datas = [c for c in df.columns if c not in ["Regional", "Nucleo", "Meta", "Acum"]]

    # cria coluna Acum se houver pelo menos uma coluna de data
    if cols_datas:
        ultimo_col = cols_datas[-1]
        df["Acum"] = df[ultimo_col]
    else:
        # garante que a coluna exista mesmo se não houver dados
        df["Acum"] = pd.NA

    # reorganiza colunas de forma segura
    cols = df.columns.tolist()
    if "Acum" in cols:
        cols.remove("Acum")
        insert_pos = 2 if len(cols) >= 2 else len(cols)
        cols.insert(insert_pos, "Acum")
        df = df[cols]

    return df

# ===============================
# FUNÇÕES DE COR E FORMATAÇÃO DE META
# ===============================
def _to_float_or_none(x):
    try:
        return float(str(x).replace("%", "").replace(",", "."))
    except:
        return None

def get_dot_color(penalidade, acum, meta):
    def _to_float_or_none_local(x):
        try:
            val = float(x)
            if math.isnan(val):
                return None
            return val
        except (TypeError, ValueError):
            return None

    acum_val = _to_float_or_none_local(acum)
    meta_val = _to_float_or_none_local(meta)

    # Se meta for nula/ausente → bolinha preta (sem meta definida)
    if meta_val is None:
        return "⚫"

    # Se ambos forem numéricos e zero → verde
    if acum_val is not None and meta_val == 0 and acum_val == 0:
        return "🟢"

    # Se acum for ausente (meta existe mas não há dado de acumulação) → cinza claro (indeterminado)
    if acum_val is None:
        return "⚪"

    # Agora ambos são numéricos — aplica lógica normal
    if penalidade in {"BaixaConducao%", "MultasRegulatorias", "DocsPendentes", "DocsVencidBloq",
                      "Reclamacoes", "Acidentes", "VPML", "EventosExcessos"}:
        # métricas que devem ser menores que a meta
        if acum_val < meta_val:
            return "🟢"
        elif acum_val == meta_val:
            return "🟡"
        else:
            return "🔴"
    else:
        # métricas que devem ser maiores que a meta
        if acum_val > meta_val:
            return "🟢"
        elif acum_val == meta_val:
            return "🟡"
        else:
            return "🔴"

# ===============================
# NOMES DOS INDICADORES
# ===============================
nome_indicador = {
    "DocsVencidBloq": "Documento Vencidos/Bloqueados",
    "DocsPendentes": "Documento Pendentes",
    "ControleEmbarque": "Controle de Embarque",
    "VPML": "Veículo Parado com o Motor Ligado",
    "NotaConducao": "Nota Condução",
    "PenalBaixaConducao": "Baixa Condução",
    "BaixaConducao%": "% Baixa Condução",
    "AcadDDS": "DDS",
    "AcadFixo": "Cursos Fixos",
    "EventosExcessos": "Excessos de Velocidade",
    "Pontual%": "Pontualidade",
    "MetaReg%": "Multas Regulatórias % da meta",
    "MultasRegulatorias": "Multas Regulatórias",
    "PenalMultasReg": "Multas Regulatórias",
    "TripulacaoEscalada%": "Escala de Tripulantes - OPTZ",
    "Identificacao%": "Identificação de Condutor",
    "Reclamacoes": "Reclamações",
    "MetaRecl%": "Reclamações % da meta",
    "Acidentes": "Sinistros",
    "MetaAcid%": "Sinistros % da meta",
    "PendIdentificacao": "Pendência de Identificação"
}

# ===============================
# CARREGAR DADOS
# ===============================
xls_path = r"I:\ITG_Inteligencia_Operacional\JCA_Inteligencia\01 - TELEMETRIA\dBase Nucleos.xlsx"
df_nucleos = carregar_nucleos(xls_path)

url_base = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQt4btv46n1B98NZscSD8hz78_x2mUHlKWnXe3z4mL1vJWeymx4RMgoV58N4OLV2sG2U_GBj5AcTGVQ/"
gids = ["0", "1688682064", "1552712710"]
df_daily = carregar_daily_google(gids, url_base)

df_merged = df_daily.merge(
    df_nucleos[["Chave", "Nucleo", "Regional", "Setor"]],
    left_on="Chave2", right_on="Chave", how="left"
)
df_merged.drop(columns=["Chave"], inplace=True)

# ===============================
# OCULTAR PENALIDADES/METAS PARA USUÁRIO
# ===============================
penalidades_ocultas = {
    "Meta VPML", "MetaReclamacoes", "MetaAcidentes", "MetaMultasReg",
    "MetaAcid%", "VPML%", "MetaReg%", "MetaRecl%", "ViagensProg",
    "MotsAtivos", "KmRodado", "Vendas", "BaixaConducao"
}
df_exib = df_merged[~df_merged["Penalidades"].str.startswith("Penal", na=False)]
df_exib = df_exib[~df_exib["Penalidades"].isin(penalidades_ocultas)]

# ===============================
# FILTROS
# ===============================
with st.sidebar:
    st.header("🔍 Filtros")
    penalidades_visiveis = sorted(df_exib["Penalidades"].dropna().unique())
    penalidades_sel = st.multiselect("Penalidades", penalidades_visiveis)
    regional_sel = st.multiselect("Regional", sorted(df_exib["Regional"].dropna().unique()))
    nucleo_sel = st.multiselect("Núcleo", sorted(df_exib["Nucleo"].dropna().unique()))
    setor_sel = st.multiselect("Setor", sorted(df_exib["Setor"].dropna().unique()))

    min_date = df_exib["Data"].min().date()
    max_date = min(df_exib["Data"].max().date(), hoje - timedelta(days=1))
    data_sel = st.date_input("Período", value=[min_date, max_date], min_value=min_date, max_value=max_date)

    if not isinstance(data_sel, (list, tuple)) or len(data_sel) < 2:
        st.warning("⚠️ Selecione duas datas para continuar.")
        st.stop()

# ===============================
# FILTRAGEM
# ===============================
df_filt = df_exib.copy()
if penalidades_sel:
    df_filt = df_filt[df_filt["Penalidades"].isin(penalidades_sel)]
if nucleo_sel:
    df_filt = df_filt[df_filt["Nucleo"].isin(nucleo_sel)]
if regional_sel:
    df_filt = df_filt[df_filt["Regional"].isin(regional_sel)]
if setor_sel:
    df_filt = df_filt[df_filt["Setor"].isin(setor_sel)]

df_filt = df_filt[
    (df_filt["Data"].dt.date >= data_sel[0]) & (df_filt["Data"].dt.date <= data_sel[1])
]

# ===============================
# METAS DINÂMICAS
# ===============================
metas_dinamicas = {
    "VPML": "Meta VPML",
    "Reclamacoes": "MetaReclamacoes",
    "Acidentes": "MetaAcidentes",
    "MultasRegulatorias": "MetaMultasReg"
}
metas_por_nucleo = {}
for pen, nome_meta in metas_dinamicas.items():
    df_meta = df_merged[df_merged["Penalidades"] == nome_meta].copy()
    df_meta["Data"] = pd.to_datetime(df_meta["Data"], errors="coerce")
    df_meta = df_meta[
        (df_meta["Data"].dt.date >= data_sel[0]) & (df_meta["Data"].dt.date <= data_sel[1])
    ]
    if df_meta.empty:
        continue
    if pen == "VPML":
        df_meta_agg = df_meta.groupby(["Nucleo", "Data"], as_index=False)["Contagem"].mean()
    else:
        df_meta_agg = df_meta.groupby(["Nucleo", "Data"], as_index=False)["Contagem"].sum()
    ultima_data_periodo = df_meta_agg["Data"].max()
    df_meta_ult = df_meta_agg[df_meta_agg["Data"] == ultima_data_periodo]
    metas_por_nucleo[pen] = df_meta_ult.set_index("Nucleo")["Contagem"].to_dict()

# ===============================
# PENALIDADES COM MÉDIA
# ===============================
penalidades_media = {
    "Meta VPML", "VPML", "VPML%", "MetaAcid%", "MetaRecl%", "MetaReg%",
    "Pontual%", "ControleEmbarque", "AcadDDS", "AcadFixo", "Identificacao%",
    "TripulacaoEscalada%", "BaixaConducao%", "NotaConducao", "BaixaConducao"
}

# ===============================
# LOOP PRINCIPAL (TABELAS)
# ===============================
for i, pen in enumerate(df_filt["Penalidades"].dropna().unique()):
    sub = df_filt[df_filt["Penalidades"] == pen].copy()
    aggfunc = "mean" if pen in penalidades_media else "sum"

    pivot = sub.pivot_table(
        index=["Regional", "Nucleo"],
        columns="Data",
        values="Contagem",
        aggfunc=aggfunc,
        fill_value=pd.NA
    )
    pivot = pivot.sort_index(axis=1)
    pivot.columns = [col.strftime("%d/%m") for col in pivot.columns]
    pivot = pivot.reset_index()
    pivot = calcular_acum_ultimo_dia(pivot, pen)

    # Meta
    if pen in metas_por_nucleo:
        pivot["Meta"] = pivot["Nucleo"].map(metas_por_nucleo.get(pen, {})).fillna("")
    else:
        metas_fixas = {
            "Pontual%": 0.8, "ControleEmbarque": 0.9, "AcadDDS": 0.95, "AcadFixo": 0.9,
            "BaixaConducao%": 0.1, "DocsPendentes": 0, "DocsVencidBloq": 0,
            "EventosExcessos": 0.02, "Identificacao%": 0.98, "TripulacaoEscalada%": 0.96,
            "NotaConducao": 70.0
        }
        pivot["Meta"] = metas_fixas.get(pen, "")

    # Linha geral
    if pen in penalidades_media:
        geral_vals = pivot.iloc[:, 3:].apply(lambda col: pd.to_numeric(col, errors='coerce').dropna().mean(), axis=0)
    else:
        geral_vals = pivot.iloc[:, 3:].apply(lambda col: pd.to_numeric(col, errors='coerce').dropna().sum(), axis=0)
    geral = pd.DataFrame([geral_vals])
    geral["Regional"] = "GERAL"
    geral["Nucleo"] = "-"

    # ---------- Meta geral: lógica corrigida (baseada na versão antiga) ----------
    if pen in metas_dinamicas:
        df_meta_geral = df_merged[df_merged["Penalidades"] == metas_dinamicas.get(pen, "")].copy()
        df_meta_geral["Data"] = pd.to_datetime(df_meta_geral["Data"], errors="coerce")
        if not df_meta_geral.empty:
            # considerar apenas os núcleos visíveis na tabela atual
            nucleos_visiveis = pivot["Nucleo"].unique().tolist()
            df_meta_geral = df_meta_geral[df_meta_geral["Nucleo"].isin(nucleos_visiveis)]
            df_meta_geral = df_meta_geral[
                (df_meta_geral["Data"].dt.date >= data_sel[0]) &
                (df_meta_geral["Data"].dt.date <= data_sel[1])
            ]
            if not df_meta_geral.empty:
                ultima_data = df_meta_geral["Data"].max()
                df_meta_geral = df_meta_geral[df_meta_geral["Data"] == ultima_data]
                # VPML -> média por núcleo; demais -> soma
                meta_geral = df_meta_geral["Contagem"].mean() if pen == "VPML" else df_meta_geral["Contagem"].sum()
            else:
                meta_geral = ""
        else:
            meta_geral = ""
    else:
        metas_fixas = {
            "Pontual%": 0.8, "ControleEmbarque": 0.9, "AcadDDS": 0.95, "AcadFixo": 0.9,
            "BaixaConducao%": 0.1, "DocsPendentes": 0, "DocsVencidBloq": 0,
            "EventosExcessos": 0.02, "Identificacao%": 0.98, "TripulacaoEscalada%": 0.96,
            "NotaConducao": 70.0
        }
        meta_geral = metas_fixas.get(pen, "")

    geral["Meta"] = meta_geral

    # Acum = último dia
    cols_datas = [c for c in geral.columns if c not in ["Regional", "Nucleo", "Meta"]]
    if cols_datas:
        geral["Acum"] = geral[cols_datas[-1]]

    pivot = pd.concat([pivot, geral], ignore_index=True)

    # Cálculo da cor
    media_acum = pivot["Acum"].apply(_to_float_or_none).dropna().mean()
    media_meta = pivot["Meta"].apply(_to_float_or_none).dropna().mean()
    cor = get_dot_color(pen, media_acum, media_meta)
    display_pen = nome_indicador.get(pen, pen)

    st.markdown(f"### {cor} {display_pen}")

    # Formatar
    pivot_formatado = pivot.copy()
    for col in pivot_formatado.columns:
        if pd.api.types.is_numeric_dtype(pivot_formatado[col]):
            pivot_formatado[col] = pivot_formatado[col].apply(lambda x: formatar_contagem(x, pen))

    gb = GridOptionsBuilder.from_dataframe(pivot_formatado)
    gb.configure_default_column(resizable=True, width=100)
    gb.configure_column("Regional", pinned="left", width=150)
    gb.configure_column("Nucleo", pinned="left", width=150)
    gb.configure_column("Meta", pinned="left", width=100)
    gb.configure_column("Acum", pinned="left", width=100)
    grid_options = gb.build()

    AgGrid(
        pivot_formatado,
        gridOptions=grid_options,
        height=min(500, 35 * len(pivot_formatado) + 50),
        fit_columns_on_grid_load=False,
        enable_enterprise_modules=False,
        key=f"aggrid_{i}"
    )

    st.divider()

st.markdown('</div>', unsafe_allow_html=True)
