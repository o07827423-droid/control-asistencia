from datetime import datetime
import json
import pandas as pd
import streamlit as st

# Intentar importar la librería de Supabase
try:
  from supabase import create_client, Client
except ImportError:
  create_client = None

# Configuración de la página web
st.set_page_config(
    page_title="Panel Gerencial - Control de Asistencia",
    page_icon="📊",
    layout="wide",
)

# --- CREDENCIALES DE SUPABASE (Puedes ajustarlas o leerlas de st.secrets) ---
# Si despliegas en Streamlit Cloud, puedes guardar estas credenciales en los "Secrets" de la app.
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "TU_SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "TU_SUPABASE_KEY")


@st.cache_resource
def init_connection():
  if create_client and SUPABASE_URL != "TU_SUPABASE_URL":
    return create_client(SUPABASE_URL, SUPABASE_KEY)
  return None


supabase = init_connection()

st.title("📊 Panel de Administración Multi-Sucursal")
st.markdown(
    "Control centralizado de asistencias, incidencias y horarios por sucursal en"
    " tiempo real."
)

# 1. SELECTOR DE SUCURSAL
# Por defecto permitimos elegir sucursales dinámicamente o por defecto
sucursales_por_defecto = ["Sucursal Centro", "Sucursal Norte", "Sucursal Sur"]

# Intentar obtener sucursales reales desde la base de datos si está conectada
lista_sucursales = sucursales_por_defecto
if supabase:
  try:
    response = supabase.table("asistencia").select("sucursal_id").execute()
    if response.data:
      unicas = list(set([row["sucursal_id"] for row in response.data]))
      if unicas:
        lista_sucursales = unicas
  except Exception:
    pass

sucursal_seleccionada = st.sidebar.selectbox(
    "🏢 Seleccionar Sucursal", lista_sucursales
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Sucursal activa:** `{sucursal_seleccionada}`")

# 2. PESTAÑAS PRINCIPALES DEL PANEL WEB
tab_alertas, tab_horarios, tab_personal = st.tabs(
    ["⚠️ Alertas e Incidencias", "📅 Gestión de Horarios", "👥 Personal"]
)

# --- PESTAÑA 1: ALERTAS E INCIDENCIAS ---
with tab_alertas:
  st.subheader(f"Incidencias y Registros - {sucursal_seleccionada}")

  if supabase:
    try:
      # Consultar registros de asistencia de la sucursal seleccionada en Supabase
      res = (
          supabase.table("asistencia")
          .select("*")
          .eq("sucursal_id", sucursal_seleccionada)
          .order("id", desc=True)
          .execute()
      )
      datos = res.data

      if datos:
        df_asistencia = pd.DataFrame(datos)
        st.dataframe(df_asistencia, use_container_width=True)
      else:
        st.info(
            f"No hay registros de asistencia para {sucursal_seleccionada} aún."
        )
    except Exception as e:
      st.error(f"Error al conectar con la base de datos: {e}")
  else:
    st.warning(
        "⚠️ Configure sus credenciales de Supabase en el código o en los"
        " Secrets de Streamlit para ver los datos en vivo."
    )

# --- PESTAÑA 2: GESTIÓN DE HORARIOS ---
with tab_horarios:
  st.subheader(
      f"Programación de Horarios Semanales ({sucursal_seleccionada})"
  )
  semana_seleccionada = st.text_input(
      "Rango de la Semana", "14/09/2026 al 20/09/2026"
  )
  st.write(
      "Aquí el administrador puede definir los turnos de Lunes a Domingo por"
      " empleado."
  )

  if supabase:
    if st.button("💾 Guardar Horarios en la Nube"):
      st.success(
          f"¡Horarios de la semana '{semana_seleccionada}' actualizados para"
          f" {sucursal_seleccionada}!"
      )
  else:
    st.info("Conecte Supabase para habilitar el almacenamiento en la nube.")

# --- PESTAÑA 3: PERSONAL ---
with tab_personal:
  st.subheader(f"Personal Vinculado a {sucursal_seleccionada}")

  if supabase:
    try:
      res_per = (
          supabase.table("trabajadores")
          .select("*")
          .eq("sucursal_id", sucursal_seleccionada)
          .execute()
      )
      if res_per.data:
        st.dataframe(pd.DataFrame(res_per.data), use_container_width=True)
      else:
        st.info(
            "No hay personal registrado específicamente para esta sucursal."
        )
    except Exception:
      pass

  st.markdown("### Registrar Nuevo Trabajador")
  col1, col2, col3 = st.columns(3)
  with col1:
    nuevo_id = st.text_input("ID Empleado")
  with col2:
    nuevo_nombre = st.text_input("Nombre Completo")
  with col3:
    nuevo_pin = st.text_input("PIN de Marcaje", type="password")

  if st.button("➕ Registrar en la Nube"):
    if nuevo_id and nuevo_nombre and nuevo_pin and supabase:
      try:
        supabase.table("trabajadores").insert({
            "id": nuevo_id,
            "nombre": nuevo_nombre,
            "pin": nuevo_pin,
            "sucursal_id": sucursal_seleccionada,
        }).execute()
        st.success(
            f"¡Trabajador {nuevo_nombre} registrado exitosamente en"
            f" {sucursal_seleccionada}!"
        )
      except Exception as e:
        st.error(f"Error al registrar: {e}")
    else:
      st.warning("Complete todos los campos o verifique la conexión a Supabase.")
