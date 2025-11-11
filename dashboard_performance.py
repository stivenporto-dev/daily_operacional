import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
import math
import json

# ===============================
# CONFIGURAÇÃO DA PÁGINA
# ===============================
st.set_page_config(
    layout="wide", 
    page_title="📊 Daily Operacional",
    # 💡 ESTE É O PARÂMETRO CHAVE
    initial_sidebar_state="collapsed", 
    sidebar_width="300px" # Mantenha o ajuste de largura se desejar
hoje = date.today()

# ===============================
# ESTILO FIXO (AJUSTADO PARA MINIMIZAR ESPAÇAMENTO PÓS-TABELA SEM DIVIDER)
# ======================================================================
st.markdown("""
    <style>
    /* Ajustes de CABEÇALHO (Para ícone não cortado) */
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

    /* Ajuste para garantir que o conteúdo comece abaixo do cabeçalho fixo */
    .content { margin-top: 30px; } 

    /* Ajuste para o container principal */
    .block-container {
        padding: 1rem !important;
        max-width: 100% !important;
        margin: 0 auto !important;
    }

    /* 🟢 NOVO: CSS para reduzir espaçamento ao máximo entre AgGrid e o próximo H3 */

    /* 1. Reduzir a margem do título (###) para trazê-lo para mais perto da tabela anterior */
    h3 {
        margin-top: 0rem !important;    /* Reduz o espaço ANTES do título (o grande espaço branco) */
        margin-bottom: 0rem !important;
    }

    /* 2. Reduzir a margem inferior do componente AgGrid e do bloco que o contém */
    /* Este seletor tenta atingir o bloco que envolve a tabela AgGrid */
    div[data-testid*="stVerticalBlock"] > div:last-child {
        margin-bottom: 0rem !important; 
    }

    /* 3. Ajuste fino para o container principal onde o AgGrid é inserido (Pode ser necessário) */
    div[data-testid*="stVerticalBlock"] > div > div.ag-root-wrapper {
        margin-bottom: 0rem !important;
    }

    /* Remover HR (st.divider) se ainda houver alguma instância */
    hr {
        display: none; /* Garante que qualquer hr remanescente seja invisível e não ocupe espaço */
    }
    /* ========================================================= */
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
        try:
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
        except Exception as e:
            st.error(f"Erro ao carregar aba {gid}: {e}")
    if abas:
        return pd.concat(abas, ignore_index=True)
    else:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_nucleos_google():
    """Carrega dados dos núcleos do Google Sheets (Substitui carregar_nucleos(xls_path))"""

    # 1. Cria um placeholder para a mensagem na sidebar
    status_placeholder = st.sidebar.empty()

    try:
        sheet_id = "1N2C-g4RSV4nOaPOwqp_u85395p6xv0OiBs-akfxLTfk"
        gid = "0"
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

        # 2. Mostra um status temporário de 'loading'
        # Esta mensagem aparecerá apenas quando o cache for "miss" (primeira execução ou cache expirado)
        status_placeholder.info("Carregando dados dos Núcleos...")

        df_nuc = pd.read_csv(url)
        df_nuc.columns = df_nuc.columns.str.strip()

        colunas_necessarias = ['Empresa', 'Setor', 'Nucleo', 'Regional']
        colunas_faltantes = [col for col in colunas_necessarias if col not in df_nuc.columns]

        if colunas_faltantes:
            # Em caso de erro, a mensagem de erro deve persistir
            status_placeholder.error(f"❌ Colunas faltantes na planilha de Núcleos: {colunas_faltantes}")
            return pd.DataFrame()

        # Criação da chave de merge
        df_nuc["Chave"] = df_nuc["Empresa"].astype(str) + df_nuc["Setor"].astype(str)

        # 3. Mostra o sucesso (apenas para o usuário ver que terminou)
        status_placeholder.success("✅ Dados dos núcleos carregados!")

        # 4. LIMPA O PLACEHOLDER IMEDIATAMENTE APÓS EXIBIR O SUCESSO.
        # Isso faz com que a mensagem de sucesso suma.
        status_placeholder.empty()  # 💡 ESTA É A MUDANÇA PRINCIPAL

        return df_nuc

    except Exception as e:
        # Se houver erro, a mensagem de erro deve persistir
        status_placeholder.error(f"❌ Erro ao carregar dados dos núcleos: {str(e)}")
        return pd.DataFrame()


def _format_label(dt):
    # Formatting in Portuguese
    label = f"Daily - {dt.strftime('%B/%Y')}".replace(
        'January', 'Janeiro').replace('February', 'Fevereiro').replace(
        'March', 'Março').replace('April', 'Abril').replace(
        'May', 'Maio').replace('June', 'Junho').replace(
        'July', 'Julho').replace('August', 'Agosto').replace(
        'September', 'Setembro').replace('October', 'Outubro').replace(
        'November', 'Novembro').replace('December', 'Dezembro')
    return label


# Função para gerar os rótulos de período mensal (Ajustada)
def generate_monthly_periods(min_date: date, today: date, max_data_date: date):
    periods = {}

    current_dt = datetime(min_date.year, min_date.month, 1)

    # O loop deve ir até o PRIMEIRO dia do mês ATUAL
    end_loop_dt = datetime(today.year, today.month, 1)

    # Loop que inclui o primeiro dia do mês atual
    while current_dt <= end_loop_dt:
        month_start = current_dt.date()

        is_current_month = (current_dt.date().year == today.year and current_dt.date().month == today.month)

        if is_current_month:
            # Se for o mês atual, a data final é a menor entre 'hoje' e a data do último dado disponível.
            month_end = min(today, max_data_date)
        else:
            # Para meses passados, a data final é o último dia do mês
            month_end = (current_dt + relativedelta(months=1) - timedelta(days=1)).date()

        # Adiciona o mês apenas se o período for válido (month_start <= month_end).
        if month_start <= month_end:
            label = _format_label(current_dt)
            periods[label] = (month_start, month_end)

        current_dt += relativedelta(months=1)

    return periods


# Listas de formatação
PERCENTUAIS_LIST = {"Meta VPML", "VPML", "Pontual%", "ControleEmbarque",
                    "AcadDDS", "AcadFixo", "Identificacao%", "TripulacaoEscalada%", "BaixaConducao%",
                    "MetaRecl%", "MetaAcid%", "VPML%"}
INTEIROS_LIST = {"DocsPendentes", "DocsVencidBloq", "Reclamacoes", "Acidentes"}
DECIMAIS_LIST = {"NotaConducao", "EventosExcessos", "BaixaConducao", "MultasRegulatorias"}


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


# ===============================
# NOMES DOS INDICADORES E NOVO MAPA DE TEMA
# ===============================
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
}

# 🟢 NOVO: Mapeamento de Penalidade para Tema
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
}

# ===============================
# CARREGAR DADOS
# ===============================
try:
    # 🔄 Carregamento do Google Sheets (com placeholder de status)
    df_nucleos = carregar_nucleos_google()

    url_base = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQt4btv46n1B98NZscSD8hz78_x2mUHlKWnXe3z4mL1vJWeymx4RMgoV58N4OLV2sG2U_GBj5AcTGVQ/"
    gids = ["0", "1688682064", "1552712710"]
    df_daily = carregar_daily_google(gids, url_base)

    if df_daily.empty or df_nucleos.empty:
        st.error("Erro: Dados não puderam ser carregados. Verifique as fontes.")
        st.stop()

    df_merged = df_daily.merge(
        df_nucleos[["Chave", "Nucleo", "Regional", "Setor"]],
        left_on="Chave2", right_on="Chave", how="left"
    )
    df_merged.drop(columns=["Chave"], inplace=True)
    df_merged["Contagem"] = pd.to_numeric(df_merged["Contagem"], errors='coerce').astype(float)

    # 🟢 NOVO: Adiciona a coluna Tema
    df_merged["Tema"] = df_merged["Penalidades"].map(INDICADOR_TEMA_MAP).fillna("Outros")


except Exception as e:
    st.error(f"Erro ao processar dados: {e}")
    st.stop()

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
df_exib["Setor"] = df_exib["Setor"].fillna("-")

# ===============================
# FILTROS
# ===============================
# 💡 MUDANÇA: Revertido para st.sidebar para manter na lateral
with st.sidebar:
    st.header("🔍 Filtros")

    if df_exib.empty:
        st.warning("Nenhum dado disponível para filtros.")
        st.stop()

    # 🟢 NOVO: FILTRO TEMA (1º FILTRO)
    temas_visiveis = sorted(df_exib["Tema"].dropna().unique())
    tema_sel = st.multiselect("Tema", temas_visiveis, key="tema_sel_key")

    penalidades_visiveis = sorted(df_exib["Penalidades"].dropna().unique())
    penalidades_sel = st.multiselect("Penalidades", penalidades_visiveis, key="penalidades_sel_key")

    regional_sel = st.multiselect("Regional", sorted(df_exib["Regional"].dropna().unique()), key="regional_sel_key")
    nucleo_sel = st.multiselect("Núcleo", sorted(df_exib["Nucleo"].dropna().unique()), key="nucleo_sel_key")
    setor_sel = st.multiselect("Setor", sorted(df_exib["Setor"].dropna().unique()), key="setor_sel_key")

    # Lógica de seleção de período mensal
    try:
        # Pega a menor e a maior data do DataFrame
        min_data_dt = df_exib["Data"].min().to_pydatetime()
        min_period_date = min_data_dt.date()
        max_data_date = df_exib["Data"].max().to_pydatetime().date()  # Última data com dado no DF

        period_map = generate_monthly_periods(min_period_date, hoje, max_data_date)

        if not period_map:
            st.warning("⚠️ Não foi possível gerar os períodos mensais. Verifique a coluna 'Data'.")
            st.stop()

        period_labels = list(period_map.keys())

        # Define a seleção padrão para o mês mais recente (último da lista)
        default_index = len(period_labels) - 1

        periodo_sel = st.selectbox(
            "Selecione o Período",
            options=period_labels,
            index=default_index,
            key="periodo_sel_key"
        )

        # Extrai as datas do período selecionado
        start_date, end_date = period_map[periodo_sel]

        st.caption(f"De: **{start_date.strftime('%d/%m/%Y')}** a **{end_date.strftime('%d/%m/%Y')}**")

    except Exception as e:
        st.error(f"Erro ao processar datas para o filtro: {e}")
        # Se ocorrer um erro, definimos as datas para um período vazio para evitar que o código falhe
        start_date, end_date = date(1900, 1, 1), date(1900, 1, 1)

# ===============================
# FILTRAGEM
# ===============================
df_filt = df_exib.copy()

# 🟢 NOVO: FILTRA POR TEMA
if tema_sel:
    df_filt = df_filt[df_filt["Tema"].isin(tema_sel)]

if penalidades_sel:
    df_filt = df_filt[df_filt["Penalidades"].isin(penalidades_sel)]
if nucleo_sel:
    df_filt = df_filt[df_filt["Nucleo"].isin(nucleo_sel)]
if regional_sel:
    df_filt = df_filt[df_filt["Regional"].isin(regional_sel)]
if setor_sel:
    df_filt = df_filt[df_filt["Setor"].isin(setor_sel)]

# Uso das datas de início e fim do período selecionado
df_filt = df_filt[
    (df_filt["Data"].dt.date >= start_date) & (df_filt["Data"].dt.date <= end_date)
    ]

if df_filt.empty or df_filt["Penalidades"].dropna().empty:
    st.warning("⚠️ Nenhum dado encontrado para os filtros e período selecionados.")
    st.stop()

# ===============================
# METAS DINÂMICAS (AJUSTADO PARA O SETOR)
# ===============================
metas_dinamicas = {
    "VPML": "Meta VPML",
    "Reclamacoes": "MetaReclamacoes",
    "Acidentes": "MetaAcidentes",
    "MultasRegulatorias": "MetaMultasReg"
}
metas_por_setor = {}
for pen, nome_meta in metas_dinamicas.items():
    df_meta = df_merged[df_merged["Penalidades"] == nome_meta].copy()

    # Filtra apenas núcleos/setores que estão na exibição
    nucleos_visiveis = df_exib["Nucleo"].unique().tolist()
    setores_visiveis = df_exib["Setor"].unique().tolist()
    df_meta = df_meta[df_meta["Nucleo"].isin(nucleos_visiveis) & df_meta["Setor"].isin(setores_visiveis)]

    df_meta["Data"] = pd.to_datetime(df_meta["Data"], errors="coerce")
    df_meta = df_meta[
        (df_meta["Data"].dt.date >= start_date) & (df_meta["Data"].dt.date <= end_date)
        ]
    if df_meta.empty:
        continue

    # MUDANÇA: Agrupa por Núcleo, Setor e Data
    if pen == "VPML":
        df_meta_agg = df_meta.groupby(["Nucleo", "Setor", "Data"], as_index=False)["Contagem"].mean()
    else:
        df_meta_agg = df_meta.groupby(["Nucleo", "Setor", "Data"], as_index=False)["Contagem"].sum()

    ultima_data_periodo = df_meta_agg["Data"].max()
    df_meta_ult = df_meta_agg[df_meta_agg["Data"] == ultima_data_periodo]

    # MUDANÇA: Cria uma chave composta (Núcleo_Setor)
    df_meta_ult["Chave_Setor"] = df_meta_ult["Nucleo"].astype(str) + "_" + df_meta_ult["Setor"].astype(str)
    metas_por_setor[pen] = df_meta_ult.set_index("Chave_Setor")["Contagem"].to_dict()

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

    if sub.empty:
        continue

    aggfunc = "mean" if pen in penalidades_media else "sum"

    # Cria o PIVOT
    try:
        pivot = sub.pivot_table(
            index=["Regional", "Nucleo", "Setor"],
            columns="Data",
            values="Contagem",
            aggfunc=aggfunc,
            fill_value=pd.NA
        ).sort_index(axis=1)

        if "Data" in pivot.columns:
            pivot = pivot.drop(columns=["Data"])

        # Renomeia colunas de data
        pivot.columns = [col.strftime("%d/%m") for col in pivot.columns]

        df_data_raw = pivot.reset_index()

        if "Data" in df_data_raw.columns:
            df_data_raw = df_data_raw.drop(columns=["Data"])

        colunas_duplicadas = [c for c in df_data_raw.columns if c.lower().strip() == "data"]
        if colunas_duplicadas:
            df_data_raw = df_data_raw.drop(columns=colunas_duplicadas)

        df_data_raw = df_data_raw.loc[:, ~df_data_raw.columns.duplicated()]
        df_data_raw = df_data_raw[[c for c in df_data_raw.columns if not ("00:00" in str(c) or "Data" in str(c))]]
    except Exception as e:
        st.error(f"Erro ao criar pivot para {pen}: {e}")
        continue

    # Força todas as colunas de dados para float64
    cols_data_in_pivot = [c for c in df_data_raw.columns if c not in ["Regional", "Nucleo", "Setor"]]
    for c in cols_data_in_pivot:
        df_data_raw[c] = pd.to_numeric(df_data_raw[c], errors='coerce')

    # Trata NaN para agregação correta no AgGrid
    if pen in penalidades_media:
        # Para MÉDIAS: NaN vira None, para que o 'avg' ignore esses valores
        cols_to_fill_mean = [c for c in cols_data_in_pivot if c not in ["Meta", "Acum"]]
        for c in cols_to_fill_mean:
            df_data_raw[c] = df_data_raw[c].mask(pd.isna(df_data_raw[c]), None)
    else:
        # Para SOMAS: NaN vira 0.0
        cols_to_fill = [c for c in df_data_raw.columns if c not in ["Regional", "Nucleo", "Setor"]]
        for c in cols_to_fill:
            df_data_raw[c] = df_data_raw[c].fillna(0.0)

    # Acumulado = Último Dia
    df_data_raw = calcular_acum_ultimo_dia(df_data_raw, pen)

    # Mapeamento de Meta (AJUSTADO PARA O SETOR)
    # MUDANÇA: Cria a chave composta em df_data_raw para mapeamento
    df_data_raw["Chave_Setor"] = df_data_raw["Nucleo"].astype(str) + "_" + df_data_raw["Setor"].astype(str)

    if pen in metas_por_setor:
        # MUDANÇA: Mapeia usando a chave Setor
        df_data_raw["Meta"] = df_data_raw["Chave_Setor"].map(metas_por_setor.get(pen, {})).fillna(pd.NA)
    else:
        metas_fixas = {
            "Pontual%": 0.8, "ControleEmbarque": 0.9, "AcadDDS": 0.95, "AcadFixo": 0.9,
            "BaixaConducao%": 0.1, "DocsPendentes": 0, "DocsVencidBloq": 0,
            "EventosExcessos": 0.02, "Identificacao%": 0.98, "TripulacaoEscalada%": 0.96,
            "NotaConducao": 70.0
        }
        df_data_raw["Meta"] = metas_fixas.get(pen, pd.NA)

    df_data_raw["Meta"] = pd.to_numeric(df_data_raw["Meta"], errors='coerce')

    # MUDANÇA: Remove a coluna temporária
    df_data_raw.drop(columns=["Chave_Setor"], inplace=True)

    # BLOCO ANTIGO REMOVIDO: A remoção desse bloco é a chave para exibir a meta em todos os setores
    # if pen not in penalidades_media:
    #     is_duplicated_nucleo = df_data_raw.duplicated(subset=["Nucleo"], keep='first')
    #     df_data_raw.loc[is_duplicated_nucleo, "Meta"] = pd.NA

    cols_data_to_check = [c for c in df_data_raw.columns if c not in ["Regional", "Nucleo", "Setor"]]
    df_data_raw['has_data'] = df_data_raw[cols_data_to_check].notna().any(axis=1)
    df_data_raw = df_data_raw[df_data_raw['has_data']].drop(columns=['has_data'])

    if df_data_raw.empty:
        display_pen = nome_indicador.get(pen, pen)
        st.warning(f"⚠️ Nenhum resultado com dados para o indicador: **{display_pen}** no período selecionado.")
        st.divider()
        continue

    # Cálculo da Linha GERAL
    cols_data_in_pivot_geral = [c for c in df_data_raw.columns if
                                c not in ["Regional", "Nucleo", "Setor", "Meta", "Acum"]]

    if pen in penalidades_media:
        geral_vals = df_data_raw[cols_data_in_pivot_geral].apply(
            lambda col: col[col.notna()].mean() if len(col[col.notna()]) > 0 else pd.NA, axis=0)
    else:
        geral_vals = df_data_raw[cols_data_in_pivot_geral].apply(
            lambda col: col.sum(), axis=0)

    geral = pd.DataFrame([geral_vals]).astype(float)
    geral["Regional"] = "GERAL"
    geral["Nucleo"] = "-"
    geral["Setor"] = "-"

    geral = geral[["Regional", "Nucleo", "Setor"] + geral_vals.index.tolist()]

    # Cálculo da Meta Geral
    if pen in metas_dinamicas:
        df_meta_geral = df_merged[df_merged["Penalidades"] == metas_dinamicas.get(pen, "")].copy()
        df_meta_geral["Data"] = pd.to_datetime(df_meta_geral["Data"], errors="coerce")
        if not df_meta_geral.empty:
            nucleos_visiveis = df_data_raw["Nucleo"].unique().tolist()
            df_meta_geral = df_meta_geral[df_meta_geral["Nucleo"].isin(nucleos_visiveis)]
            df_meta_geral = df_meta_geral[
                (df_meta_geral["Data"].dt.date >= start_date) &
                (df_meta_geral["Data"].dt.date <= end_date)
                ]
            if not df_meta_geral.empty:
                ultima_data = df_meta_geral["Data"].max()
                df_meta_geral = df_meta_geral[df_meta_geral["Data"] == ultima_data]
                # A Meta Geral ainda é calculada por soma/média de todos os valores de meta
                meta_geral = df_meta_geral["Contagem"].mean() if pen == "VPML" else df_meta_geral["Contagem"].sum()
            else:
                meta_geral = pd.NA
        else:
            meta_geral = pd.NA
    else:
        meta_geral = metas_fixas.get(pen, pd.NA)

    geral["Meta"] = meta_geral

    # Acum Geral
    cols_datas_geral = [c for c in geral.columns if c not in ["Regional", "Nucleo", "Setor", "Meta"]]
    if cols_datas_geral:
        geral["Acum"] = geral[cols_datas_geral[-1]]
    else:
        geral["Acum"] = pd.NA

    # Reordenar colunas
    cols = geral.columns.tolist()
    for col in ["Meta", "Acum"]:
        if col in cols:
            cols.remove(col)
    cols.insert(3, "Acum")
    cols.insert(4, "Meta")
    geral = geral[cols]

    geral_aggrid_raw = geral.copy()
    for col in geral_aggrid_raw.columns:
        geral_aggrid_raw[col] = geral_aggrid_raw[col].mask(pd.isna(geral_aggrid_raw[col]), None)

    # Cálculo da cor e Título
    media_acum = geral["Acum"].apply(_to_float_or_none).dropna().mean()
    media_meta = geral["Meta"].apply(_to_float_or_none).dropna().mean()
    cor = get_dot_color(pen, media_acum, media_meta)
    display_pen = nome_indicador.get(pen, pen)

    st.markdown(f"### {cor} {display_pen}")

    # Formatter JS
    percentuais_js = json.dumps(list(PERCENTUAIS_LIST))
    inteiros_js = json.dumps(list(INTEIROS_LIST))
    decimais_js = json.dumps(list(DECIMAIS_LIST))

    formatter_js = f"""
    function(params) {{
        var value = params.value; 
        var penalidade = "{pen}".trim();
        var num_value;

        if (value === null || value === undefined) {{
            return ""; 
        }}

        try {{
            num_value = parseFloat(String(value));
        }} catch (e) {{
            return ""; 
        }}

        if (isNaN(num_value)) {{
            return ""; 
        }}

        var percentuais = {percentuais_js};
        var inteiros = {inteiros_js};
        var decimais = {decimais_js};

        // 1. PERCENTUAIS (Remove .toFixed(2) para que o formatter retire zeros desnecessários)
        if (percentuais.includes(penalidade)) {{
            return (num_value * 100).toFixed(2).replace(/0+$/, '').replace(/\.$/, '') + "%";
        }}

        // 2. INTEIROS
        if (inteiros.includes(penalidade)) {{
            return Math.round(num_value).toString();
        }}

        // 3. DECIMAIS / PADRÃO
        var str = decimais.includes(penalidade) ? num_value.toFixed(2) : num_value.toFixed(3);

        if (num_value !== 0) {{
            if (str.indexOf('.') > -1) {{
                str = str.replace(/0+$/, ''); 
                str = str.replace(/\.$/, '');
            }}
        }}

        if (num_value === 0) {{
            return "0"; // Permite que zero seja exibido para não-percentuais
        }}

        return str;
    }}
    """

    getRowId_js = JsCode("""
        function(params) {
            if (params.data.Setor) {
                return params.data.Regional + params.data.Nucleo + params.data.Setor;
            }
            if (params.data.Regional === 'GERAL') {
                return 'GERAL_ROW';
            }
            return Math.random().toString();
        }
        """)

    # Estratégias de agregação
    if pen in penalidades_media:
        data_agg_func = "avg"
        meta_agg_func = "avg"
        suppressAggFuncInHeader = True
    else:
        data_agg_func = "sum"
        meta_agg_func = "sum"
        suppressAggFuncInHeader = True

    gb = GridOptionsBuilder.from_dataframe(df_data_raw)
    gb.configure_default_column(resizable=True, width=100)

    # Configurar colunas de agrupamento
    gb.configure_column("Regional", rowGroup=True, hide=True, width=120)
    gb.configure_column("Nucleo", rowGroup=True, hide=True, width=120)
    gb.configure_column("Setor", rowGroup=True, hide=True, width=120)

    # Configurar colunas Acum e Meta
    gb.configure_column(
        "Meta",
        headerName="Meta",
        pinned="left",
        width=110,
        aggFunc=meta_agg_func,
        valueFormatter=JsCode(formatter_js),
        type=['numericColumn', 'rightAligned']
    )

    gb.configure_column(
        "Acum",
        headerName="Acum",
        pinned="left",
        width=110,
        aggFunc=data_agg_func,
        valueFormatter=JsCode(formatter_js),
        type=['numericColumn', 'rightAligned']
    )

    # Configurar colunas de Data Diária
    cols_data_in_pivot_aggrid = [c for c in df_data_raw.columns if
                                 c not in ["Regional", "Nucleo", "Setor", "Meta", "Acum"]]
    for col in cols_data_in_pivot_aggrid:
        gb.configure_column(
            col,
            headerName=col,
            aggFunc=data_agg_func,
            valueFormatter=JsCode(formatter_js),
            type=['numericColumn', 'rightAligned']
        )

    # Configurar coluna de agrupamento automática
    autoGroupColumnDef = {
        "headerName": "Regional / Núcleo / Setor",
        "pinned": "left",
        "width": 350,
        "cellRendererParams": {
            "suppressCount": True,
            # 💡 SOLUÇÃO APLICADA AQUI: Suprimir a linha de dados após o grupo
            "suppressLeafAfterColumns": True,
        },
    }

    # Configurar grid options
    gb.configure_grid_options(
        autoGroupColumnDef=autoGroupColumnDef,
        pinnedBottomRowData=geral_aggrid_raw.to_dict('records'),
        groupDefaultExpanded=0,
        suppressAggFuncInHeader=suppressAggFuncInHeader,
        rangeSelection=True,
        getRowId=getRowId_js,
        allow_unsafe_jscode=True,
        # Manter as configurações de supressão que não devem estar ativadas para o seu caso
        groupSuppressGroupRows=False,
        groupIncludeFooter=False,
        groupSuppressBlankAndFloatingRow=False,

        # Esta opção garante que a agregação apareça no nível do grupo
        suppressAggAtRoot=True,
    )

    grid_options = gb.build()

    # Exibir a grade
    try:
        AgGrid(
            df_data_raw,
            gridOptions=grid_options,
            autoHeight=True,
            fit_columns_on_grid_load=False,  # Manteve False
            enable_enterprise_modules=True,
            key=f"aggrid_{i}_{pen}",
            allow_unsafe_jscode=True,
            # 💡 REMOVIDA: autoSizeColumns=True foi removido para evitar problemas de largura com colunas fixadas
        )
    except Exception as e:
        st.error(f"Erro ao exibir tabela para {pen}: {e}")
        continue

    st.divider()

st.markdown('</div>', unsafe_allow_html=True)


