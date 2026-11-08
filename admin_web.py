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

# --- MENÚ DE ADMINISTRACIÓN ---
menu_admin = st.tabs(["👥 Personal", "🕒 Horarios", "📋 Historial", "🚨 Alertas"])

# ==========================================
# 1. PESTAÑA: PERSONAL
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

        submitted = st.form_submit_button("➕ Añadir / Actualizar Trabajador")
        if submitted:
            if id_empleado and nombre_completo:
                try:
                    nuevo_registro = {
                        "id_empleado": id_empleado,
                        "nombre": nombre_completo,
                        "pin": pin_marcaje,
                        "sucursal_id": sucursal_seleccionada
                    }
                    supabase.table("trabajadores").upsert(nuevo_registro, on_conflict="id_empleado").execute()
                    st.success(f"¡Trabajador {nombre_completo} guardado exitosamente!")
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
                    st.success("Trabajador eliminado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al eliminar: {e}")
        else:
            st.info("No hay personal registrado en esta sucursal.")
    except Exception as e:
        st.error(f"Error al cargar personal: {e}")

# ==========================================
# 2. PESTAÑA: HORARIOS (Gestión de Semanas)
# ==========================================
with menu_admin[1]:
    st.subheader("Programación de Horarios Semanales")

    try:
        resp_sem = supabase.table("horarios").select("semana").eq("sucursal_id", sucursal_seleccionada).execute()
        semanas_guardadas = sorted(list(set([item['semana'] for item in resp_sem.data]))) if resp_sem.data else []
    except:
        semanas_guardadas = []

    if "Semana Actual (General)" not in semanas_guardadas:
        semanas_guardadas.insert(0, "Semana Actual (General)")

    col_acc1, col_acc2, col_acc3 = st.columns([2, 2, 4])
    
    with col_acc1:
        with st.popover("➕ Añadir Semana"):
            nueva_semana_input = st.text_input("Rango de fechas (Ej: 14/09/2026 al 20/09/2026)")
            if st.button("Guardar Nueva Semana"):
                if nueva_semana_input:
                    st.session_state["semana_activa"] = nueva_semana_input
                    st.success(f"Semana {nueva_semana_input} creada.")
                    st.rerun()

    with col_acc2:
        if st.button("🗑️ Eliminar Semana Actual"):
            semana_actual = st.session_state.get("semana_seleccionada", "Semana Actual (General)")
            if semana_actual != "Semana Actual (General)":
                try:
                    supabase.table("horarios").delete().eq("sucursal_id", sucursal_seleccionada).eq("semana", semana_actual).execute()
                    st.success(f"Semana {semana_actual} eliminada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al eliminar semana: {e}")
            else:
                st.warning("No se puede eliminar la semana general por defecto.")

    with col_acc3:
        semana_seleccionada = st.selectbox("Seleccionar Semana Activa", semanas_guardadas, key="semana_seleccionada")

    st.markdown(f"**Editando Horarios para la Semana:** `{semana_seleccionada}`")
    st.markdown("---")

    try:
        trabajadores_res = supabase.table("trabajadores").select("*").eq("sucursal_id", sucursal_seleccionada).execute()
        lista_trabajadores = trabajadores_res.data

        if not lista_trabajadores:
            st.warning("No hay personal registrado en esta sucursal para asignar horarios.")
        else:
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            
            resp_horarios = supabase.table("horarios").select("*").eq("sucursal_id", sucursal_seleccionada).eq("semana", semana_seleccionada).execute()
            mapa_horarios = {h["id_empleado"]: eval(h["detalle_semana"]) for h in resp_horarios.data} if resp_horarios.data else {}

            for t in lista_trabajadores:
                id_emp = t.get('id_empleado')
                nombre_emp = t.get('nombre')
                horario_empleado_actual = mapa_horarios.get(id_emp, {})

                with st.expander(f"{id_emp} - {nombre_emp}"):
                    horarios_dias = {}
                    cols_dias = st.columns(len(dias_semana))
                    
                    for idx, dia in enumerate(dias_semana):
                        with cols_dias[idx]:
                            st.markdown(f"**{dia}**")
                            h_entrada = st.time_input(f"Entrada {dia}", key=f"h_{id_emp}_{dia}_{semana_seleccionada}", label_visibility="collapsed")
                            horarios_dias[dia] = str(h_entrada)

                    if st.button(f"💾 Guardar Horario - {nombre_emp}", key=f"btn_hor_{id_emp}_{semana_seleccionada}"):
                        try:
                            payload = {
                                "id_empleado": id_emp,
                                "sucursal_id": sucursal_seleccionada,
                                "semana": semana_seleccionada,
                                "detalle_semana": str(horarios_dias)
                            }
                            supabase.table("horarios").upsert(payload, on_conflict="id_empleado,semana").execute()
                            st.success(f"Horario guardado correctamente para {nombre_emp} en la semana {semana_seleccionada}")
                        except Exception as e:
                            st.error(f"Error al guardar horario: {e}")
    except Exception as e:
        st.error(f"Error al cargar horarios: {e}")

# ==========================================
# 3. PESTAÑA: HISTORIAL
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
# 4. PESTAÑA: ALERTAS
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
