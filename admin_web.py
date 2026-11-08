import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Sistema Profesional de Control de Asistencia",
    page_icon="📊",
    layout="wide"
)

# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Error al conectar con las credenciales de Supabase: {e}")
    st.stop()

# --- TÍTULO Y SELECTOR DE SUCURSAL ---
st.title("📊 Sistema Profesional de Control de Asistencia")
st.markdown("Panel centralizado de administración multi-sucursal.")

sucursales_disponibles = ["Sucursal Centro", "Sucursal Sur", "Sucursal Norte", "Sucursal Principal"]
sucursal_seleccionada = st.sidebar.selectbox("📍 Seleccionar Sucursal", sucursales_disponibles)

st.markdown(f"### Sucursal Activa: **{sucursal_seleccionada}**")

# --- MENÚ DE ADMINISTRACIÓN (REPLICANDO ESCRITORIO) ---
menu_admin = st.tabs(["👥 Personal", "🕒 Horarios", "📋 Historial", "🚨 Alertas"])

# ==========================================
# 1. PESTAÑA: PERSONAL (ID, Nombre, PIN + Eliminar)
# ==========================================
with menu_admin[0]:
    st.subheader("Gestión de Personal")
    
    with st.form("form_nuevo_trabajador", clear_on_submit=True):
        col_id, col_nombre, col_pin = st.columns([1, 2, 1])
        with col_id:
            id_empleado = st.text_input("ID")
        with col_nombre:
            nombre_completo = st.text_input("Nombre completo")
        with col_pin:
            pin_marcaje = st.text_input("PIN", type="password")

        submitted = st.form_submit_button("➕ Añadir Trabajador")
        if submitted:
            if id_empleado and nombre_completo:
                try:
                    nuevo_registro = {
                        "id_empleado": id_empleado,
                        "nombre": nombre_completo,
                        "pin": pin_marcaje,
                        "sucursal_id": sucursal_seleccionada
                    }
                    supabase.table("trabajadores").insert(nuevo_registro).execute()
                    st.success(f"¡Trabajador {nombre_completo} registrado exitosamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar: {e}")
            else:
                st.warning("Por favor completa el ID y el Nombre completo.")

    st.markdown("---")
    st.markdown("#### Personal Registrado")
    try:
        resp_trab = supabase.table("trabajadores").select("*").eq("sucursal_id", sucursal_seleccionada).execute()
        trabajadores_actuales = resp_trab.data

        if trabajadores_actuales:
            df_trab = pd.DataFrame(trabajadores_actuales)[["id_empleado", "nombre", "pin"]]
            df_trab.columns = ["ID", "Nombre", "PIN"]
            # Ocultar parcialmente el PIN por seguridad visual
            df_trab["PIN"] = "****"
            st.dataframe(df_trab, use_container_width=True)

            st.markdown("#### Eliminar Trabajador Seleccionado")
            trabajador_a_borrar = st.selectbox(
                "Seleccione trabajador",
                options=trabajadores_actuales,
                format_func=lambda x: f"{x.get('id_empleado')} - {x.get('nombre')}"
            )
            if st.button("🗑️ Eliminar Trabajador Seleccionado", type="primary"):
                try:
                    supabase.table("trabajadores").delete().eq("id_empleado", trabajador_a_borrar.get('id_empleado')).execute()
                    st.success(f"Trabajador eliminado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al eliminar: {e}")
        else:
            st.info("No hay personal registrado en esta sucursal.")
    except Exception as e:
        st.error(f"Error al cargar personal: {e}")

# ==========================================
# 2. PESTAÑA: HORARIOS (Lunes a Domingo)
# ==========================================
with menu_admin[1]:
    st.subheader("Programación de Horarios Semanales")
    
    col_acc1, col_acc2, col_acc3 = st.columns([2, 2, 4])
    with col_acc1:
        if st.button("➕ Añadir Semana"):
            st.info("Semana habilitada para edición.")
    with col_acc2:
        if st.button("🗑️ Eliminar Semana Actual"):
            st.info("Semana restablecida.")
    with col_acc3:
        st.markdown("**Semana Actual (General)**")

    st.markdown("---")

    try:
        trabajadores_res = supabase.table("trabajadores").select("*").eq("sucursal_id", sucursal_seleccionada).execute()
        lista_trabajadores = trabajadores_res.data

        if not lista_trabajadores:
            st.warning("No hay personal registrado en esta sucursal para asignar horarios.")
        else:
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            
            for t in lista_trabajadores:
                id_emp = t.get('id_empleado')
                nombre_emp = t.get('nombre')

                with st.expander(f"{id_emp} - {nombre_emp}"):
                    horarios_dias = {}
                    cols_dias = st.columns(len(dias_semana))
                    
                    for idx, dia in enumerate(dias_semana):
                        with cols_dias[idx]:
                            st.markdown(f"**{dia}**")
                            h_entrada = st.time_input(f"Entrada {dia}", key=f"h_{id_emp}_{dia}", label_visibility="collapsed")
                            horarios_dias[dia] = str(h_entrada)

                    if st.button(f"💾 Guardar Horario - {nombre_emp}", key=f"btn_hor_{id_emp}"):
                        try:
                            payload = {
                                "id_empleado": id_emp,
                                "sucursal_id": sucursal_seleccionada,
                                "detalle_semana": str(horarios_dias)
                            }
                            supabase.table("horarios").upsert(payload, on_conflict="id_empleado").execute()
                            st.success(f"Horario guardado correctamente para {nombre_emp}")
                        except Exception as e:
                            st.error(f"Error al guardar horario: {e}")
    except Exception as e:
        st.error(f"Error al cargar horarios: {e}")

# ==========================================
# 3. PESTAÑA: HISTORIAL (ID, Nombre, Movimiento, Fecha, Hora)
# ==========================================
with menu_admin[2]:
    st.subheader("Historial de Movimientos")
    try:
        response = supabase.table("asistencia").select("*").eq("sucursal", sucursal_seleccionada).execute()
        datos = response.data

        if datos:
            df_hist = pd.DataFrame(datos)
            st.dataframe(df_hist, use_container_width=True)
        else:
            st.info("No hay registros en el historial para esta sucursal.")
    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")

# ==========================================
# 4. PESTAÑA: ALERTAS (Tipo, Nombre, Fecha, Detalle / Exceso)
# ==========================================
with menu_admin[3]:
    st.subheader("Panel de Alertas e Incidencias")
    
    if st.button("🔄 Actualizar Alertas"):
        st.rerun()

    try:
        response = supabase.table("asistencia").select("*").eq("sucursal", sucursal_seleccionada).execute()
        datos_alertas = response.data

        if datos_alertas:
            df_alerta = pd.DataFrame(datos_alertas)
            # Adaptar formato de columnas para alertas
            if "tipo" in df_alerta.columns:
                df_alerta = df_alerta.rename(columns={"tipo": "Tipo", "empleado": "Nombre", "fecha": "Fecha"})
                df_alerta["Detalle / Exceso"] = "Marcaje registrado"
                cols_mostrar = [c for c in ["Tipo", "Nombre", "Fecha", "Detalle / Exceso"] if c in df_alerta.columns]
                st.dataframe(df_alerta[cols_mostrar], use_container_width=True)
            else:
                st.dataframe(df_alerta, use_container_width=True)
        else:
            st.info("No hay alertas registradas para esta sucursal.")
    except Exception as e:
        st.error(f"Error al cargar las alertas: {e}")
