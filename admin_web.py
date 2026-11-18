import streamlit as st
import pandas as pd
from supabase import create_client
import io
from datetime import datetime, timedelta, timezone
import ast

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Sistema Profesional de Control de Asistencia",
    page_icon="🏢",
    layout="wide"
)

# Hora actual local exacta para Venezuela
def ahora_venezuela_naive():
    """Devuelve la hora actual del sistema adaptada a la hora local sin tzinfo."""
    TZ_VENEZUELA = timezone(timedelta(hours=-4))
    return datetime.now(TZ_VENEZUELA).replace(tzinfo=None)

def normalizar_fecha_naive(dt_val):
    """
    Extrae la hora local exacta tal como fue registrada, 
    eliminando cualquier desfase UTC o conversión de huso horario.
    """
    if pd.isna(dt_val):
        return None
    
    if isinstance(dt_val, str):
        dt_limpio = dt_val.split("+")[0].split("Z")[0].split(".")[0]
        try:
            return datetime.fromisoformat(dt_limpio)
        except Exception:
            pass
            
    dt_pd = pd.to_datetime(dt_val, errors='coerce')
    if pd.isna(dt_pd):
        return None
        
    if hasattr(dt_pd, "to_pydatetime"):
        dt_pd = dt_pd.to_pydatetime()
        
    # Eliminar la zona horaria directamente SIN restar horas (mantiene la hora local pura)
    if getattr(dt_pd, "tzinfo", None) is not None:
        return dt_pd.replace(tzinfo=None)
        
    return dt_pd

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

def auto_cerrar_turnos_excedidos():
    """
    Cierra automáticamente con 'Salida (Cierre Automático +15h)' cualquier turno
    que lleve más de 15 horas abierto tomando como punto de partida la Entrada.
    """
    try:
        resp = supabase.table("asistencia").select("*").execute()
        asistencia_data = resp.data or []
        if not asistencia_data:
            return 0

        df_asis = pd.DataFrame(asistencia_data)
        if 'fecha' not in df_asis.columns or 'empleado' not in df_asis.columns:
            return 0

        df_asis['fecha_dt'] = pd.to_datetime(df_asis['fecha'], errors='coerce')
        df_asis_sorted = df_asis.dropna(subset=['fecha_dt']).sort_values(by='fecha_dt')

        ahora_ve = ahora_venezuela_naive()
        cerrados = 0
        for emp, grupo in df_asis_sorted.groupby('empleado'):
            entradas = grupo[grupo['tipo'].astype(str).str.contains("Entrada", na=False)]
            if entradas.empty:
                continue

            ultima_entrada = entradas.iloc[-1]
            fecha_entrada_raw = ultima_entrada['fecha_dt']
            fecha_entrada = normalizar_fecha_naive(fecha_entrada_raw)

            movimientos_posteriores = grupo[grupo['fecha_dt'] > fecha_entrada_raw]
            tiene_salida = movimientos_posteriores['tipo'].astype(str).str.contains("Salida", na=False).any()

            if not tiene_salida and fecha_entrada is not None:
                tiempo_transcurrido = ahora_ve - fecha_entrada

                if tiempo_transcurrido > timedelta(hours=15):
                    suc_emp = ultima_entrada.get('sucursal', ultima_entrada.get('sucursal_id', 'Sucursal Principal'))
                    fecha_cierre = (fecha_entrada + timedelta(hours=15)).isoformat()

                    payload_cierre = {
                        "empleado": emp,
                        "sucursal": suc_emp,
                        "tipo": "Salida (Cierre Automático +15h)",
                        "fecha": fecha_cierre
                    }
                    supabase.table("asistencia").insert(payload_cierre).execute()
                    cerrados += 1
        return cerrados
    except Exception:
        return 0

def main():
    # Ejecutar cierre automático silencioso al cargar el panel
    turnos_cerrados_auto = auto_cerrar_turnos_excedidos()
    if turnos_cerrados_auto > 0:
        st.toast(f"🔄 Se cerraron automáticamente {turnos_cerrados_auto} turno(s) con más de 15 horas abiertas.", icon="⏱️")

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
        
        q_trab = supabase.table("trabajadores").select("id_empleado, nombre, sucursal_id")
        if sucursal_activa_bd != "Todas las Sucursales":
            q_trab = q_trab.eq("sucursal_id", sucursal_activa_bd)
        trabajadores_oficiales = q_trab.execute().data or []
        ids_oficiales = {str(t.get("id_empleado")).strip() for t in trabajadores_oficiales}

        if not asistencia_data:
            st.info("No se encontraron registros de asistencia en la base de datos.")
            return

        df_asis = pd.DataFrame(asistencia_data)

        if sucursal_activa_bd != "Todas las Sucursales":
            cond = False
            if 'sucursal' in df_asis.columns:
                cond = cond | (df_asis['sucursal'] == sucursal_activa_bd) | (df_asis['sucursal'] == sucursal_activa_display)
            if 'sucursal_id' in df_asis.columns:
                cond = cond | (df_asis['sucursal_id'] == sucursal_activa_bd) | (df_asis['sucursal_id'] == sucursal_activa_display)
            df_asis = df_asis[cond]

        if df_asis.empty:
            st.info(f"No hay registros para {sucursal_activa_display}.")
            return

        # --- TURNOS ABIERTOS ---
        st.markdown("### 🔴 Turnos Abiertos (Pendientes de Salida)")
        turnos_abiertos = []
        ids_turnos_abiertos = []
        ahora_ve = ahora_venezuela_naive()
        
        if 'fecha' in df_asis.columns and 'empleado' in df_asis.columns:
            df_asis['fecha_dt'] = pd.to_datetime(df_asis['fecha'], errors='coerce')
            df_asis_sorted = df_asis.dropna(subset=['fecha_dt']).sort_values(by='fecha_dt')

            for emp, grupo in df_asis_sorted.groupby('empleado'):
                emp_str = str(emp).split(" - ")[0].strip()
                if ids_oficiales and emp_str not in ids_oficiales:
                    continue

                ultimo_movimiento = grupo.iloc[-1]
                tipo_ult = str(ultimo_movimiento.get('tipo', ''))
                
                if "Salida" not in tipo_ult:
                    entradas_grupo = grupo[grupo['tipo'].astype(str).str.contains("Entrada", na=False)]
                    if not entradas_grupo.empty:
                        mov_entrada_real = entradas_grupo.iloc[-1]
                        fecha_ent_naive = normalizar_fecha_naive(mov_entrada_real['fecha_dt'])
                    else:
                        fecha_ent_naive = normalizar_fecha_naive(ultimo_movimiento.get('fecha_dt'))

                    suc_emp_bd = ultimo_movimiento.get('sucursal', ultimo_movimiento.get('sucursal_id', 'N/D'))
                    suc_emp_display = to_display(suc_emp_bd)

                    if fecha_ent_naive is not None:
                        tiempo_transcurrido = ahora_ve - fecha_ent_naive
                        segundos_totales = max(0, tiempo_transcurrido.total_seconds())
                        horas_abierto = round(segundos_totales / 3600, 1)

                        turnos_abiertos.append({
                            "ID": ultimo_movimiento.get("id"),
                            "Sucursal": suc_emp_display,
                            "Empleado": emp,
                            "Último Movimiento": tipo_ult,
                            "Fecha/Hora Marcaje": fecha_ent_naive.strftime("%d/%m/%Y %I:%M %p"),
                            "Horas Transcurridas": f"{horas_abierto} hrs"
                        })
                        if ultimo_movimiento.get("id") is not None:
                            ids_turnos_abiertos.append(ultimo_movimiento.get("id"))

        if turnos_abiertos:
            df_t_abiertos = pd.DataFrame(turnos_abiertos)
            st.dataframe(df_t_abiertos.drop(columns=["ID"]), use_container_width=True)
            
            if st.button("🧹 Limpiar / Borrar Turnos Abiertos Mostrados", type="primary", key="btn_limpiar_turnos"):
                try:
                    for reg_id in ids_turnos_abiertos:
                        supabase.table("asistencia").delete().eq("id", reg_id).execute()
                    st.success("¡Turnos abiertos eliminados correctamente en Supabase!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error al limpiar turnos abiertos: {ex}")
        else:
            st.success("✅ Sin turnos abiertos pendientes (los mayores a 15h se cierran automáticamente).")

        st.divider()
        
        # --- LOGS DE SINCRONIZACIÓN ---
        st.markdown("### 🔄 Auditoría de Logs de Sincronización")
        logs_sinc = []
        ids_logs = []
        df_asis_desc = df_asis.sort_values(by='fecha', ascending=False)
        
        for _, r in df_asis_desc.iterrows():
            emp_val = str(r.get('empleado', '')).split(" - ")[0].strip()
            if ids_oficiales and emp_val not in ids_oficiales:
                continue

            f_local_str = str(r.get('fecha', ''))
            f_creado_nube = str(r.get('created_at', r.get('fecha', '')))
            try:
                dt_local = normalizar_fecha_naive(pd.to_datetime(f_local_str))
                dt_nube = normalizar_fecha_naive(pd.to_datetime(f_creado_nube))
                diferencia_minutos = abs((dt_nube - dt_local).total_seconds() / 60)
                
                estado_sync = "🟢 En Línea (Tiempo Real)"
                if "Cierre Automático" in str(r.get('tipo', '')):
                    estado_sync = "⏱️ Cierre Automático (+15h)"
                elif diferencia_minutos > 3:
                    estado_sync = f"🟠 Sincronizado Offline (+{int(diferencia_minutos)} min)"

                suc_bd_log = r.get('sucursal', r.get('sucursal_id', 'N/D'))
                logs_sinc.append({
                    "ID": r.get("id"),
                    "Sucursal": to_display(suc_bd_log),
                    "Empleado": r.get('empleado', 'N/D'),
                    "Movimiento": r.get('tipo', 'N/D'),
                    "Hora Marcaje Local": dt_local.strftime("%d/%m/%Y %I:%M %p"),
                    "Estado / Sincronización": estado_sync
                })
                if r.get("id") is not None:
                    ids_logs.append(r.get("id"))
            except Exception:
                pass

        if logs_sinc:
            df_logs = pd.DataFrame(logs_sinc)
            st.dataframe(df_logs.drop(columns=["ID"]).head(25), use_container_width=True)
            
            if st.button("🧹 Limpiar / Borrar Logs de Sincronización", type="primary", key="btn_limpiar_logs"):
                try:
                    for reg_id in ids_logs:
                        supabase.table("asistencia").delete().eq("id", reg_id).execute()
                    st.success("¡Logs de sincronización eliminados con éxito en Supabase!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error al limpiar logs: {ex}")
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
        q_asis = supabase.table("asistencia").select("*")
        datos_asis = q_asis.execute().data or []
        
        q_trab = supabase.table("trabajadores").select("*").eq("sucursal_id", sucursal_activa_bd)
        trabajadores_suc = q_trab.execute().data or []
        ids_empleados_oficiales = {str(t.get("id_empleado")).strip() for t in trabajadores_suc}

        q_hor = supabase.table("horarios").select("*").eq("sucursal_id", sucursal_activa_bd)
        horarios_suc = q_hor.execute().data or []

        datos_sucursal = []
        for r in datos_asis:
            s_val = str(r.get("sucursal", r.get("sucursal_id", "")))
            if s_val == sucursal_activa_bd or s_val == sucursal_activa_display or sucursal_activa_bd == "Todas las Sucursales":
                emp_id_val = str(r.get("empleado", "")).split(" - ")[0].strip()
                if emp_id_val in ids_empleados_oficiales:
                    datos_sucursal.append(r)

        col_al1, col_al2 = st.columns(2)

        with col_al1:
            st.markdown("### ⚠️ Incidencias (Tardanzas y Excesos)")
            incidencias = []
            ids_incidencias = []
            
            for r in datos_sucursal:
                tipo = str(r.get("tipo", ""))
                if "Tarde" in tipo or "Exceso" in tipo:
                    f_str = str(r.get("fecha", ""))
                    try:
                        dt_f = normalizar_fecha_naive(pd.to_datetime(f_str)).strftime("%d/%m/%Y %I:%M %p")
                    except Exception:
                        dt_f = f_str

                    incidencias.append({
                        "ID": r.get("id"),
                        "Empleado": r.get("empleado", "N/D"),
                        "Incidencia": tipo,
                        "Fecha y Hora": dt_f
                    })
                    if r.get("id") is not None:
                        ids_incidencias.append(r.get("id"))

            df_inc = pd.DataFrame(incidencias) if incidencias else pd.DataFrame(columns=["Empleado", "Incidencia", "Fecha y Hora"])
            cols_mostrar = [c for c in df_inc.columns if c != "ID"]
            st.dataframe(df_inc[cols_mostrar], use_container_width=True)

            if incidencias:
                if st.button("🧹 Borrar / Limpiar Todas las Incidencias", type="primary", key="btn_limpiar_inc"):
                    try:
                        for reg_id in ids_incidencias:
                            supabase.table("asistencia").delete().eq("id", reg_id).execute()
                        st.success("¡Datos de incidencias eliminados de Supabase correctamente!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error al limpiar incidencias: {ex}")
            else:
                st.success("✅ Sin incidencias registradas.")

        with col_al2:
            st.markdown("### 👤 Ausencias (Días Pasados)")
            dias_map_orden = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4, "Sábado": 5, "Domingo": 6}
            
            fichajes_por_fecha = set()
            for r in datos_sucursal:
                emp_id_val = str(r.get("empleado", "")).split(" - ")[0].strip()
                try:
                    f_dt = normalizar_fecha_naive(pd.to_datetime(r.get('fecha')))
                    f_corta = f_dt.date()
                    if "Entrada" in str(r.get('tipo', '')):
                        fichajes_por_fecha.add((emp_id_val, f_corta))
                except Exception:
                    pass

            ausencias = []
            hoy = ahora_venezuela_naive().date()
            inicio_semana_actual = hoy - timedelta(days=hoy.weekday())

            for h in horarios_suc:
                id_emp = str(h.get('id_empleado')).strip()
                if id_emp not in ids_empleados_oficiales:
                    continue

                try:
                    detalle = ast.literal_eval(h.get('detalle_semana', '{}'))
                except Exception:
                    continue
                
                nombre_emp = id_emp
                for t in trabajadores_suc:
                    if str(t.get('id_empleado')).strip() == id_emp:
                        nombre_emp = t.get('nombre')
                        break

                for nombre_dia, idx_dia in dias_map_orden.items():
                    dia_evaluar = inicio_semana_actual + timedelta(days=idx_dia)
                    if dia_evaluar < hoy:
                        turno_hora = str(detalle.get(nombre_dia, "Libre")).strip().lower()
                        if turno_hora != "libre" and turno_hora != "" and turno_hora != "none":
                            if (id_emp, dia_evaluar) not in fichajes_por_fecha:
                                ausencias.append({
                                    "Fecha": dia_evaluar.strftime("%d/%m/%Y"),
                                    "Día": nombre_dia,
                                    "ID_EMP": id_emp,
                                    "Empleado": nombre_emp
                                })

            df_aus = pd.DataFrame(ausencias) if ausencias else pd.DataFrame(columns=["Fecha", "Día", "ID_EMP", "Empleado"])
            st.dataframe(df_aus, use_container_width=True)

            if ausencias:
                st.markdown("#### 🧹 Justificar / Limpiar Ausencia")
                emp_aus_opciones = {f"{a['Empleado']} ({a['Fecha']} - {a['Día']})": a for a in ausencias}
                sel_aus_key = st.selectbox("Seleccionar ausencia a justificar:", list(emp_aus_opciones.keys()), key="sel_justificar_aus")
                
                if st.button("✅ Justificar Ausencia Seleccionada", type="primary"):
                    item_sel = emp_aus_opciones[sel_aus_key]
                    try:
                        dt_aus_parse = datetime.strptime(item_sel["Fecha"], "%d/%m/%Y").replace(hour=8, minute=0)
                        payload_justificacion = {
                            "empleado": f"{item_sel['ID_EMP']} - {item_sel['Empleado']}",
                            "sucursal": sucursal_activa_bd,
                            "tipo": "Entrada (Justificada)",
                            "fecha": dt_aus_parse.isoformat()
                        }
                        supabase.table("asistencia").insert(payload_justificacion).execute()
                        st.success(f"¡Ausencia de {item_sel['Empleado']} justificada con éxito!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error al justificar ausencia: {ex}")

        st.divider()
        st.markdown("### 📥 Descargar Reporte Consolidado (3 Hojas)")
        if st.button("📦 Generar Libro Excel con Ausencias, Incidencias e Historial"):
            output = io.BytesIO()
            df_historial = pd.DataFrame(datos_sucursal)
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
        semanas_bd = [h.get("semana") for h in (resp_h.data or []) if h.get("semana")]
        
        if "semanas_creadas_local" not in st.session_state:
            st.session_state.semanas_creadas_local = []
            
        semanas_registradas = sorted(list(set(semanas_bd + st.session_state.semanas_creadas_local)))
        if not semanas_registradas:
            semanas_registradas = ["Semana Actual (General)"]

        col_h1, col_h2, col_h3 = st.columns(3)
        
        with col_h1:
            st.markdown("### ➕ Añadir Semana")
            hoy = ahora_venezuela_naive()
            lunes_actual = hoy - timedelta(days=hoy.weekday())
            opciones_semanas_sugeridas = []
            for w in range(4):
                inicio_w = lunes_actual + timedelta(weeks=w)
                fin_w = inicio_w + timedelta(days=5)
                opciones_semanas_sugeridas.append(f"Semana del {inicio_w.strftime('%d/%m/%Y')} al {fin_w.strftime('%d/%m/%Y')}")

            tipo_creacion = st.radio("Método:", ["Seleccionar Sugerida", "Personalizada"], horizontal=True, key="tipo_creacion_sem")
            if tipo_creacion == "Seleccionar Sugerida":
                nueva_semana = st.selectbox("Seleccionar Rango de Semana:", opciones_semanas_sugeridas, key="sel_sug_sem")
            else:
                nueva_semana = st.text_input("Escribir identificador:", key="input_pers_sem")

            if st.button("Crear Semana", key="btn_crear_sem_accion"):
                if nueva_semana.strip():
                    if nueva_semana not in st.session_state.semanas_creadas_local:
                        st.session_state.semanas_creadas_local.append(nueva_semana.strip())
                    st.success(f"¡Semana '{nueva_semana}' creada con éxito!")
                    st.rerun()

        with col_h2:
            st.markdown("### 🗑️ Eliminar Semana")
            sem_a_eliminar = st.selectbox("Seleccionar semana a eliminar", semanas_registradas, key="del_sem")
            if st.button("🗑️ Eliminar Semana Seleccionada", type="primary", key="btn_del_sem_accion"):
                try:
                    supabase.table("horarios").delete().eq("sucursal_id", sucursal_activa_bd).eq("semana", sem_a_eliminar).execute()
                    if sem_a_eliminar in st.session_state.semanas_creadas_local:
                        st.session_state.semanas_creadas_local.remove(sem_a_eliminar)
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
        mapa_horarios_actuales = {}
        for h in (resp_horarios_sem.data or []):
            try:
                mapa_horarios_actuales[str(h.get("id_empleado")).strip()] = ast.literal_eval(h.get("detalle_semana", "{}"))
            except Exception:
                pass

        opciones_horas = ["Libre"]
        for hora in range(7, 21):
            opciones_horas.append(f"{hora:02d}:00")
            if hora < 20:
                opciones_horas.append(f"{hora:02d}:30")

        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        nuevos_horarios_guardar = {}

        for t in trabajadores_suc:
            id_emp = str(t.get("id_empleado")).strip()
            nombre_emp = t.get("nombre")
            horario_actual_emp = mapa_horarios_actuales.get(id_emp, {})

            with st.expander(f"👤 {id_emp} - {nombre_emp}"):
                cols_dias = st.columns(7)
                detalle_emp = {}
                for idx, dia in enumerate(dias_semana):
                    with cols_dias[idx]:
                        val_actual = str(horario_actual_emp.get(dia, "08:00")).strip()
                        if val_actual not in opciones_horas:
                            val_actual = "08:00"
                        idx_default = opciones_horas.index(val_actual)
                        
                        widget_key = f"horario_{sucursal_activa_bd}_{id_emp}_{dia}_{semana_activa}"
                        sel_hora = st.selectbox(dia, opciones_horas, index=idx_default, key=widget_key)
                        detalle_emp[dia] = st.session_state.get(widget_key, sel_hora)
                nuevos_horarios_guardar[id_emp] = detalle_emp

        if st.button("💾 Guardar Todos los Horarios de la Semana", key="btn_guardar_horarios_accion", type="primary"):
            try:
                contador_guardados = 0
                for id_emp, detalle in nuevos_horarios_guardar.items():
                    existe_resp = supabase.table("horarios")\
                        .select("id")\
                        .eq("id_empleado", id_emp)\
                        .eq("sucursal_id", sucursal_activa_bd)\
                        .eq("semana", semana_activa)\
                        .execute()
                    
                    filas_existentes = existe_resp.data or []
                    if filas_existentes:
                        supabase.table("horarios")\
                            .update({"detalle_semana": str(detalle)})\
                            .eq("id", filas_existentes[0]["id"])\
                            .execute()
                    else:
                        payload = {
                            "id_empleado": id_emp,
                            "sucursal_id": sucursal_activa_bd,
                            "semana": semana_activa,
                            "detalle_semana": str(detalle)
                        }
                        supabase.table("horarios").insert(payload).execute()
                    contador_guardados += 1
                
                st.success(f"¡Se guardaron exitosamente los horarios de {contador_guardados} empleado(s) en Supabase!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar horarios: {e}")

    except Exception as e:
        st.error(f"Error en gestión de horarios: {e}")


def modulo_historial_exportacion(sucursal_activa_bd, sucursal_activa_display):
    st.markdown(f"## 📜 Historial y Exportación • `{sucursal_activa_display}`")

    try:
        q = supabase.table("asistencia").select("*")
        datos = q.execute().data or []

        datos_sucursal = []
        ids_historial = []
        for r in datos:
            s_val = str(r.get("sucursal", r.get("sucursal_id", "")))
            if s_val == sucursal_activa_bd or s_val == sucursal_activa_display or sucursal_activa_bd == "Todas las Sucursales":
                datos_sucursal.append(r)
                if r.get("id") is not None:
                    ids_historial.append(r.get("id"))

        if datos_sucursal:
            df_historial = pd.DataFrame(datos_sucursal)
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
                    st.markdown("### 🗑️ Limpiador de Historial y Exportación")
                    
                    if st.button("🧹 Borrar TODO el Historial de esta Sucursal", type="primary", key="btn_borrar_todo_hist"):
                        try:
                            for reg_id in ids_historial:
                                supabase.table("asistencia").delete().eq("id", reg_id).execute()
                            st.success(f"¡Todo el historial de {sucursal_activa_display} fue borrado con éxito en Supabase!")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error al limpiar historial: {ex}")

                    st.divider()

                    st.markdown("### 🗑️ Limpiar Registros por Semana")
                    semanas_historial = []
                    for _, r in df_historial.iterrows():
                        f_str = str(r.get("fecha", ""))
                        try:
                            dt_f = normalizar_fecha_naive(pd.to_datetime(f_str))
                            inicio_sem = (dt_f - timedelta(days=dt_f.weekday())).strftime("%d/%m/%Y")
                            fin_sem = (dt_f + timedelta(days=6 - dt_f.weekday())).strftime("%d/%m/%Y")
                            sem_label = f"Semana del {inicio_sem} al {fin_sem}"
                            if sem_label not in semanas_historial:
                                semanas_historial.append(sem_label)
                        except Exception:
                            pass

                    if semanas_historial:
                        sem_sel_limpiar = st.selectbox("Seleccionar semana a limpiar:", semanas_historial, key="limpiar_sem_hist")
                        if st.button("🗑️ Borrar Historial de la Semana Seleccionada", key="btn_borrar_sem_hist"):
                            try:
                                partes = sem_sel_limpiar.replace("Semana del ", "").split(" al ")
                                dt_ini = datetime.strptime(partes[0].strip(), "%d/%m/%Y")
                                dt_fin = datetime.strptime(partes[1].strip(), "%d/%m/%Y") + timedelta(days=1)

                                eliminados = 0
                                for _, r in df_historial.iterrows():
                                    f_str = str(r.get("fecha", ""))
                                    try:
                                        dt_r = normalizar_fecha_naive(pd.to_datetime(f_str))
                                        if dt_ini <= dt_r < dt_fin and r.get("id") is not None:
                                            supabase.table("asistencia").delete().eq("id", r.get("id")).execute()
                                            eliminados += 1
                                    except Exception:
                                        pass
                                
                                st.success(f"¡Se eliminaron {eliminados} registros de la {sem_sel_limpiar} en Supabase!")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Error al limpiar registros por semana: {ex}")
                else:
                    st.info("Para usar los limpiadores, selecciona una sucursal específica.")
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

