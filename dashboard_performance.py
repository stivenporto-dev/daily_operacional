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

# Esta função original não será usada diretamente, mas a lógica de conversão é mantida abaixo.
# @st.cache_data(ttl=3600, show_spinner=False)
# def carregar_nucleos(xls_path):
#    ...

def formatar_contagem(valor, tipo):
    if pd.isna(valor):
        return ""
    percentuais = {"Meta VPML", "VPML", "Pontual%", "ControleEmbarque",
                   "AcadDDS", "AcadFixo", "Identificacao%", "TripulacaoEscalada%", "BaixaConducao%",
                   "MetaRecl%", "MetaAcid%", "VPML%"}
    inteiros = {"DocsPendentes", "DocsVencidBloq", "Reclamacoes", "Acidentes"}
    decimais = {"NotaConducao", "EventosExcessos", "BaixaConducao", "MultasRegulatorias"}
    
    # Tentativa de converter para float para formatação segura
    try:
        val_float = float(valor)
    except (ValueError, TypeError):
        return str(valor)

    if tipo in percentuais:
        return f"{val_float * 100:.1f}%"
    if tipo in inteiros:
        return str(int(round(val_float)))
    if tipo in decimais:
        return f"{val_float:.2f}".rstrip("0").rstrip(".")
    
    return f"{val_float:.3f}".rstrip("0").rstrip(".")

def calcular_acum_ultimo_dia(df, penalidade):
    # Identifica colunas de data (exclui colunas fixas)
    cols_datas = [c for c in df.columns if c not in ["Regional", "Nucleo", "Meta", "Acum"]]

    # Cria coluna Acum se houver pelo menos uma coluna de data
    if cols_datas:
        ultimo_col = cols_datas[-1]
        df["Acum"] = df[ultimo_col]
    else:
        # Garante que a coluna exista mesmo se não houver dados
        df["Acum"] = pd.NA

    # Reorganiza colunas de forma segura
    cols = df.columns.tolist()
    if "Acum" in cols:
        cols.remove("Acum")
        insert_pos = 2 if len(cols) >= 2 else len(cols)
        cols.insert(insert_pos, "Acum")
        df = df[cols]

    return df

# FUNÇÕES DE COR E FORMATAÇÃO DE META (Mantidas inalteradas)
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

    if meta_val is None:
        return "⚫"
    if acum_val is not None and meta_val == 0 and acum_val == 0:
        return "🟢"
    if acum_val is None:
        return "⚪"

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

# NOMES DOS INDICADORES (Mantidos inalterados)
nome_indicador = {
    "DocsVencidBloq": "Documento Vencidos/Bloqueados", "DocsPendentes": "Documento Pendentes",
    "ControleEmbarque": "Controle de Embarque", "VPML": "Veículo Parado com o Motor Ligado",
    "NotaConducao": "Nota Condução", "PenalBaixaConducao": "Baixa Condução",
    "BaixaConducao%": "% Baixa Condução", "AcadDDS": "DDS", "AcadFixo": "Cursos Fixos",
    "EventosExcessos": "Excessos de Velocidade", "Pontual%": "Pontualidade",
    "MetaReg%": "Multas Regulatórias % da meta", "MultasRegulatorias": "Multas Regulatórias",
    "PenalMultasReg": "Multas Regulatórias", "TripulacaoEscalada%": "Escala de Tripulantes - OPTZ",
    "Identificacao%": "Identificação de Condutor", "Reclamacoes": "Reclamações",
    "MetaRecl%": "Reclamações % da meta", "Acidentes": "Sinistros",
    "MetaAcid%": "Sinistros % da meta", "PendIdentificacao": "Pendência de Identificação"
}

# ===============================
# CARREGAMENTO DE DADOS (Consolidado e Robusto)
# ===============================

@st.cache_data(ttl=3600, show_spinner=False)
def carregar_nucleos_google():
    """Carrega dados dos núcleos do Google Sheets"""
    try:
        sheet_id = "1N2C-g4RSV4nOaPOwqp_u85395p6xv0OiBs-akfxLTfk"
        gid = "0"
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        df_nuc = pd.read_csv(url)
        colunas_necessarias = ['Empresa', 'Setor', 'Nucleo', 'Regional']
        colunas_faltantes = [col for col in colunas_necessarias if col not in df_nuc.columns]

        if colunas_faltantes:
            st.error(f"❌ Colunas faltantes na planilha: {colunas_faltantes}")
            st.info("📋 Colunas encontradas: " + ", ".join(df_nuc.columns.tolist()))
            return None

        df_nuc["Chave"] = df_nuc["Empresa"].astype(str) + df_nuc["Setor"].astype(str)
        st.sidebar.success("✅ Dados dos núcleos carregados do Google Sheets")
        return df_nuc

    except Exception as e:
        st.error(f"❌ Erro ao carregar dados dos núcleos: {str(e)}")
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def carregar_daily_google():
    """Carrega dados do daily do Google Sheets"""
    try:
        url_base = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQt4btv46n1B98NZscSD8hz78_x2mUHlKWnXe3z4mL1vJWeymx4RMgoV58N4OLV2sG2U_GBj5AcTGVQ/"
        gids = ["0", "1688682064", "1552712710"]

        abas = []
        for gid in gids:
            url_csv = f"{url_base}pub?gid={gid}&single=true&output=csv"
            df = pd.read_csv(url_csv, encoding="utf-8")
            df.columns = df.columns.str.strip()
            
            # Aplica conversão robusta de Data e Contagem
            if "Data" in df.columns:
                df["Data"] = df["Data"].apply(converter_data_robusta)
            if "Contagem" in df.columns:
                df["Contagem"] = pd.to_numeric(
                    df["Contagem"].astype(str).str.replace(",", ".", regex=False),
                    errors="coerce"
                )
            abas.append(df)

        df_daily = pd.concat(abas, ignore_index=True)
        st.sidebar.success("✅ Dados diários carregados do Google Sheets")
        return df_daily

    except Exception as e:
        st.error(f"❌ Erro ao carregar dados diários: {str(e)}")
        return None

# Carregar todos os dados
with st.spinner("Carregando dados do Google Sheets..."):
    df_nucleos = carregar_nucleos_google()

    if df_nucleos is None:
        st.error("Não foi possível carregar os dados dos núcleos. Verifique as permissões de compartilhamento.")
        st.stop()

    df_daily = carregar_daily_google()

    if df_daily is None:
        st.error("Não foi possível carregar os dados diários.")
        st.stop()

    # Merge dos dados
    df_merged = df_daily.merge(
        df_nucleos[["Chave", "Nucleo", "Regional", "Setor"]],
        left_on="Chave2", right_on="Chave", how="left"
    )
    df_merged.drop(columns=["Chave"], inplace=True)
    
    # 💡 CORREÇÃO APLICADA: Forçar a coluna "Data" como datetime após o merge
    # Isso garante que a filtragem por data_sel funcione corretamente.
    df_merged["Data"] = pd.to_datetime(df_merged["Data"], errors="coerce")

    st.success("✅ Todos os dados carregados com sucesso!")

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

    # Lógica de data para evitar erro se df_exib for vazio
    min_date = df_exib["Data"].min().date() if not df_exib.empty and pd.notna(df_exib["Data"].min()) else hoje - timedelta(days=30)
    max_date = df_exib["Data"].max().date() if not df_exib.empty and pd.notna(df_exib["Data"].max()) else hoje - timedelta(days=1)
    
    # Garante que a data máxima de seleção não passe de "hoje - 1 dia"
    max_date_safe = min(max_date, hoje - timedelta(days=1))
    
    data_sel = st.date_input("Período", value=[min_date, max_date_safe], min_value=min_date, max_value=max_date_safe)

    if not isinstance(data_sel, (list, tuple)) or len(data_sel) < 2:
        st.warning("⚠️ Selecione duas datas para continuar.")
        st.stop()

# ===============================
# FILTRAGEM (Mantida inalterada, mas agora mais robusta devido à correção no dtype)
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

# Se após a filtragem o DF estiver vazio, pare a execução
if df_filt.empty:
    st.info("Nenhum dado encontrado para o período e filtros selecionados.")
    st.stop()

# ===============================
# METAS DINÂMICAS (Mantida inalterada)
# ===============================
metas_dinamicas = {
    "VPML": "Meta VPML", "Reclamacoes": "MetaReclamacoes",
    "Acidentes": "MetaAcidentes", "MultasRegulatorias": "MetaMultasReg"
}
metas_por_nucleo = {}
for pen, nome_meta in metas_dinamicas.items():
    df_meta = df_merged[df_merged["Penalidades"] == nome_meta].copy()
    df_meta["Data"] = pd.to_datetime(df_meta["Data"], errors="coerce") # OK: Re-converte no DF de meta
    df_meta = df_meta[
        (df_meta["Data"].dt.date >= data_sel[0]) & (df_meta["Data"].dt.date <= data_sel[1])
    ]
    if df_meta.empty:
        continue
    
    # Agregação
    if pen == "VPML":
        df_meta_agg = df_meta.groupby(["Nucleo", "Data"], as_index=False)["Contagem"].mean()
    else:
        df_meta_agg = df_meta.groupby(["Nucleo", "Data"], as_index=False)["Contagem"].sum()
        
    ultima_data_periodo = df_meta_agg["Data"].max()
    df_meta_ult = df_meta_agg[df_meta_agg["Data"] == ultima_data_periodo]
    metas_por_nucleo[pen] = df_meta_ult.set_index("Nucleo")["Contagem"].to_dict()

# ===============================
# PENALIDADES COM MÉDIA (Mantida inalterada)
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

    # Pivotagem
    pivot = sub.pivot_table(
        index=["Regional", "Nucleo"],
        columns="Data",
        values="Contagem",
        aggfunc=aggfunc,
        fill_value=pd.NA
    )
    
    # Formatação de Colunas de Data
    pivot = pivot.sort_index(axis=1)
    pivot.columns = [col.strftime("%d/%m") for col in pivot.columns]
    pivot = pivot.reset_index()
    pivot = calcular_acum_ultimo_dia(pivot, pen)

    # Meta por Núcleo (Lógica Mantida)
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

    # Meta Geral (Lógica Mantida)
    if pen in metas_dinamicas:
        # Lógica de Meta Geral baseada no df_merged filtrado pela data_sel
        df_meta_geral = df_merged[df_merged["Penalidades"] == metas_dinamicas.get(pen, "")].copy()
        df_meta_geral["Data"] = pd.to_datetime(df_meta_geral["Data"], errors="coerce")
        
        nucleos_visiveis = pivot["Nucleo"].unique().tolist()
        df_meta_geral = df_meta_geral[df_meta_geral["Nucleo"].isin(nucleos_visiveis)]
        df_meta_geral = df_meta_geral[
            (df_meta_geral["Data"].dt.date >= data_sel[0]) &
            (df_meta_geral["Data"].dt.date <= data_sel[1])
        ]
        
        if not df_meta_geral.empty:
            ultima_data = df_meta_geral["Data"].max()
            df_meta_geral = df_meta_geral[df_meta_geral["Data"] == ultima_data]
            meta_geral = df_meta_geral["Contagem"].mean() if pen == "VPML" else df_meta_geral["Contagem"].sum()
        else:
            meta_geral = ""
    else:
        meta_geral = metas_fixas.get(pen, "")

    geral["Meta"] = meta_geral

    # Acum = último dia
    cols_datas = [c for c in geral.columns if c not in ["Regional", "Nucleo", "Meta"]]
    if cols_datas:
        geral["Acum"] = geral[cols_datas[-1]]

    pivot = pd.concat([pivot, geral], ignore_index=True)

    # Exibição
    media_acum = pivot["Acum"].apply(_to_float_or_none).dropna().mean()
    media_meta = pivot["Meta"].apply(_to_float_or_none).dropna().mean()
    cor = get_dot_color(pen, media_acum, media_meta)
    display_pen = nome_indicador.get(pen, pen)

    st.markdown(f"### {cor} {display_pen}")

    # Formatar para exibição
    pivot_formatado = pivot.copy()
    for col in pivot_formatado.columns:
        if col in ["Regional", "Nucleo", "Meta", "Acum"] or any(char.isdigit() for char in col):
            # Formata apenas colunas de dados ou as colunas fixas relevantes
            # Garante que a coluna de data (no formato dd/mm) seja formatada como Contagem
            pivot_formatado[col] = pivot_formatado[col].apply(lambda x: formatar_contagem(x, pen))

    # Configuração AgGrid (Mantida inalterada)
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
