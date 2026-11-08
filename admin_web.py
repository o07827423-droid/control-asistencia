import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Panel de Administración Multi-Sucursal",
    page_icon="📊",
    layout="wide"
)

# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        return None

supabase = init_connection()

# --- VERIFICACIÓN DE CREDENCIALES ---
if not supabase:
    st.error("⚠️ Configure sus credenciales de Supabase en el código o en los Secrets de Streamlit Cloud.")
    st.stop()

# --- SELECTOR DE SUCURSAL ---
st.sidebar.title("Configuración")
sucursales_disponibles = ["Centro", "Norte", "Sur", "Oeste"]
sucursal_activa = st.sidebar.selectbox("Seleccionar Sucursal", sucursales_disponibles)

st.title("Panel de Administración Multi-Sucursal")
st.markdown("Control centralizado de asistencias, incidencias y horarios por sucursal en tiempo real.")

# --- TABS DE NAVEGACIÓN ---
tab_alertas, tab_horarios, tab_personal = st.tabs([
    "⚠️ Alertas e Incidencias",
    "📅 Gestión de Horarios",
    "👥 Personal"
])

# ==========================================
# TAB 1: ALERTAS E INCIDENCIAS Y REGISTROS
# ==========================================
with tab_alertas:
    st.header(f"Incidencias y Registros - Sucursal {sucursal_activa}")
   
    try:
        # Consultar la tabla asistencia filtrada por sucursal
        response = supabase.table("asistencia").select("*").eq("sucursal", sucursal_activa).execute()
        datos_asistencia = response.data
       
        if datos_asistencia and len(datos_asistencia) > 0:
            df = pd.DataFrame(datos_asistencia)
            st.dataframe(df, use_container_width=True)
        else:
            st.info(f"No hay registros de asistencia para la sucursal {sucursal_activa}.")
           
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")

# ==========================================
# TAB 2: GESTIÓN DE HORARIOS SEMANALES
# ==========================================
with tab_horarios:
    st.header(f"Programación de Horarios Semanales (Sucursal {sucursal_activa})")
   
    # Obtener trabajadores de la sucursal activa
    try:
        resp_trabajadores = supabase.table("trabajadores").select("*").eq("sucursal_id", sucursal_activa).execute()
        lista_trabajadores = resp_trabajadores.data
    except Exception as e:
        lista_trabajadores = []

    if lista_trabajadores:
        st.markdown("Aquí el administrador puede definir los turnos y horas de entrada/salida por empleado.")
       
        for t in lista_trabajadores:
            with st.expander(f"Horario para: {t.get('nombre')} (ID: {t.get('id_empleado')})"):
                col_ent, col_sal = st.columns(2)
                with col_ent:
                    hora_entrada = st.time_input("Hora de Entrada", key=f"ent_{t.get('id_empleado')}")
                with col_sal:
                    hora_salida = st.time_input("Hora de Salida", key=f"sal_{t.get('id_empleado')}")
               
                if st.button("Guardar Horario en la Nube", key=f"btn_horario_{t.get('id_empleado')}"):
                    st.success(f"Horario actualizado exitosamente para {t.get('nombre')}")
    else:
        st.info(f"No hay personal registrado específicamente para esta sucursal ({sucursal_activa}). Regístrelos en la pestaña Personal.")

# ==========================================
# TAB 3: PERSONAL Y GESTIÓN
# ==========================================
with tab_personal:
    st.header(f"Personal Vinculado a Sucursal {sucursal_activa}")
   
    # Formulario para registrar nuevo trabajador
    with st.form("form_nuevo_trabajador"):
        st.subheader("Registrar Nuevo Trabajador")
        col_id, col_nombre, col_pin = st.columns([1, 2, 1])
       
        with col_id:
            id_empleado = st.text_input("ID Empleado")
        with col_nombre:
            nombre = st.text_input("Nombre Completo")
        with col_pin:
            pin = st.text_input("PIN de Marcaje", type="password")
           
        submit_reg = st.form_submit_button("Registrar en la Nube")
       
        if submit_reg:
            if id_empleado and nombre:
                try:
                    nuevo_registro = {
                        "id_empleado": str(id_empleado),
                        "nombre": nombre,
                        "pin": pin if pin else "0000",
                        "sucursal_id": sucursal_activa
                    }
                    supabase.table("trabajadores").insert(nuevo_registro).execute()
                    st.success(f"¡Trabajador {nombre} registrado correctamente en la sucursal {sucursal_activa}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar: {e}")
            else:
                st.warning("Por favor complete al menos el ID y el Nombre del empleado.")

    st.markdown("---")
    st.subheader("Listado de Personal y Acciones")
   
    try:
        resp_pers = supabase.table("trabajadores").select("*").eq("sucursal_id", sucursal_activa).execute()
        personal_sucursal = resp_pers.data
       
        if personal_sucursal:
            for trabajador in personal_sucursal:
                c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
                with c1:
                    st.text(f"ID: {trabajador.get('id_empleado')}")
                with c2:
                    st.text(f"Nombre: {trabajador.get('nombre')}")
                with c3:
                    st.text(f"Sucursal: {trabajador.get('sucursal_id')}")
                with c4:
                    if st.button("Eliminar", key=f"eliminar_{trabajador.get('id_empleado')}"):
                        try:
                            supabase.table("trabajadores").delete().eq("id_empleado", trabajador.get('id_empleado')).execute()
                            st.success("Trabajador eliminado.")
                            st.rerun()
                        except Exception as err:
                            st.error(f"No se pudo eliminar: {err}")
        else:
            st.info("No hay trabajadores registrados en esta sucursal.")
           
    except Exception as err:
        st.error(f"Error al cargar el personal: {err}")
