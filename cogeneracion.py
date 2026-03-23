import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Cogeneración – Análisis Técnico y Económico 2026", layout="wide")

st.logo(
    "logo.png",           # ← nombre exacto de tu archivo
    size="large",                     # prueba "small", "medium" o "large"
    link="https://www.luxem.mx"        # opcional
)
# ────────────────────────────────────────────────
# FUNCIONES DE CÁLCULO
# ────────────────────────────────────────────────

def calcular_energetico(P_el, η_el, η_rec, Q_dem, h_op, PCI):
    PCI_MW_por_Nm3h = PCI / 3600.0
    Q_comb = P_el / η_el if η_el > 0 else 0
    Q_rec_teor = Q_comb * (1 - η_el) * η_rec
    Q_util = min(Q_rec_teor, Q_dem)
    P_perd = Q_comb - P_el - Q_util
    η_global = (P_el + Q_util) / Q_comb if Q_comb > 0 else 0

    V_Nm3h = Q_comb / PCI_MW_por_Nm3h if PCI_MW_por_Nm3h > 0 else 0
    V_anual = V_Nm3h * h_op

    E_el_an_MWh = P_el * h_op
    Q_util_an_MWh = Q_util * h_op
    E_comb_an_MWh = Q_comb * h_op

    return {
        'Q_comb': Q_comb, 'Q_rec_teor': Q_rec_teor, 'Q_util': Q_util, 'P_perd': P_perd,
        'η_global': η_global, 'V_Nm3h': V_Nm3h, 'V_anual': V_anual,
        'E_el_an_MWh': E_el_an_MWh, 'Q_util_an_MWh': Q_util_an_MWh, 'E_comb_an_MWh': E_comb_an_MWh
    }

def calcular_economico(energetico, precio_cfe_usd_kwh, precio_gas_usd_mwh, eta_caldera, inversion_inicial_usd):
    costo_cfe = energetico['E_el_an_MWh'] * 1000 * precio_cfe_usd_kwh
    costo_gas_chp = energetico['E_comb_an_MWh'] * precio_gas_usd_mwh
    costo_caldera = (energetico['Q_util_an_MWh'] / eta_caldera) * precio_gas_usd_mwh if eta_caldera > 0 else 0

    ahorro_calor = costo_caldera - (energetico['Q_util_an_MWh'] * precio_gas_usd_mwh)
    ahorro_neto = costo_cfe + ahorro_calor - costo_gas_chp
    costo_base = costo_cfe + costo_caldera
    ahorro_pct = (ahorro_neto / costo_base * 100) if costo_base > 0 else 0

    if ahorro_neto > 0:
        payback = inversion_inicial_usd / ahorro_neto
        payback_str = f"{payback:.1f} años"
        payback_color = "normal" if payback < 5 else "inverse"
    else:
        payback_str = "No rentable"
        payback_color = "inverse"

    return {
        'costo_cfe': costo_cfe, 'costo_gas_chp': costo_gas_chp, 'costo_caldera': costo_caldera,
        'ahorro_calor': ahorro_calor, 'ahorro_neto': ahorro_neto, 'ahorro_pct': ahorro_pct,
        'payback_str': payback_str, 'payback_color': payback_color, 'costo_base': costo_base
    }

def calcular_emisiones(E_el_an_MWh, E_comb_an_MWh):
    f_sen = 0.444
    f_chp = 0.200
    return E_el_an_MWh * f_sen, E_comb_an_MWh * f_chp, (E_el_an_MWh * f_sen - E_comb_an_MWh * f_chp)

# ────────────────────────────────────────────────
# SIDEBAR
# ────────────────────────────────────────────────

with st.sidebar:
    st.header("Parámetros de diseño")
    P_el = st.slider("Potencia eléctrica nominal (MW)", 0.5, 50.0, 5.0, 0.5)
    η_el_pct = st.slider("Eficiencia eléctrica (%)", 28.0, 45.0, 35.0)
    η_el = η_el_pct / 100.0
    η_rec_pct = st.slider("Eficiencia de recuperación térmica (%)", 65.0, 95.0, 82.0)
    η_rec = η_rec_pct / 100.0
    Q_dem = st.number_input("Demanda térmica útil (MW)", 1.0, 150.0, 10.0, step=0.5)
    h_op = st.number_input("Horas operación anual (h/año)", 4000, 8760, 7500, step=500)
    PCI = st.number_input("PCI gas natural (MJ/Nm³)", 30.0, 42.0, 36.5, 0.1)

    st.subheader("Datos económicos")
    precio_cfe = st.number_input("Tarifa CFE evitada (USD/kWh)", 0.08, 0.18, 0.125, 0.005)
    precio_gas_mmbtu = st.number_input("Precio gas natural (USD/MMBtu)", 3.0, 10.0, 5.0, 0.1)
    eta_caldera_pct = st.slider("Eficiencia caldera convencional (%)", 75.0, 90.0, 82.0)
    eta_caldera = eta_caldera_pct / 100.0

    st.subheader("Inversión estimada (valores de mercado 2026)")
    costo_por_mw = st.slider(
        "Costo por MW instalado (USD/MW) – CHP gas natural",
        800000, 2500000, 1500000, step=50000,
        help="Rango realista de mercado México 2026"
    )
    inversion_inicial_usd = P_el * costo_por_mw

    st.session_state.precio_gas_mmbtu = precio_gas_mmbtu

# ────────────────────────────────────────────────
# CÁLCULOS
# ────────────────────────────────────────────────

energetico = calcular_energetico(P_el, η_el, η_rec, Q_dem, h_op, PCI)
precio_gas_usd_mwh = st.session_state.precio_gas_mmbtu / 0.293
economico = calcular_economico(energetico, precio_cfe, precio_gas_usd_mwh, eta_caldera, inversion_inicial_usd)
em_sen, em_chp, em_evit = calcular_emisiones(energetico['E_el_an_MWh'], energetico['E_comb_an_MWh'])

# ────────────────────────────────────────────────
# ALERTAS
# ────────────────────────────────────────────────

if energetico['Q_rec_teor'] < Q_dem:
    st.warning(f"⚠️ Recuperación térmica limitante: solo se aprovechan {energetico['Q_util']:.1f} MW de {Q_dem:.1f} MW demandados.")

if economico['ahorro_neto'] < 0:
    st.error(f"⚠️ Pérdida neta anual: ${economico['ahorro_neto']:,.0f}")

if η_el > 0.40:
    st.warning("⚠️ Eficiencia eléctrica > 40% → temperatura de gases más baja → recuperación térmica real posiblemente menor. Validar con fabricante.")

# ────────────────────────────────────────────────
# TABS
# ────────────────────────────────────────────────

tab_dashboard, tab_balance, tab_econ, tab_emis, tab_detalle, tab_sens = st.tabs([
    "Dashboard", "Balance Energético", "Económico", "Emisiones", "Cálculos Detallados", "Sensibilidad"
])

# ==================== DASHBOARD ====================
with tab_dashboard:
    st.title("Dashboard – Análisis de Cogeneración 2026")

    cols1 = st.columns(4)
    cols1[0].metric("Electricidad anual", f"{energetico['E_el_an_MWh']:,.0f} MWh")
    cols1[1].metric("Calor útil anual", f"{energetico['Q_util_an_MWh']:,.0f} MWh")
    cols1[2].metric("Ahorro neto anual", f"${economico['ahorro_neto']:,.0f}", delta=f"{economico['ahorro_pct']:.1f}%")
    cols1[3].metric("Eficiencia global", f"{energetico['η_global']*100:.1f}%")

    cols2 = st.columns(2)
    cols2[0].metric(
        "Requerimiento gas natural anual",
        f"{energetico['V_anual']:,.0f} Nm³/año",
        help="Tasado solo en costo de la molécula (sin transporte ni distribución)"
    )
    cols2[1].metric(
        "Payback Simple (sin DCF)",
        economico['payback_str'],
        delta_color=economico['payback_color']
    )

    # Gráfica histórica Henry Hub
    st.markdown("---")
    st.subheader("Histórico del Precio del Gas Natural – Henry Hub")

    archivo_excel = "Henry Hub.xls"

    if not os.path.exists(archivo_excel):
        st.error(f"No se encontró '{archivo_excel}' en la carpeta. Colócalo junto a este .py.")
    else:
        try:
            df_henry = pd.read_excel(archivo_excel)
            df_henry.columns = df_henry.columns.str.strip().str.lower()

            col_fecha = next((c for c in df_henry.columns if "date" in c or "fecha" in c), None)
            col_precio = next((c for c in df_henry.columns if "price" in c or "precio" in c or "dollars" in c or "btu" in c), None)

            if not col_fecha or not col_precio:
                st.error("No se detectaron columnas de fecha y precio. Verifica el Excel.")
            else:
                df_henry[col_fecha] = pd.to_datetime(df_henry[col_fecha], errors='coerce')
                df_henry[col_precio] = pd.to_numeric(df_henry[col_precio], errors='coerce')
                df_henry = df_henry.dropna(subset=[col_fecha, col_precio]).sort_values(col_fecha)

                fig_henry = go.Figure()
                fig_henry.add_trace(go.Scatter(
                    x=df_henry[col_fecha],
                    y=df_henry[col_precio],
                    mode='lines',
                    name='Henry Hub Spot Price',
                    line=dict(color='royalblue')
                ))

                fig_henry.update_layout(
                    title="Evolución histórica Henry Hub (1997–2026)",
                    xaxis_title="Fecha",
                    yaxis_title="Precio (USD/MMBtu)",
                    height=500,
                    hovermode="x unified",
                    template="plotly_white"
                )

                st.plotly_chart(fig_henry, use_container_width=True)

                st.caption(f"Fuente: {archivo_excel}")
                st.caption(f"Período: {df_henry[col_fecha].min().strftime('%Y-%m')} → {df_henry[col_fecha].max().strftime('%Y-%m')}")
                st.caption(f"Precio promedio histórico: ${df_henry[col_precio].mean():.2f} USD/MMBtu")

        except Exception as e:
            st.error(f"Error al leer el Excel:\n{str(e)}")

# ==================== BALANCE ENERGÉTICO ====================
with tab_balance:
    st.subheader("Diagrama Sankey – Balance Energético")
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=40,
            thickness=30,
            line=dict(color="black", width=0.5),
            label=[
                f"Combustible entrada\n{energetico['Q_comb']:.1f} MW",
                f"Electricidad\n{P_el:.1f} MW",
                f"Calor útil\n{energetico['Q_util']:.1f} MW",
                f"Pérdidas\n{energetico['P_perd']:.1f} MW"
            ],
            color=["#5c8be6", "#2ecc71", "#f39c12", "#e74c3c"]
        ),
        link=dict(
            source=[0, 0, 0],
            target=[1, 2, 3],
            value=[P_el, energetico['Q_util'], energetico['P_perd']],
            color=["rgba(92,139,230,0.4)", "rgba(46,204,113,0.4)", "rgba(231,76,60,0.4)"]
        )
    )])
    fig.update_layout(
        title_text="Flujos energéticos (MW) – Combustible → Electricidad + Calor + Pérdidas",
        font_size=14,
        height=650
    )
    st.plotly_chart(fig, use_container_width=True)

# ==================== ECONÓMICO ====================
with tab_econ:
    st.subheader("Comparación económica")
    
    # Usamos 3 columnas para dar más espacio y equilibrio visual
    col_izq, col_der = st.columns([1, 1.2])  # un poco más ancho la derecha
    
    with col_izq:
        st.markdown("**Sin cogeneración (escenario base)**")
        st.metric("Costo CFE", f"${economico['costo_cfe']:,.0f}")
        st.metric("Costo caldera convencional", f"${economico['costo_caldera']:,.0f}")
        st.metric("**Total base**", f"${economico['costo_base']:,.0f}")
    
    with col_der:
        st.markdown("**Con cogeneración (CHP)**")
        st.metric("Costo gas CHP", f"${economico['costo_gas_chp']:,.0f}")
        st.metric("**Ahorro neto anual**", 
                  f"${economico['ahorro_neto']:,.0f}",
                  delta=f"{economico['ahorro_pct']:.1f}% vs base")
        
        # ← Aquí agregamos el Payback
        st.metric(
            "**Payback Simple**",
            economico['payback_str'],
            delta_color=economico['payback_color']  # ya lo tienes: "normal" o "inverse"
        )
    
    # Opcional: una nota pequeña al final
    st.caption("Payback simple = Inversión inicial / Ahorro neto anual (sin considerar valor del dinero en el tiempo, inflación ni impuestos)")
# ==================== EMISIONES ====================
with tab_emis:
    st.subheader("Emisiones de CO₂")
    cols = st.columns(3)
    cols[0].metric("Sin CHP (SEN)", f"{em_sen:,.0f} t/año")
    cols[1].metric("Con CHP", f"{em_chp:,.0f} t/año")
    cols[2].metric("Evitadas", f"{em_evit:,.0f} t/año")

# ==================== CÁLCULOS DETALLADOS ====================
with tab_detalle:
    st.title("📐 Cálculos Detallados – Paso a Paso")
    st.caption("Cada paso con ecuación + sustitución numérica completa + resultado.")

    with st.expander("1. Balance Energético (1ª Ley)", expanded=True):
        st.latex(r"Q_{\text{comb}} = P_{\text{el}} + Q_{\text{util}} + P_{\text{pérdidas}}")
        st.write(f"**Combustible entrante:** {energetico['Q_comb']:.2f} MW")
        st.write(f"→ Electricidad producida: {P_el:.2f} MW")
        st.write(f"→ Calor útil aprovechado: {energetico['Q_util']:.2f} MW")
        st.write(f"→ Pérdidas térmicas: {energetico['P_perd']:.2f} MW")
        st.success(f"**Balance cerrado:** {energetico['Q_comb']:.2f} = {P_el:.2f} + {energetico['Q_util']:.2f} + {energetico['P_perd']:.2f} MW")

    with st.expander("2. Potencia térmica del combustible (Q_comb)"):
        st.latex(r"Q_{\text{comb}} = \frac{P_{\text{el}}}{\eta_{\text{el}}}")
        st.write(f"**Entrada:** P_el = {P_el:.2f} MW, η_el = {η_el:.3f}")
        st.latex(r"\Rightarrow Q_{\text{comb}} = \frac{" + f"{P_el:.2f}" + r"}{" + f"{η_el:.3f}" + r"} = \boxed{" + f"{energetico['Q_comb']:.2f}" + r"} \ \text{MW}")
        st.success(f"**Resultado: {energetico['Q_comb']:.2f} MW**")

    with st.expander("3. Calor recuperable teórico y calor útil"):
        st.latex(r"Q_{\text{rec,teor}} = Q_{\text{comb}} \times (1 - \eta_{\text{el}}) \times \eta_{\text{rec}}")
        st.write(f"**Sustitución:** {energetico['Q_comb']:.2f} × {1-η_el:.3f} × {η_rec:.3f} = {energetico['Q_rec_teor']:.2f} MW")
        st.latex(r"Q_{\text{util}} = \min(" + f"{energetico['Q_rec_teor']:.2f}" + r", " + f"{Q_dem:.2f}" + r") = " + f"{energetico['Q_util']:.2f} MW")
        porcentaje_cobertura = (energetico['Q_util'] / Q_dem * 100) if Q_dem > 0 else 0
        st.latex(r"\frac{Q_{\text{util}}}{Q_{\text{dem}}} \times 100 = \boxed{" + f"{porcentaje_cobertura:.1f}" + r"\%}")
        st.success(f"**Calor útil: {energetico['Q_util']:.2f} MW ({porcentaje_cobertura:.1f}% de la demanda)**")

    with st.expander("4. Eficiencia global de la cogeneración", expanded=False):
        st.latex(r"\eta_{\text{global}} = \frac{P_{\text{el}} + Q_{\text{util}}}{Q_{\text{comb}}}")
        st.write("Representa la fracción del combustible que se convierte en energía útil (eléctrica + térmica aprovechada).")
    
        st.write(f"- Potencia eléctrica: **{P_el:.2f} MW**")
        st.write(f"- Calor útil aprovechado: **{energetico['Q_util']:.2f} MW**")
        st.write(f"- Energía útil total: {P_el + energetico['Q_util']:.2f} MW")
        st.write(f"- Combustible entrante: **{energetico['Q_comb']:.2f} MW**")
    
        st.latex(
         r"\eta_{\text{global}} = \frac{" + 
         f"{P_el:.2f} + {energetico['Q_util']:.2f}" + 
         r"}{" + 
         f"{energetico['Q_comb']:.2f}" + 
         r"} = \frac{" + 
         f"{P_el + energetico['Q_util']:.2f}" + 
         r"}{" + 
         f"{energetico['Q_comb']:.2f}" + 
         r"} = \boxed{" + 
         f"{energetico['η_global']*100:.1f}" + 
         r"\%}"
    )
    
    if energetico['η_global'] > 0.80:
        st.success(f"**Eficiencia global: {energetico['η_global']*100:.1f}%** → Excelente rendimiento (típico de CHP de alta calidad)")
    elif energetico['η_global'] > 0.70:
        st.info(f"**Eficiencia global: {energetico['η_global']*100:.1f}%** → Muy buena (estándar en muchas aplicaciones industriales)")
    else:
        st.warning(f"**Eficiencia global: {energetico['η_global']*100:.1f}%** → Revisar parámetros de eficiencia o recuperación térmica")

    with st.expander("4. Requerimiento de gas natural (Nm³)"):
        st.markdown("**Nota:** Tasado solo en costo de la molécula (sin transporte ni distribución).")
        st.latex(r"\dot{V}_{\text{Nm}^3/\text{h}} = \frac{Q_{\text{comb}}}{\text{PCI}/3600}")
        st.write(f"**Sustitución:** {energetico['Q_comb']:.2f} / ({PCI:.1f}/3600) = {energetico['V_Nm3h']:,.0f} Nm³/h")
        st.latex(r"V_{\text{anual}} = " + f"{energetico['V_Nm3h']:,.0f}" + r" \times " + f"{h_op:,.0f}" + r" = \boxed{" + f"{energetico['V_anual']:,.0f}" + r"} \ \text{Nm³/año}")
        st.success(f"**Gas anual: {energetico['V_anual']:,.0f} Nm³/año**")

    with st.expander("5. Costo anual electricidad CFE"):
        st.latex(r"\text{Costo CFE} = E_{\text{el anual}} \times 1000 \times \text{precio CFE}")
        st.write(f"**Sustitución:** {energetico['E_el_an_MWh']:,.0f} × 1000 × {precio_cfe:.4f} = ${economico['costo_cfe']:,.0f}")
        st.success(f"**Costo CFE: ${economico['costo_cfe']:,.0f}**")

    with st.expander("6. Costo anual del gas en CHP"):
        st.markdown("**Conversión precio**")
        st.latex(r"\text{Precio USD/MWh} = \frac{" + f"{st.session_state.precio_gas_mmbtu:.2f}" + r"}{0.293} = " + f"{precio_gas_usd_mwh:.3f}")
        st.markdown("**Costo total**")
        st.latex(r"\text{Costo gas CHP} = E_{\text{comb anual}} \times \text{precio USD/MWh}")
        st.write(f"**Sustitución:** {energetico['E_comb_an_MWh']:,.0f} × {precio_gas_usd_mwh:.3f} = ${economico['costo_gas_chp']:,.0f}")
        st.success(f"**Costo gas CHP: ${economico['costo_gas_chp']:,.0f}**")

    with st.expander("7. Costo caldera convencional"):
        st.latex(r"\text{Costo caldera} = \frac{Q_{\text{util anual}}}{\eta_{\text{caldera}}} \times \text{precio gas}")
        st.write(f"**Sustitución:** {energetico['Q_util_an_MWh']:,.0f} / {eta_caldera:.3f} × {precio_gas_usd_mwh:.3f} = ${economico['costo_caldera']:,.0f}")
        st.success(f"**Costo caldera: ${economico['costo_caldera']:,.0f}**")

    with st.expander("8. Ahorro neto anual"):
        st.latex(r"\text{Ahorro neto} = \text{CFE} + \text{Caldera base} - \text{Gas CHP}")
        st.write(f"**Sustitución:** {economico['costo_cfe']:,.0f} + {economico['costo_caldera']:,.0f} - {economico['costo_gas_chp']:,.0f} = ${economico['ahorro_neto']:,.0f}")
        st.success(f"**Ahorro neto: ${economico['ahorro_neto']:,.0f}**")

    with st.expander("9. Payback Simple (sin DCF)"):
        st.markdown("**Inversión total**")
        st.latex(r"\text{Inversión} = P_{\text{el}} \times \text{Costo por MW}")
        st.write(f"**Sustitución:** {P_el:.1f} × {costo_por_mw:,.0f} = ${inversion_inicial_usd:,.0f}")
        st.latex(r"\Rightarrow \text{Inversión total} = \boxed{" + f"${inversion_inicial_usd:,.0f}" + r"}")
        st.markdown("**Payback Simple**")
        st.latex(r"\text{Payback} = \frac{\text{Inversión}}{\text{Ahorro neto anual}}")
        st.write(f"**Sustitución:** {inversion_inicial_usd:,.0f} / {economico['ahorro_neto']:,.0f} = {economico['payback_str']}")
        st.success(f"**Payback Simple (sin DCF): {economico['payback_str']}**")
        st.caption("Nota: Payback simple. No considera DCF, inflación ni impuestos.")

    with st.expander("10. Emisiones evitadas"):
        st.latex(r"E_{\text{SEN}} = E_{\text{el anual}} \times 0.444 = " + f"{em_sen:,.0f} t/año")
        st.latex(r"E_{\text{CHP}} = E_{\text{comb anual}} \times 0.200 = " + f"{em_chp:,.0f} t/año")
        st.success(f"**Emisiones evitadas: {em_evit:,.0f} tCO₂/año**")

# ==================== SENSIBILIDAD ====================
with tab_sens:
    st.subheader("Análisis y Proyección del Precio del Gas Natural – 8-10 años")

    archivo_excel = "Henry Hub.xls"

    if not os.path.exists(archivo_excel):
        st.error(f"No se encontró '{archivo_excel}'. Colócalo en la misma carpeta que el .py")
    else:
        try:
            df_henry = pd.read_excel(archivo_excel)
            df_henry.columns = df_henry.columns.str.strip().str.lower()

            col_fecha = next((c for c in df_henry.columns if "date" in c or "fecha" in c or "dia" in c), None)
            col_precio = next((c for c in df_henry.columns if "price" in c or "precio" in c or "dollars" in c or "btu" in c or "spot" in c), None)

            if not col_fecha or not col_precio:
                st.error("No se detectaron columnas de fecha y precio en el Excel.")
            else:
                df_henry[col_fecha] = pd.to_datetime(df_henry[col_fecha], errors='coerce')
                df_henry[col_precio] = pd.to_numeric(df_henry[col_precio], errors='coerce')
                df_henry = df_henry.dropna(subset=[col_fecha, col_precio]).sort_values(col_fecha)

                # ===================== ESTADÍSTICAS HISTÓRICAS =====================
                st.markdown("### Estadísticas Históricas del Henry Hub")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Promedio histórico", f"${df_henry[col_precio].mean():.2f}")
                col2.metric("Mínimo histórico", f"${df_henry[col_precio].min():.2f}")
                col3.metric("Máximo histórico", f"${df_henry[col_precio].max():.2f}")
                col4.metric("Último precio", f"${df_henry[col_precio].iloc[-1]:.2f}")

                # ===================== PROYECCIÓN 2026-2035 =====================
                st.markdown("### Proyección del Precio del Gas (2026-2035)")

                df_hist = df_henry.copy()
                df_hist['year'] = df_hist[col_fecha].dt.year
                df_last10 = df_hist[df_hist['year'] >= 2016]

                x = (df_last10[col_fecha] - df_last10[col_fecha].min()).dt.days.values
                y = df_last10[col_precio].values
                slope, intercept = np.polyfit(x, y, 1)

                dias_totales = (df_last10[col_fecha].iloc[-1] - df_last10[col_fecha].iloc[0]).days
                cagr = (df_last10[col_precio].iloc[-1] / df_last10[col_precio].iloc[0]) ** (1 / (dias_totales / 365.25)) - 1

                ultimo_precio = df_henry[col_precio].iloc[-1]
                años_proy = list(range(2026, 2036))
                proyecciones = []

                for año in años_proy:
                    dias_desde_ultimo = (pd.to_datetime(f"{año}-01-01") - df_henry[col_fecha].iloc[-1]).days
                    tendencia_lineal = ultimo_precio + slope * dias_desde_ultimo

                    optimista = ultimo_precio * (1 + cagr * 0.5) ** (año - 2025)
                    base = ultimo_precio * (1 + cagr) ** (año - 2025)
                    pesimista = ultimo_precio * (1 + cagr * 1.5) ** (año - 2025)

                    proyecciones.append({
                        "Año": año,
                        "Optimista (bajo)": round(optimista, 2),
                        "Base": round(base, 2),
                        "Pesimista (alto)": round(pesimista, 2),
                        "Lineal": round(tendencia_lineal, 2)
                    })

                df_proy = pd.DataFrame(proyecciones)

                st.dataframe(
                    df_proy.style
                        .format({
                            col: "${:,.2f}" for col in df_proy.columns if col != "Año"
                        })
                        .background_gradient(cmap="RdYlGn_r", subset=["Optimista (bajo)", "Base", "Pesimista (alto)", "Lineal"])
                        .set_properties(**{'text-align': 'center'}),
                    use_container_width=True,
                    hide_index=True
                )

                st.caption("Proyección basada en tendencia lineal y CAGR de los últimos 10 años del archivo Henry Hub.xls. Escenarios realistas para México 2026-2035 (sin diferencial local).")

                # ===================== SENSIBILIDAD Precio Gas vs Payback =====================
                st.markdown("---")
                st.subheader("Sensibilidad: Precio del Gas vs Payback Simple")
                st.caption(f"Inversión inicial fija usada: **${inversion_inicial_usd:,.0f}** (basada en {P_el:.1f} MW × ${costo_por_mw:,.0f}/MW)")

                precios_sens = np.linspace(3.0, 12.0, 19)
                resultados = []
                precio_actual = st.session_state.precio_gas_mmbtu

                for p in precios_sens:
                    pg_mwh = p / 0.293
                    eco_temp = calcular_economico(energetico, precio_cfe, pg_mwh, eta_caldera, inversion_inicial_usd)
                    ahorro_neto_temp = eco_temp['ahorro_neto']
                    payback_val = inversion_inicial_usd / ahorro_neto_temp if ahorro_neto_temp > 0 else 0
                    payback_str = f"{payback_val:.1f} años" if payback_val > 0 else "No rentable"
                    resultados.append({
                        "Precio gas (USD/MMBtu)": round(p, 1),
                        "Payback Simple (años)": payback_str,
                        "Ahorro neto anual (USD)": ahorro_neto_temp,
                        "Inversión estimada (USD)": inversion_inicial_usd,
                        "Rentable": "Sí" if ahorro_neto_temp > 0 else "No"
                    })

                df_sens = pd.DataFrame(resultados)

                st.dataframe(
                    df_sens.style
                        .format({
                            "Ahorro neto anual (USD)": "${:,.0f}",
                            "Inversión estimada (USD)": "${:,.0f}",
                            "Precio gas (USD/MMBtu)": "{:.1f}"
                        })
                        .applymap(
                            lambda x: "background-color: #d4edda; color: black" if x == "Sí" else "background-color: #f8d7da; color: black" if x == "No" else "",
                            subset=["Rentable"]
                        ),
                    use_container_width=True,
                    hide_index=True
                )

                st.caption("Nota: El payback se calcula como Inversión fija ÷ Ahorro neto anual. La fila con tu precio actual del sidebar debe coincidir exactamente con el Dashboard. Si no coincide, refresca la app (F5).")

        except Exception as e:
            st.error(f"Error al procesar el Excel:\n{str(e)}")
