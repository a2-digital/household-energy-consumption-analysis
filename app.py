from datetime import date

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="Dashboard de Consumo Energético",
    page_icon="⚡",
    layout="wide"
)

# =========================================================
# CONSTANTES
# =========================================================
BG = "#0e1117"
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
ESTACIONES = ["Primavera", "Verano", "Otoño", "Invierno"]
MAPA_ESTACION = {
    12: "Invierno", 1: "Invierno", 2: "Invierno",
    3: "Primavera", 4: "Primavera", 5: "Primavera",
    6: "Verano", 7: "Verano", 8: "Verano",
    9: "Otoño", 10: "Otoño", 11: "Otoño",
}
COLOR_ESTACION = {
    "Primavera": "limegreen", "Verano": "gold",
    "Otoño": "sienna", "Invierno": "steelblue",
}
# Columna del archivo horario -> nombre para mostrar
CIRCUITOS = {
    "Sub1_Wh": "Cocina (Sub 1)",
    "Sub2_Wh": "Lavandería (Sub 2)",
    "Sub3_Wh": "Calentador/AC (Sub 3)",
    "Otros_Wh": "Otros (Other)",
}
# Mismos colores que tu notebook
COLOR_CIRCUITO = {
    "Cocina (Sub 1)": "sandybrown",
    "Lavandería (Sub 2)": "deepskyblue",
    "Calentador/AC (Sub 3)": "crimson",
    "Otros (Other)": "silver",
}

# =========================================================
# ESTILOS
# =========================================================
st.markdown("""
    <style>
        [data-testid="stAppViewContainer"], [data-testid="stSidebar"], header[data-testid="stHeader"] {
            background-color: #0e1117;
            color: white;
        }
        [data-testid="stMarkdownContainer"],
        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"] {
            color: white;
        }
        div[data-testid="stAlert"] {
            background-color: rgba(245, 158, 11, 0.12) !important;
            border-left: 4px solid #f59e0b !important;
            color: #fef08a !important;
        }
        div[data-testid="stDownloadButton"] button {
            background-color: #f59e0b;
            border: none;
        }
        div[data-testid="stDownloadButton"] button * {
            color: #0e1117 !important;
            font-weight: 600;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
    </style>
""", unsafe_allow_html=True)


def estilizar(fig):
    """Tema oscuro completo (textos, ejes y leyendas) para todos los gráficos."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        margin=dict(t=60, l=10, r=10, b=10),
    )
    return fig


def mostrar(fig):
    st.plotly_chart(estilizar(fig), width="stretch")


# =========================================================
# CARGA DE DATOS (archivo agregado por hora, liviano)
# =========================================================
@st.cache_data
def cargar_datos():
    df = pd.read_csv("data/consumo_horario.csv", parse_dates=["Datetime"])
    # kWh de cada hora = potencia media (kW) x horas con datos
    df["Energia_kWh"] = df["Potencia_media"] * df["Minutos"] / 60
    df["Hora"] = df["Datetime"].dt.hour
    df["DiaNum"] = df["Datetime"].dt.dayofweek
    df["Dia"] = df["DiaNum"].map(dict(enumerate(DIAS)))
    df["Mes"] = df["Datetime"].dt.month
    df["Estacion"] = df["Mes"].map(MAPA_ESTACION)
    df["TipoDia"] = df["DiaNum"].ge(5).map({True: "Fin de semana", False: "Día laboral"})
    return df


def potencia_por(d, clave):
    """Potencia media (kW) agrupada, ponderada por los minutos con datos."""
    g = d.groupby(clave, observed=True).agg(
        E=("Energia_kWh", "sum"), M=("Minutos", "sum")
    ).reset_index()
    g["Potencia_kW"] = g["E"] / (g["M"] / 60)
    return g


def circuitos_por_minuto(d, clave=None):
    """Consumo medio por minuto (Wh/min) de cada circuito."""
    cols = list(CIRCUITOS.keys())
    if clave is None:
        return d[cols].sum() / d["Minutos"].sum()
    g = d.groupby(clave)[cols + ["Minutos"]].sum()
    g[cols] = g[cols].div(g["Minutos"], axis=0)
    return g[cols]


df_all = cargar_datos()

# =========================================================
# SIDEBAR: filtro de fechas + información
# =========================================================
f_min = df_all["Datetime"].min().date()
f_max = df_all["Datetime"].max().date()

# Atajos: todo el período + un año por opción (se marcan los años incompletos)
opciones = {"Todo el período": (f_min, f_max)}
for anio in sorted(df_all["Datetime"].dt.year.unique()):
    anio = int(anio)
    ini = max(f_min, date(anio, 1, 1))
    fin_anio = min(f_max, date(anio, 12, 31))
    parcial = ini > date(anio, 1, 1) or fin_anio < date(anio, 12, 31)
    opciones[f"{anio} (parcial)" if parcial else str(anio)] = (ini, fin_anio)
opciones["Personalizado"] = None

with st.sidebar:
    st.header("🗓️ Filtro de fechas")
    eleccion = st.selectbox("Período", list(opciones.keys()))
    if eleccion == "Personalizado":
        rango = st.date_input(
            "Rango de análisis",
            value=(f_min, f_max),
            min_value=f_min,
            max_value=f_max,
        )
    else:
        rango = opciones[eleccion]
        st.caption(f"{rango[0]:%Y-%m-%d} a {rango[1]:%Y-%m-%d}")

if not isinstance(rango, (tuple, list)) or len(rango) != 2:
    st.info("Selecciona la fecha de inicio y la fecha de fin en el panel lateral.")
    st.stop()

inicio = pd.Timestamp(rango[0])
fin = pd.Timestamp(rango[1]) + pd.Timedelta(days=1)
df = df_all[(df_all["Datetime"] >= inicio) & (df_all["Datetime"] < fin)]

if df.empty:
    st.warning("No hay datos en el rango seleccionado.")
    st.stop()

with st.sidebar:
    st.header("⚙️ Información del Dataset")
    lecturas = int(df["Minutos"].sum())
    st.markdown(f"""
        <div style="
            background-color: rgba(245, 158, 11, 0.12);
            border-left: 4px solid #f59e0b;
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 16px;
            font-size: 1rem;
        ">
            <ul style="margin: 0; padding-left: 18px; color: #f3f4f6;">
                <li><b>Fuente:</b> UCI Household Power Consumption</li>
                <li><b>Lecturas originales:</b> {lecturas:,} (1 por minuto)</li>
                <li><b>Período:</b> {df['Datetime'].min():%Y-%m-%d} a {df['Datetime'].max():%Y-%m-%d}</li>
                <li><b>Vista:</b> agregada por hora</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)

# =========================================================
# CUERPO PRINCIPAL: Título + KPIs
# =========================================================
st.title("⚡ Dashboard de Consumo Energético Residencial")
st.caption("Análisis de Patrones y Eficiencia Energética")

consumo_total_kwh = df["Energia_kWh"].sum()
promedio_kw = consumo_total_kwh / (df["Minutos"].sum() / 60)
pico_max_kw = df["Potencia_max"].max()
voltaje_prom = (df["Voltaje_medio"] * df["Minutos"]).sum() / df["Minutos"].sum()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Consumo Est. Total", f"{consumo_total_kwh:,.0f} kWh")
with col2:
    st.metric("Potencia Promedio", f"{promedio_kw:.3f} kW")
with col3:
    st.metric("Pico de Potencia", f"{pico_max_kw:.2f} kW")
with col4:
    st.metric("Voltaje Promedio", f"{voltaje_prom:.0f} V")

st.markdown("---")

# =========================================================
# PESTAÑAS
# =========================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1. Desglose por Circuito",
    "2. Patrones Temporales",
    "3. Evolución Histórica",
    "4. Insights y Recomendaciones",
    "5. Explora los Datos",
])

# ---------------------------------------------------------
# TAB 1: DESGLOSE POR CIRCUITO
# ---------------------------------------------------------
with tab1:
    st.header("Distribución del Consumo por Circuito")

    medias = circuitos_por_minuto(df)
    pct = medias / medias.sum() * 100

    st.write(
        f"Hallazgo principal: el **{pct['Otros_Wh']:.1f}%** del consumo corresponde a circuitos "
        f"no medidos directamente (Otros), y el Calentador/AC (Sub 3) representa el "
        f"**{pct['Sub3_Wh']:.1f}%**."
    )

    df_circuits = pd.DataFrame({
        "Circuito": [CIRCUITOS[c] for c in medias.index],
        "Consumo_Wh": medias.values,
    })

    c1, c2 = st.columns(2)
    with c1:
        fig_bar = px.bar(
            df_circuits, x="Circuito", y="Consumo_Wh", color="Circuito",
            color_discrete_map=COLOR_CIRCUITO, text_auto=".2f",
            title="Consumo Promedio por Circuito (Wh por minuto)",
        )
        fig_bar.update_layout(showlegend=False, yaxis_title="Wh por minuto")
        mostrar(fig_bar)
    with c2:
        fig_pie = px.pie(
            df_circuits, names="Circuito", values="Consumo_Wh",
            color="Circuito", color_discrete_map=COLOR_CIRCUITO,
            title="Distribución Porcentual (%)",
        )
        mostrar(fig_pie)

    # Patrón horario por circuito
    por_hora = circuitos_por_minuto(df, "Hora").rename(columns=CIRCUITOS)
    por_hora = por_hora.reset_index().melt(
        id_vars="Hora", var_name="Circuito", value_name="Wh_min"
    )
    fig_circ_hora = px.line(
        por_hora, x="Hora", y="Wh_min", color="Circuito",
        color_discrete_map=COLOR_CIRCUITO, markers=True,
        title="Patrón Horario por Circuito (Wh por minuto)",
    )
    fig_circ_hora.update_layout(yaxis_title="Wh por minuto")
    fig_circ_hora.update_xaxes(dtick=1)
    mostrar(fig_circ_hora)

# ---------------------------------------------------------
# TAB 2: PATRONES TEMPORALES
# ---------------------------------------------------------
with tab2:
    st.header("Patrones de Consumo por Hora, Día y Estación")

    # 1. Por hora, separando días laborales y fines de semana
    hora_tipo = potencia_por(df, ["Hora", "TipoDia"])
    fig_hour = px.line(
        hora_tipo, x="Hora", y="Potencia_kW", color="TipoDia", markers=True,
        title="Consumo Promedio por Hora del Día (kW)",
    )
    fig_hour.update_layout(yaxis_title="kW", legend_title_text="")
    fig_hour.update_xaxes(dtick=1)
    mostrar(fig_hour)

    # 2. Por día de la semana y por estación
    c1, c2 = st.columns(2)
    with c1:
        daily_avg = potencia_por(df, "Dia")
        fig_day = px.bar(
            daily_avg, x="Dia", y="Potencia_kW", text_auto=".2f",
            category_orders={"Dia": DIAS},
            title="Consumo Promedio por Día de la Semana (kW)",
        )
        fig_day.update_layout(xaxis_title="", yaxis_title="kW")
        mostrar(fig_day)
    with c2:
        est = potencia_por(df, "Estacion")
        fig_est = px.bar(
            est, x="Estacion", y="Potencia_kW", color="Estacion", text_auto=".2f",
            color_discrete_map=COLOR_ESTACION,
            category_orders={"Estacion": ESTACIONES},
            title="Consumo Promedio por Estación del Año (kW)",
        )
        fig_est.update_layout(showlegend=False, xaxis_title="", yaxis_title="kW")
        mostrar(fig_est)

    # 3. Por mes
    mes = potencia_por(df, "Mes")
    mes["MesNombre"] = mes["Mes"].map(lambda m: MESES[m - 1])
    fig_mes = px.line(
        mes, x="MesNombre", y="Potencia_kW", markers=True,
        category_orders={"MesNombre": MESES},
        title="Consumo Promedio por Mes (kW)",
    )
    fig_mes.update_layout(xaxis_title="", yaxis_title="kW")
    mostrar(fig_mes)

    # 4. Heatmap hora x día
    hm = potencia_por(df, ["Dia", "Hora"]).pivot(
        index="Dia", columns="Hora", values="Potencia_kW"
    ).reindex(DIAS)
    fig_hm = px.imshow(
        hm, aspect="auto", color_continuous_scale="RdYlGn_r",
        labels=dict(x="Hora del día", y="", color="kW"),
        title="Consumo Promedio por Hora y Día de la Semana (kW)",
    )
    fig_hm.update_xaxes(dtick=1)
    mostrar(fig_hm)

# ---------------------------------------------------------
# TAB 3: EVOLUCIÓN HISTÓRICA
# ---------------------------------------------------------
with tab3:
    st.header("Evolución Histórica del Consumo")

    gran = st.radio(
        "Granularidad", ["Diaria", "Semanal", "Mensual"], index=1, horizontal=True
    )
    freq = {"Diaria": "D", "Semanal": "W", "Mensual": "MS"}[gran]
    titulo = {
        "Diaria": "Consumo Diario Promedio (kW)",
        "Semanal": "Consumo Semanal Promedio (kW)",
        "Mensual": "Consumo Mensual Promedio (kW)",
    }[gran]
    etiqueta = {"Diaria": "Diario", "Semanal": "Semanal", "Mensual": "Mensual"}[gran]

    serie = df.set_index("Datetime").resample(freq).agg(
        E=("Energia_kWh", "sum"), M=("Minutos", "sum")
    )
    serie[etiqueta] = serie["E"] / (serie["M"] / 60)   # periodos sin datos -> NaN
    columnas_y = [etiqueta]
    if gran == "Diaria":
        serie["Media móvil 7 días"] = serie[etiqueta].rolling(7, min_periods=3).mean()
        columnas_y.append("Media móvil 7 días")

    fig_time = px.line(
        serie.reset_index(), x="Datetime", y=columnas_y,
        markers=(gran == "Mensual"), title=titulo,
    )
    fig_time.update_layout(xaxis_title="", yaxis_title="kW", legend_title_text="")
    mostrar(fig_time)

    sin_datos = int((serie["M"] == 0).sum())
    if sin_datos > 0:
        periodo = {"Diaria": "día(s)", "Semanal": "semana(s)", "Mensual": "mes(es)"}[gran]
        st.caption(
            f"ℹ️ Hay {sin_datos} {periodo} sin ninguna lectura válida en este rango; "
            "se ven como huecos en la línea."
        )

# ---------------------------------------------------------
# TAB 4: INSIGHTS Y RECOMENDACIONES (cifras calculadas en vivo)
# ---------------------------------------------------------
with tab4:
    st.header("Insights Clave")

    # Hora pico y valle
    h = potencia_por(df, "Hora")
    pico = h.loc[h["Potencia_kW"].idxmax()]
    valle = h.loc[h["Potencia_kW"].idxmin()]
    ratio_pico = pico["Potencia_kW"] / valle["Potencia_kW"]

    # Franja 19:00 - 22:00
    franja = df[df["Hora"].isin([19, 20, 21])]["Energia_kWh"].sum() / consumo_total_kwh * 100

    # Fin de semana vs laboral
    tipo = potencia_por(df, "TipoDia").set_index("TipoDia")["Potencia_kW"]
    dif_fds = None
    if {"Fin de semana", "Día laboral"} <= set(tipo.index):
        dif_fds = (tipo["Fin de semana"] / tipo["Día laboral"] - 1) * 100

    # Invierno vs verano
    est_s = potencia_por(df, "Estacion").set_index("Estacion")["Potencia_kW"]
    ratio_est = None
    if {"Invierno", "Verano"} <= set(est_s.index):
        ratio_est = est_s["Invierno"] / est_s["Verano"]

    # Consumo base en la madrugada (posible standby)
    madr = df[df["Hora"].between(2, 5)]
    base_kw = madr["Potencia_media"].mul(madr["Minutos"]).sum() / madr["Minutos"].sum() if len(madr) else None

    i1, i2, i3 = st.columns(3)
    with i1:
        st.metric("Hora pico", f"{int(pico['Hora']):02d}:00",
                  f"{ratio_pico:.1f}x la hora más baja", delta_color="off")
    with i2:
        st.metric("Energía entre 19:00 y 22:00", f"{franja:.1f}%")
    with i3:
        if base_kw is not None:
            st.metric("Consumo base (2-5 am)", f"{base_kw:.2f} kW")

    st.markdown("### 🔍 Qué dicen los datos")
    puntos = [
        f"El pico de consumo ocurre a las **{int(pico['Hora']):02d}:00** "
        f"({pico['Potencia_kW']:.2f} kW), unas **{ratio_pico:.1f} veces** el valle de las "
        f"{int(valle['Hora']):02d}:00 ({valle['Potencia_kW']:.2f} kW).",
        f"Entre las 19:00 y las 22:00 se concentra el **{franja:.1f}%** de la energía total.",
        f"Los circuitos no medidos (Otros) son el **{pct['Otros_Wh']:.1f}%** del consumo y el "
        f"calentador/AC (Sub 3) el **{pct['Sub3_Wh']:.1f}%**.",
    ]
    if dif_fds is not None:
        puntos.append(
            f"Los fines de semana el consumo promedio es **{dif_fds:+.1f}%** respecto a los días laborales."
        )
    if ratio_est is not None:
        puntos.append(
            f"El invierno consume **{ratio_est:.2f} veces** lo que consume el verano."
        )
    if base_kw is not None:
        puntos.append(
            f"De madrugada (2-5 am) el hogar mantiene un consumo base de **{base_kw:.2f} kW**, "
            "señal de cargas permanentes o en standby."
        )
    for p in puntos:
        st.markdown(f"- {p}")

    st.markdown("### 💡 Recomendaciones")
    st.markdown("""
- **Calentador:** programarlo y apagarlo cuando no se necesite; es el circuito medido de mayor demanda.
- **Cargas fantasma:** desconectar equipos en standby o usar regletas con interruptor.
- **Franja nocturna:** mover lavado, planchado y cocina intensiva fuera de las 19:00–22:00.
- **Automatización:** temporizadores y monitoreo para controlar horarios de uso.
    """)

# ---------------------------------------------------------
# TAB 5: DATOS
# ---------------------------------------------------------
with tab5:
    st.header("Datos Agregados por Hora")
    columnas = [
        "Datetime", "Potencia_media", "Potencia_max", "Voltaje_medio",
        "Sub1_Wh", "Sub2_Wh", "Sub3_Wh", "Otros_Wh", "Minutos",
    ]
    tabla = df[columnas]

    c_info, c_btn = st.columns([3, 1], vertical_alignment="center")
    with c_info:
        st.caption(
            f"{len(tabla):,} filas en el rango seleccionado (una por hora). "
            "Desplázate dentro de la tabla para ver todas."
        )
    with c_btn:
        st.download_button(
            "⬇️ Descargar CSV",
            data=tabla.to_csv(index=False).encode("utf-8"),
            file_name="consumo_horario_filtrado.csv",
            mime="text/csv",
        )

    st.dataframe(
        tabla,
        width="stretch",
        height=450,
        hide_index=True,
        column_config={
            "Datetime": st.column_config.DatetimeColumn("Fecha y hora", format="YYYY-MM-DD HH:mm"),
            "Potencia_media": st.column_config.NumberColumn("Potencia media (kW)", format="%.3f"),
            "Potencia_max": st.column_config.NumberColumn("Potencia máx. (kW)", format="%.3f"),
            "Voltaje_medio": st.column_config.NumberColumn("Voltaje medio (V)", format="%.1f"),
            "Sub1_Wh": st.column_config.NumberColumn("Cocina (Wh)", format="%.0f"),
            "Sub2_Wh": st.column_config.NumberColumn("Lavandería (Wh)", format="%.0f"),
            "Sub3_Wh": st.column_config.NumberColumn("Calentador/AC (Wh)", format="%.0f"),
            "Otros_Wh": st.column_config.NumberColumn("Otros (Wh)", format="%.0f"),
            "Minutos": st.column_config.NumberColumn("Minutos con datos", format="%d"),
        },
    )

    with st.expander("ℹ️ ¿Qué significa cada columna?"):
        st.markdown("""
- **Potencia media / máx. (kW):** promedio y valor máximo de la potencia activa dentro de la hora.
- **Voltaje medio (V):** promedio del voltaje durante la hora.
- **Cocina, Lavandería y Calentador/AC (Wh):** energía consumida en la hora por cada sub-medidor.
- **Otros (Wh):** energía no medida por los sub-medidores (potencia global menos los tres circuitos).
- **Minutos con datos:** lecturas válidas dentro de la hora (60 = hora completa).
        """)