import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import os
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# ────────────────────────────────────────────────
# CONFIGURACIÓN DE PÁGINA (antes del login para que logo sea visible)
# ────────────────────────────────────────────────
st.set_page_config(
    page_title="Cogeneración – Análisis Técnico y Económico 2026",
    layout="wide",
    page_icon="⚡"
)

# ────────────────────────────────────────────────
# AUTENTICACIÓN (versión actual: location primero)
# ────────────────────────────────────────────────
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# Login: location='main' OBLIGATORIO como primer parámetro
authenticator.login(
    location='main',
    fields={
        'Form name': 'Iniciar sesión - Cogeneración 2026',
        'Username': 'Usuario',
        'Password': 'Contraseña',
        'Login': 'Entrar'
    }
)

# El estado de autenticación ahora se maneja con session_state
if st.session_state["authentication_status"]:
    # Usuario logueado → muestra TODO el contenido de la app

    # Logo (ya que estás autenticado)
    st.logo(
        "logo.png",
        size="large",
        link="https://www.luxem.mx"
    )

    # Saludo opcional
    st.sidebar.success(f"Bienvenido, {st.session_state['name']}! 👋")

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
    # TABS (tu contenido completo aquí)
    # ────────────────────────────────────────────────
    tab_dashboard, tab_balance, tab_econ, tab_emis, tab_detalle, tab_sens = st.tabs([
        "Dashboard", "Balance Energético", "Económico", "Emisiones", "Cálculos Detallados", "Sensibilidad"
    ])

    # Dashboard
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
        st.markdown("---")
        st.subheader("Histórico del Precio del Gas Natural – Henry Hub")
        archivo_excel = "Henry Hub.xls"
        if not os.path.exists(archivo_excel):
            st.error(f"No se encontró '{archivo_excel}' en la carpeta. Colócalo junto a este .py.")
        else:
            try:
                df_henry = pd.read_excel(archivo_excel)
                # ... (tu código completo de lectura y gráfica Henry Hub)
                # (no lo repito todo para no alargar, pero mantenlo igual que tenías)
            except Exception as e:
                st.error(f"Error al leer el Excel:\n{str(e)}")

    # Balance Energético
    with tab_balance:
        st.subheader("Diagrama Sankey – Balance Energético")
        # ... tu código completo de Sankey (mantén igual)

    # Económico
    with tab_econ:
        st.subheader("Comparación económica")
        # ... tu código completo con columnas y payback

    # Emisiones
    with tab_emis:
        st.subheader("Emisiones de CO₂")
        # ... tu código de columnas

    # Cálculos Detallados
    with tab_detalle:
        st.title("📐 Cálculos Detallados – Paso a Paso")
        # ... todos tus expanders (incluyendo eficiencia global)

    # Sensibilidad
    with tab_sens:
        st.subheader("Análisis y Proyección del Precio del Gas Natural – 8-10 años")
        # ... tu código completo de proyección y sensibilidad

    # Logout (puedes moverlo al sidebar si prefieres)
    authenticator.logout("Cerrar sesión", location='sidebar')

else:
    if st.session_state.get("authentication_status") is False:
        st.error("Usuario o contraseña incorrectos 😕")
    else:
        st.warning("Ingresa tus credenciales para continuar 🔒")
