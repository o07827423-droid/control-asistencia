import streamlit as st
import pandas as pd
from supabase import create_client
import io
from datetime import datetime, timedelta
import ast

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Sistema Profesional de Control de Asistencia",
    page_icon="🏢",
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

# Mapeo visual para renombrar "Sucursal Principal" a "Hugo Oliveros" sin alterar la BD
MAPEO_NOMBRES = {
    "Sucursal Principal": "Hugo Oliveros"
}

def to_display(nombre_bd):
    return MAPEO_NOMBRES.get(nombre_bd, nombre_bd)

def to_db(nombre_display):
    for k, v in MAPEO_NOMBRES.items():
        if v == nombre_display:
            return k
    return nombre_display

def obtener_lista_sucursales_bd():
    try:
        resp = supabase.table("trabajadores").select("sucursal_id").execute()
        if resp.data:
            sucs = sorted(list(set([item.get("sucursal_id") for item in resp.data if item.get("sucursal_id")])))
            if sucs:
                return sucs
    except Exception:
        pass
    return ["Sucursal Principal", "2010", "guacara", "palo negro", "Turmero", "DG", "San Francisco"]

def obtener_lista_sucursales_display():
    sucs_bd = obtener_lista_sucursales_bd()
    return [to_display(s) for s in sucs_bd]

def main():
    # --- SELECTOR GLOBAL DE SUCURSAL EN LA BARRA LATERAL ---
    st.sidebar.title("🏢 Control Global")
    sucs_display = obtener_lista_sucursales_display()
    
    sucursal_activa_display = st.sidebar.selectbox(
        "Sucursal Activa:", 
        ["Todas las Sucursales"] + sucs_display,
        help="Selecciona la sucursal para filtrar toda la información corporativa en tiempo real."
    )
    
    sucursal_activa_bd = "Todas las Sucursales" if sucursal_activa_display == "Todas las Sucursales" else to_db(sucursal_activa_display)
    
    st.sidebar.divider()
    st.sidebar.info(f"**Sucursal Activa:**\n`{sucursal_activa_display}`")

    st.title("🏢 Panel Corporativo • Control de Asistencia")
    st.divider()

    # --- NAVEGACIÓN CON PESTAÑAS HORIZONTALES ---
    tab_auditoria, tab_alertas, tab_personal, tab_horarios, tab_historial, tab_sucursales = st.tabs([
        "📊 Auditoría y Sincronización", 
        "🚨 Alertas, Incidencias y Ausencias",
        "👥 Gestión de Personal",
        "📅 Gestión de Horarios", 
        "📜 Historial y Exportación",
        "⚙️ Gestión de Sucursales"
    ])

    with tab_auditoria:
        modulo_auditoria_completa(sucursal_activa_bd, sucursal_activa_display)

    with tab_alertas:
        modulo_alertas_incidencias(sucursal_activa_bd, sucursal_activa_display)

    with tab_personal:
        modulo_gestion_personal(sucursal_activa_bd, sucursal_activa_display)

    with tab_horarios:
        modulo_gestion_horarios(sucursal_activa_bd, sucursal_activa_display)

    with tab_historial:
        modulo_historial_exportacion(sucursal_activa_bd, sucursal_activa_display)

    with tab_sucursales:
        modulo_gestion_sucursales()


def modulo_auditoria_completa(sucursal_activa_bd, sucursal_activa_display):
    st.markdown("## 🚨 Auditoría Operativa: Turnos Abiertos y Sincronización")

    try:
        resp = supabase.table("asistencia").select("*").execute()
        asistencia_data = resp.data or []
        
        if not asistencia_data:
            st.info("No se encontraron registros de asistencia en la base de datos.")
            return

        df_asis = pd.DataFrame(asistencia_data)

        if sucursal_activa_bd != "Todas las Sucursales":
            col_suc = 'sucursal' if 'sucursal' in df_asis.columns else ('sucursal_id' if 'sucursal_id' in df_asis.columns else None)
            if col_suc:
                df_asis = df_asis[df_asis[col_suc] == sucursal_activa_bd]

        if df_asis.empty:
            st.info(f"No hay registros para {sucursal_activa_display}.")
            return

        st.markdown("### 🔴 Turnos Abiertos (+15 Horas)")
        turnos_abiertos = []
        if 'fecha' in df_asis.columns and 'empleado' in df_asis.columns:
            df_asis['fecha_dt'] = pd.to_datetime(df_asis['fecha'], errors='coerce')
            df_asis_sorted = df_asis.dropna(subset=['fecha_dt']).sort_values(by='fecha_dt')

            for emp, grupo in df_asis_sorted.groupby('empleado'):
                ultimo_movimiento = grupo.iloc[-1]
                tipo_ult = str(ultimo_movimiento.get('tipo', ''))
                fecha_ult = ultimo_movimiento.get('fecha_dt')
                suc_emp_bd = ultimo_movimiento.get('sucursal', ultimo_movimiento.get('sucursal_id', 'N/D'))
                suc_emp_display = to_display(suc_emp_bd)

                if "Entrada" in tipo_ult or "Retomando" in tipo_ult:
                    ahora_ref = datetime.now(fecha_ult.tzinfo) if fecha_ult.tzinfo else datetime.now()
                    fecha_cmp = fecha_ult if fecha_ult.tzinfo else fecha_ult.replace(tzinfo=None)
                    tiempo_transcurrido = ahora_ref - fecha_cmp

                    if tiempo_transcurrido > timedelta(hours=15):
                        horas_abierto = round(tiempo_transcurrido.total_seconds() / 3600, 1)
                        turnos_abiertos.append({
                            "Sucursal": suc_emp_display,
                            "Empleado": emp,
                            "Último Movimiento": tipo_ult,
                            "Fecha/Hora Marcaje": fecha_ult.strftime("%d/%m/%Y %I:%M %p"),
                            "Horas Transcurridas": f"{horas_abierto} hrs"
                        })

        if turnos_abiertos:
            st.dataframe(pd.DataFrame(turnos_abiertos), use_container_width=True)
        else:
            st.success("✅ Sin turnos abiertos mayores a 15 horas.")

        st.divider()
        st.markdown("### 🔄 Auditoría de Logs de Sincronización")
        logs_sinc = []
        df_asis_desc = df_asis.sort_values(by='fecha', ascending=False)
        for _, r in df_asis_desc.iterrows():
            f_local_str = str(r.get('fecha', ''))
            f_creado_nube = str(r.get('created_at', r.get('fecha', '')))
            try:
                dt_local = pd.to_datetime(f_local_str)
                dt_nube = pd.to_datetime(f_creado_nube)
                diferencia_minutos = abs((dt_nube - dt_local).total_seconds() / 60)
                
                estado_sync = "🟢 En Línea (Tiempo Real)"
                if diferencia_minutos > 3:
                    estado_sync = f"🟠 Sincronizado Offline (+{int(diferencia_minutos)} min)"

                suc_bd_log = r.get('sucursal', r.get('sucursal_id', 'N/D'))
                logs_sinc.append({
                    "Sucursal": to_display(suc_bd_log),
                    "Empleado": r.get('empleado', 'N/D'),
                    "Movimiento": r.get('tipo', 'N/D'),
                    "Hora Marcaje Local": dt_local.strftime("%d/%m/%Y %I:%M %p"),
                    "Estado / Sincronización": estado_sync
                })
            except Exception:
                pass

        if logs_sinc:
            st.dataframe(pd.DataFrame(logs_sinc).head(25), use_container_width=True)
        else:
            st.info("No hay suficientes registros de logs para auditar.")

    except Exception as e:
        st.error(f"Error cargando auditoría: {e}")


def modulo_alertas_incidencias(sucursal_activa_bd, sucursal_activa_display):
    st.markdown("## 🚨 Panel de Alertas, Incidencias y Ausencias")

    if sucursal_activa_bd == "Todas las Sucursales":
        st.warning("⚠️ Por favor, selecciona una **sucursal específica** en la barra lateral para gestionar alertas o ausencias.")
        return

    try:
        q_asis = supabase.table("asistencia").select("*").eq("sucursal", sucursal_activa_bd)
        q_trab = supabase.table("trabajadores").select("*").eq("sucursal_id", sucursal_activa_bd)
        q_hor = supabase.table("horarios").select("*").eq("sucursal_id", sucursal_activa_bd)

        datos_asis = q_asis.execute().data or []
        trabajadores_suc = q_trab.execute().data or []
        horarios_suc = q_hor.execute().data or []

        col_al1, col_al2 = st.columns(2)

        with col_al1:
            st.markdown("### ⚠️ Incidencias (Tardanzas y Excesos)")
            incidencias = []
            for r in datos_asis:
                tipo = str(r.get("tipo", ""))
                if "Tarde" in tipo or "Exceso" in tipo:
                    f_str = str(r.get("fecha", ""))
                    try:
                        dt_f = pd.to_datetime(f_str).strftime("%d/%m/%Y %I:%M %p")
                    except Exception:
                        dt_f = f_str

                    incidencias.append({
                        "ID": r.get("id"),
                        "Empleado": r.get("empleado", "N/D"),
                        "Incidencia": tipo,
                        "Fecha y Hora": dt_f
                    })

            df_inc = pd.DataFrame(incidencias) if incidencias else pd.DataFrame(columns=["Empleado", "Incidencia", "Fecha y Hora"])
            cols_mostrar = [c for c in df_inc.columns if c != "ID"]
            st.dataframe(df_inc[cols_mostrar], use_container_width=True)

            if incidencias and st.button("🧹 Limpiar Alertas e Incidencias"):
                try:
                    for inc in incidencias:
                        if inc.get("ID") is not None:
                            supabase.table("asistencia").delete().eq("id", inc["ID"]).execute()
                        else:
                            supabase.table("asistencia").delete().eq("empleado", inc["Empleado"]).eq("tipo", inc["Incidencia"]).execute()
                    st.success("¡Alertas limpiadas con éxito!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error al limpiar alertas: {ex}")

        with col_al2:
            st.markdown("### 👤 Ausencias (Semana en Curso - Días Pasados)")
            dias_map_orden = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4, "Sábado": 5, "Domingo": 6}
            
            # Recopilar fichajes de entrada por fecha y empleado
            fichajes_por_fecha = set()
            for r in datos_asis:
                try:
                    f_dt = pd.to_datetime(r.get('fecha'))
                    f_corta = f_dt.date()
                    if "Entrada" in str(r.get('tipo', '')):
                        fichajes_por_fecha.add((str(r.get('empleado')), f_corta))
                except Exception:
                    pass

            ausencias = []
            hoy = datetime.now().date()
            # Calcular el inicio de la semana actual (Lunes)
            inicio_semana_actual = hoy - timedelta(days=hoy.weekday())

            for h in horarios_suc:
                id_emp = str(h.get('id_empleado'))
                try:
                    detalle = ast.literal_eval(h.get('detalle_semana', '{}'))
                except Exception:
                    continue
                
                nombre_emp = id_emp
                for t in trabajadores_suc:
                    if str(t.get('id_empleado')) == id_emp:
                        nombre_emp = t.get('nombre')
                        break

                # Evaluar únicamente los días de la semana en curso que ya hayan pasado (desde el lunes hasta ayer/hoy)
                for nombre_dia, idx_dia in dias_map_orden.items():
                    dia_evaluar = inicio_semana_actual + timedelta(days=idx_dia)
                    
                    # Solo evaluar si el día ya pasó o es hoy pero ya pasó el turno (mostramos si dia_evaluar <= hoy)
                    if dia_evaluar <= hoy:
                        turno_hora = detalle.get(nombre_dia, "Libre")
                        if turno_hora != "Libre":
                            if (id_emp, dia_evaluar) not in fichajes_por_fecha and (nombre_emp, dia_evaluar) not in fichajes_por_fecha:
                                ausencias.append({
                                    "Fecha": dia_evaluar.strftime("%d/%m/%Y"),
                                    "Día": nombre_dia,
                                    "ID": id_emp,
                                    "Empleado": nombre_emp
                                })

            df_aus = pd.DataFrame(ausencias) if ausencias else pd.DataFrame(columns=["Fecha", "Día", "ID", "Empleado"])
            st.dataframe(df_aus, use_container_width=True)

        st.divider()
        st.markdown("### 📥 Descargar Reporte Consolidado (3 Hojas)")
        if st.button("📦 Generar Libro Excel con Ausencias, Incidencias e Historial"):
            output = io.BytesIO()
            df_historial = pd.DataFrame(datos_asis)
            if not df_historial.empty and "sucursal" in df_historial.columns:
                df_historial["sucursal"] = df_historial["sucursal"].apply(to_display)

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_aus.to_excel(writer, index=False, sheet_name='Ausencias')
                df_inc[cols_mostrar].to_excel(writer, index=False, sheet_name='Incidencias')
                df_historial.to_excel(writer, index=False, sheet_name='Historial')

            file_name = f"reporte_general_{sucursal_activa_display.lower().replace(' ', '_')}.xlsx"
            st.download_button(
                "📥 Descargar Archivo Excel Consolidado (.xlsx)", 
                data=output.getvalue(), 
                file_name=file_name, 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error cargando alertas: {e}")


def modulo_gestion_personal(sucursal_activa_bd, sucursal_activa_display):
    st.markdown("## 👥 Gestión de Personal")
    
    try:
        if sucursal_activa_bd == "Todas las Sucursales":
            resp_trab = supabase.table("trabajadores").select("*").execute()
            st.info("💡 Selecciona una sucursal específica en la barra lateral si deseas registrar un nuevo empleado.")
        else:
            resp_trab = supabase.table("trabajadores").select("*").eq("sucursal_id", sucursal_activa_bd).execute()
            
            st.markdown(f"### ➕ Registrar Trabajador en {sucursal_activa_display}")
            col1, col2, col3 = st.columns(3)
            with col1:
                id_emp = st.text_input("ID de Empleado:")
            with col2:
                nombre_emp = st.text_input("Nombre Completo:")
            with col3:
                pin_emp = st.text_input("PIN de Acceso:", type="password")

            if st.button("💾 Guardar Trabajador"):
                if not id_emp.strip() or not nombre_emp.strip() or not pin_emp.strip():
                    st.error("Todos los campos son obligatorios.")
                else:
                    payload = {"id_empleado": id_emp.strip(), "nombre": nombre_emp.strip(), "pin": pin_emp.strip(), "sucursal_id": sucursal_activa_bd}
                    try:
                        supabase.table("trabajadores").upsert(payload, on_conflict="id_empleado").execute()
                        st.success(f"¡Trabajador guardado en {sucursal_activa_display}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            st.divider()

        st.markdown("### 📋 Listado de Personal")
        trabajadores_lista = resp_trab.data or []
        if trabajadores_lista:
            df_t = pd.DataFrame(trabajadores_lista)
            if "pin" in df_t.columns:
                df_t["pin"] = "****"
            if "sucursal_id" in df_t.columns:
                df_t["sucursal_id"] = df_t["sucursal_id"].apply(to_display)
            st.dataframe(df_t, use_container_width=True)
        else:
            st.info("No hay personal registrado.")
    except Exception as e:
        st.error(f"Error en gestión de personal: {e}")


def modulo_gestion_horarios(sucursal_activa_bd, sucursal_activa_display):
    st.markdown("## 📅 Programación de Horarios Semanales")
    
    if sucursal_activa_bd == "Todas las Sucursales":
        st.warning("⚠️ Selecciona una **sucursal específica** en la barra lateral para configurar horarios.")
        return

    try:
        resp_h = supabase.table("horarios").select("semana").eq("sucursal_id", sucursal_activa_bd).execute()
        semanas_registradas = sorted(list(set([h.get("semana") for h in (resp_h.data or []) if h.get("semana")])))
        if not semanas_registradas:
            semanas_registradas = ["Semana Actual (General)"]

        col_h1, col_h2, col_h3 = st.columns(3)
        
        with col_h1:
            st.markdown("### ➕ Añadir Semana")
            # Selector dinámico de semanas predefinidas o mes en curso
            hoy = datetime.now()
            lunes_actual = hoy - timedelta(days=hoy.weekday())
            opciones_semanas_sugeridas = []
            for w in range(4):
                inicio_w = lunes_actual + timedelta(weeks=w)
                fin_w = inicio_w + timedelta(days=5) # Sábado
                opciones_semanas_sugeridas.append(f"Semana del {inicio_w.strftime('%d/%m/%Y')} al {fin_w.strftime('%d/%m/%Y')}")

            tipo_creacion = st.radio("Método:", ["Seleccionar Sugerida", "Personalizada"], horizontal=True)
            if tipo_creacion == "Seleccionar Sugerida":
                nueva_semana = st.selectbox("Seleccionar Rango de Semana:", opciones_semanas_sugeridas)
            else:
                nueva_semana = st.text_input("Escribir identificador:")

            if st.button("Crear Semana"):
                if nueva_semana.strip():
                    st.success(f"¡Semana '{nueva_semana}' lista para configurar!")
                    if nueva_semana not in semanas_registradas:
                        semanas_registradas.append(nueva_semana)

        with col_h2:
            st.markdown("### 🗑️ Eliminar Semana")
            sem_a_eliminar = st.selectbox("Seleccionar semana a eliminar", semanas_registradas, key="del_sem")
            if st.button("🗑️ Eliminar Semana Seleccionada", type="primary"):
                try:
                    supabase.table("horarios").delete().eq("sucursal_id", sucursal_activa_bd).eq("semana", sem_a_eliminar).execute()
                    st.success(f"¡Semana '{sem_a_eliminar}' eliminada!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error al eliminar semana: {ex}")

        with col_h3:
            st.markdown("### ⚙️ Semana Activa")
            semana_activa = st.selectbox("Seleccionar Semana Activa para Editar", semanas_registradas, key="active_sem")

        st.divider()
        st.markdown(f"**Editando Horarios para la Semana:** `{semana_activa}`")

        resp_trab = supabase.table("trabajadores").select("*").eq("sucursal_id", sucursal_activa_bd).execute()
        trabajadores_suc = resp_trab.data or []

        if not trabajadores_suc:
            st.warning(f"No hay empleados registrados en {sucursal_activa_display}.")
            return

        resp_horarios_sem = supabase.table("horarios").select("*").eq("sucursal_id", sucursal_activa_bd).eq("semana", semana_activa).execute()
        mapa_horarios_actuales = {str(h.get("id_empleado")): ast.literal_eval(h.get("detalle_semana", "{}")) for h in (resp_horarios_sem.data or [])}

        # Selector de horas ampliado hasta las 20:00
        opciones_horas = ["Libre", "07:00", "07:30", "08:00", "08:30", "09:00", "09:30", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00"]
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

        nuevos_horarios_guardar = {}

        for t in trabajadores_suc:
            id_emp = str(t.get("id_empleado"))
            nombre_emp = t.get("nombre")
            horario_actual_emp = mapa_horarios_actuales.get(id_emp, {})

            with st.expander(f"👤 {id_emp} - {nombre_emp}"):
                cols_dias = st.columns(7)
                detalle_emp = {}
                for idx, dia in enumerate(dias_semana):
                    with cols_dias[idx]:
                        val_actual = horario_actual_emp.get(dia, "08:00")
                        idx_default = opciones_horas.index(val_actual) if val_actual in opciones_horas else 3
                        sel_hora = st.selectbox(dia, opciones_horas, index=idx_default, key=f"{id_emp}_{dia}_{semana_activa}")
                        detalle_emp[dia] = sel_hora
                nuevos_horarios_guardar[id_emp] = detalle_emp

        if st.button("💾 Guardar Todos los Horarios de la Semana"):
            try:
                for id_emp, detalle in nuevos_horarios_guardar.items():
                    payload = {
                        "id_empleado": id_emp,
                        "sucursal_id": sucursal_activa_bd,
                        "semana": semana_activa,
                        "detalle_semana": str(detalle)
                    }
                    supabase.table("horarios").upsert(payload, on_conflict="id_empleado,semana").execute()
                st.success("¡Todos los horarios semanales se han guardado exitosamente en Supabase!")
            except Exception as e:
                st.error(f"Error al guardar horarios: {e}")

    except Exception as e:
        st.error(f"Error en gestión de horarios: {e}")


def modulo_historial_exportacion(sucursal_activa_bd, sucursal_activa_display):
    st.markdown(f"## 📜 Historial y Exportación • `{sucursal_activa_display}`")

    try:
        q = supabase.table("asistencia").select("*")
        if sucursal_activa_bd != "Todas las Sucursales":
            q = q.eq("sucursal", sucursal_activa_bd)

        datos = q.execute().data or []

        if datos:
            df_historial = pd.DataFrame(datos)
            if "sucursal" in df_historial.columns:
                df_historial["sucursal"] = df_historial["sucursal"].apply(to_display)
            st.dataframe(df_historial, use_container_width=True)

            st.divider()
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_historial.to_excel(writer, index=False, sheet_name='Historial')
                
                file_name = f"historial_{sucursal_activa_display.lower().replace(' ', '_')}.xlsx"
                st.download_button(
                    "📥 Descargar Historial en Excel (.xlsx)", 
                    data=output.getvalue(), 
                    file_name=file_name, 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            with col_h2:
                if sucursal_activa_bd != "Todas las Sucursales":
                    st.markdown("### 🗑️ Limpiar Registros por Semana")
                    semanas_historial = []
                    for _, r in df_historial.iterrows():
                        f_str = str(r.get("fecha", ""))
                        try:
                            dt_f = pd.to_datetime(f_str)
                            inicio_sem = (dt_f - timedelta(days=dt_f.weekday())).strftime("%d/%m/%Y")
                            fin_sem = (dt_f + timedelta(days=6 - dt_f.weekday())).strftime("%d/%m/%Y")
                            sem_label = f"Semana del {inicio_sem} al {fin_sem}"
                            if sem_label not in semanas_historial:
                                semanas_historial.append(sem_label)
                        except Exception:
                            pass

                    if semanas_historial:
                        sem_sel_limpiar = st.selectbox("Seleccionar semana a limpiar del historial:", semanas_historial, key="limpiar_sem_hist")
                        if st.button("🗑️ Limpiar Registros de la Semana Seleccionada", type="primary"):
                            try:
                                partes = sem_sel_limpiar.replace("Semana del ", "").split(" al ")
                                dt_ini = datetime.strptime(partes[0].strip(), "%d/%m/%Y")
                                dt_fin = datetime.strptime(partes[1].strip(), "%d/%m/%Y") + timedelta(days=1)

                                for _, r in df_historial.iterrows():
                                    f_str = str(r.get("fecha", ""))
                                    try:
                                        dt_r = pd.to_datetime(f_str)
                                        if dt_ini <= dt_r < dt_fin and r.get("id"):
                                            supabase.table("asistencia").delete().eq("id", r.get("id")).execute()
                                    except Exception:
                                        pass
                                st.success(f"¡Registros de la {sem_sel_limpiar} eliminados correctamente!")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Error al limpiar registros por semana: {ex}")
                    else:
                        st.info("No hay suficientes fechas estructuradas para filtrar por semana.")
                else:
                    st.info("Para limpiar el historial por semana, selecciona una sucursal específica.")
        else:
            st.info("No hay registros en el historial.")

    except Exception as e:
        st.error(f"Error cargando historial: {e}")


def modulo_gestion_sucursales():
    st.markdown("## ⚙️ Gestión y Creación de Sucursales")
    
    st.markdown("### ➕ Añadir Nueva Sucursal")
    nueva_suc_nombre = st.text_input("Nombre de la Nueva Sucursal (Ej. 'San Francisco', '2010', 'guacara'):")
    if st.button("🚀 Crear Sucursal"):
        if not nueva_suc_nombre.strip():
            st.error("El nombre no puede estar vacío.")
        else:
            nom = nueva_suc_nombre.strip()
            try:
                existente = supabase.table("trabajadores").select("*").eq("sucursal_id", nom).execute().data
                if existente:
                    st.warning("La sucursal ya existe en el sistema.")
                else:
                    payload_inicial = {
                        "id_empleado": f"9999-{nom[:3].upper()}",
                        "nombre": f"Administrador {nom}",
                        "pin": "1234",
                        "sucursal_id": nom
                    }
                    supabase.table("trabajadores").insert(payload_inicial).execute()
                    st.success(f"¡Sucursal **{nom}** creada exitosamente!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error al crear la sucursal: {e}")

    st.divider()

    sucs_bd = obtener_lista_sucursales_bd()
    if sucs_bd:
        opciones_display = [to_display(s) for s in sucs_bd]
        sucursal_elegida_display = st.selectbox("Seleccione Sucursal Existente a Administrar:", opciones_display, key="admin_suc")
        sucursal_elegida_bd = to_db(sucursal_elegida_display)

        st.markdown("### ✏️ Renombrar Sucursal")
        nuevo_nombre = st.text_input("Nuevo Nombre:", value=sucursal_elegida_display)
        if st.button("💾 Aplicar Nuevo Nombre"):
            if nuevo_nombre.strip() and nuevo_nombre.strip() != sucursal_elegida_display:
                nuevo_val = nuevo_nombre.strip()
                try:
                    supabase.table("trabajadores").update({"sucursal_id": nuevo_val}).eq("sucursal_id", sucursal_elegida_bd).execute()
                    supabase.table("horarios").update({"sucursal_id": nuevo_val}).eq("sucursal_id", sucursal_elegida_bd).execute()
                    supabase.table("asistencia").update({"sucursal": nuevo_val}).eq("sucursal", sucursal_elegida_bd).execute()
                    st.success(f"¡Renombrada a **{nuevo_val}** con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        st.divider()
        st.markdown("### 🗑️ Eliminar Sucursal")
        if st.button("❌ Eliminar Sucursal y Datos", type="primary"):
            try:
                supabase.table("asistencia").delete().eq("sucursal", sucursal_elegida_bd).execute()
                supabase.table("horarios").delete().eq("sucursal_id", sucursal_elegida_bd).execute()
                supabase.table("trabajadores").delete().eq("sucursal_id", sucursal_elegida_bd).execute()
                st.success("¡Sucursal eliminada por completo!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


if __name__ == "__main__":
    main()
