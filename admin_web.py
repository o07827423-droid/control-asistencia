import streamlit as st
import pandas as pd
from supabase import create_client, Client
import io
from datetime import datetime, timedelta

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

# --- GESTIÓN DE SUCURSALES ---
st.title("📊 Sistema Profesional de Control de Asistencia")
st.markdown("Panel centralizado de administración multi-sucursal.")

# Obtener sucursales existentes desde la tabla de trabajadores o usar la Principal por defecto
try:
    resp_suc = supabase.table("trabajadores").select("sucursal_id").execute()
    sucursales_dinamicas = list(set([item['sucursal_id'] for item in resp_suc.data if item.get('sucursal_id')])) if resp_suc.data else []
except:
    sucursales_dinamicas = []

if "Sucursal Principal" not in sucursales_dinamicas:
    sucursales_dinamicas.insert(0, "Sucursal Principal")

st.sidebar.markdown("### 📍 Control de Sucursales")
sucursal_seleccionada = st.sidebar.selectbox("Sucursal Activa", sucursales_dinamicas)

# Añadir nueva sucursal
with st.sidebar.expander("➕ Añadir Nueva Sucursal"):
    nueva_suc_input = st.text_input("Nombre de la sucursal")
    if st.button("Guardar Sucursal"):
        if nueva_suc_input:
            if nueva_suc_input not in sucursales_dinamicas:
                st.success(f"¡Sucursal '{nueva_suc_input}' creada exitosamente!")
                st.rerun()
            else:
                st.warning("La sucursal ya existe.")

# Eliminar sucursal actual (siempre que no sea la Principal)
if sucursal_seleccionada != "Sucursal Principal":
    if st.sidebar.button("🗑️ Eliminar Sucursal Actual", type="primary"):
        try:
            # Eliminar registros asociados en Supabase
            supabase.table("trabajadores").delete().eq("sucursal_id", sucursal_seleccionada).execute()
            supabase.table("horarios").delete().eq("sucursal_id", sucursal_seleccionada).execute()
            supabase.table("asistencia").delete().eq("sucursal", sucursal_seleccionada).execute()
            st.sidebar.success(f"Sucursal '{sucursal_seleccionada}' eliminada correctamente.")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error al eliminar sucursal: {e}")

st.markdown(f"### Sucursal Activa: **{sucursal_seleccionada}**")

# --- MENÚ DE ADMINISTRACIÓN ---
menu_admin = st.tabs(["👥 Personal", "🕒 Horarios", "📋 Historial", "🚨 Alertas e Incidencias"])

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

            trabajador_a_borrar = st.selectbox(
                "Seleccione trabajador para eliminar",
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
# 2. PESTAÑA: HORARIOS
# ==========================================
with menu_admin[1]:
    st.subheader("Programación de Horarios Semanales")

    try:
        resp_sem = supabase.table("horarios").select("semana").eq("sucursal_id", sucursal_seleccionada).execute()
        semanas_guardadas = sorted(list(set([item['semana'] for item in resp_sem.data if item['semana'] != "Semana Actual (General)"]))) if resp_sem.data else []
    except:
        semanas_guardadas = []

    semanas_guardadas.insert(0, "Semana Actual (General)")

    col_acc1, col_acc2, col_acc3 = st.columns([2, 2, 4])
    
    with col_acc1:
        with st.popover("➕ Añadir Semana"):
            hoy = datetime.now()
            lunes_actual = hoy - timedelta(days=hoy.weekday())
            opciones_semanas_auto = []
            for i in range(-2, 6):
                inicio = lunes_actual + timedelta(weeks=i)
                fin = inicio + timedelta(days=5)
                s_str = f"Semana del {inicio.strftime('%d/%m/%Y')} al {fin.strftime('%d/%m/%Y')}"
                opciones_semanas_auto.append(s_str)

            nueva_semana_seleccionada = st.selectbox("Seleccione el rango de la semana", opciones_semanas_auto)
            
            if st.button("Crear y Activar Semana"):
                if nueva_semana_seleccionada:
                    try:
                        payload_inicial = {
                            "id_empleado": "GENERAL",
                            "sucursal_id": sucursal_seleccionada,
                            "semana": nueva_semana_seleccionada,
                            "detalle_semana": str({"Lunes": "08:00", "Martes": "08:00", "Miércoles": "08:00", "Jueves": "08:00", "Viernes": "08:00", "Sábado": "08:00", "Domingo": "08:00"})
                        }
                        supabase.table("horarios").upsert(payload_inicial, on_conflict="id_empleado,semana").execute()
                        st.success(f"¡{nueva_semana_seleccionada} creada exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear semana: {e}")

    with col_acc2:
        semana_a_borrar = st.selectbox("Seleccionar semana a eliminar", [s for s in semanas_guardadas if s != "Semana Actual (General)"])
        if semana_a_borrar:
            if st.button("🗑️ Eliminar Semana Seleccionada", type="primary"):
                try:
                    supabase.table("horarios").delete().eq("sucursal_id", sucursal_seleccionada).eq("semana", semana_a_borrar).execute()
                    st.success(f"¡Semana '{semana_a_borrar}' eliminada correctamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al eliminar la semana: {e}")

    with col_acc3:
        semana_seleccionada = st.selectbox("Seleccionar Semana Activa para Editar", semanas_guardadas, key="semana_seleccionada")

    st.markdown(f"**Editando Horarios para la Semana:** `{semana_seleccionada}`")
    st.markdown("---")

    try:
        trabajadores_res = supabase.table("trabajadores").select("*").eq("sucursal_id", sucursal_seleccionada).execute()
        lista_trabajadores = trabajadores_res.data

        if not lista_trabajadores:
            st.warning("No hay personal registrado en esta sucursal para asignar horarios.")
        else:
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            horas_opciones = [
                "Libre", "06:00", "06:30", "07:00", "07:30", "08:00", "08:30", 
                "09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00", 
                "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", 
                "16:00", "16:30", "17:00", "17:30", "18:00", "18:30", "19:00", 
                "19:30", "20:00"
            ]

            resp_horarios = supabase.table("horarios").select("*").eq("sucursal_id", sucursal_seleccionada).eq("semana", semana_seleccionada).execute()
            mapa_horarios = {h["id_empleado"]: eval(h["detalle_semana"]) for h in resp_horarios.data if h["id_empleado"] != "GENERAL"} if resp_horarios.data else {}

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
                            val_actual = horario_empleado_actual.get(dia, "08:00")
                            if val_actual not in horas_opciones:
                                val_actual = "08:00"
                            
                            h_select = st.selectbox(
                                f"H_{id_emp}_{dia}", 
                                options=horas_opciones, 
                                index=horas_opciones.index(val_actual),
                                label_visibility="collapsed", 
                                key=f"t_{id_emp}_{dia}_{semana_seleccionada}"
                            )
                            horarios_dias[dia] = h_select

                    if st.button(f"💾 Guardar Horario - {nombre_emp}", key=f"btn_hor_{id_emp}_{semana_seleccionada}"):
                        try:
                            payload = {
                                "id_empleado": id_emp,
                                "sucursal_id": sucursal_seleccionada,
                                "semana": semana_seleccionada,
                                "detalle_semana": str(horarios_dias)
                            }
                            supabase.table("horarios").upsert(payload, on_conflict="id_empleado,semana").execute()
                            st.success(f"Horario guardado correctamente para {nombre_emp}")
                        except Exception as e:
                            st.error(f"Error al guardar horario: {e}")
    except Exception as e:
        st.error(f"Error al cargar horarios: {e}")

# ==========================================
# 3. PESTAÑA: HISTORIAL
# ==========================================
with menu_admin[2]:
    st.subheader("Historial de Movimientos")
    
    col_h1, col_h2 = st.columns([4, 1])
    with col_h2:
        if st.button("🗑️ Limpiar Historial", type="primary"):
            try:
                supabase.table("asistencia").delete().eq("sucursal", sucursal_seleccionada).execute()
                st.success("Historial limpiado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al limpiar: {e}")

    try:
        response = supabase.table("asistencia").select("*").eq("sucursal", sucursal_seleccionada).order("fecha", desc=True).execute()
        datos = response.data

        if datos:
            df_hist = pd.DataFrame(datos)
            st.dataframe(df_hist, use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_hist.to_excel(writer, index=False, sheet_name='Historial')
            excel_data = output.getvalue()

            st.download_button(
                label="📥 Descargar Historial en Excel (.xlsx)",
                data=excel_data,
                file_name=f"historial_{sucursal_seleccionada.lower().replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay registros en el historial para esta sucursal.")
    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")

# ==========================================
# 4. PESTAÑA: ALERTAS E INCIDENCIAS
# ==========================================
with menu_admin[3]:
    st.subheader("Panel de Alertas e Incidencias (Retrasos y Excesos de Descanso)")

    col_a1, col_a2 = st.columns([4, 1])
    with col_a2:
        if st.button("🗑️ Limpiar Alertas", type="primary"):
            try:
                supabase.table("asistencia").delete().eq("sucursal", sucursal_seleccionada).like("tipo", "%(Tarde:%").execute()
                supabase.table("asistencia").delete().eq("sucursal", sucursal_seleccionada).like("tipo", "%(Exceso:%").execute()
                st.success("Alertas limpiadas correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al limpiar alertas: {e}")

    try:
        response = supabase.table("asistencia").select("*").eq("sucursal", sucursal_seleccionada).order("fecha", desc=True).execute()
        datos = response.data

        if datos:
            df_alerta = pd.DataFrame(datos)
            if "tipo" in df_alerta.columns:
                df_alerta = df_alerta[df_alerta["tipo"].str.contains("Tarde|Exceso", na=False)]

            if not df_alerta.empty:
                st.dataframe(df_alerta, use_container_width=True)

                output_a = io.BytesIO()
                with pd.ExcelWriter(output_a, engine='openpyxl') as writer:
                    df_alerta.to_excel(writer, index=False, sheet_name='Alertas')
                excel_alerta_data = output_a.getvalue()

                st.download_button(
                    label="📥 Descargar Alertas en Excel (.xlsx)",
                    data=excel_alerta_data,
                    file_name=f"alertas_{sucursal_seleccionada.lower().replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("No hay alertas de retrasos ni excesos de descanso registradas para esta sucursal.")
        else:
            st.info("No hay registros en la sucursal.")
    except Exception as e:
        st.error(f"Error al cargar las alertas: {e}")
