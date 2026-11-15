import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd
import ast
import io

# Configuración de conexión a Supabase
SUPABASE_URL = "https://gmhksbvjjnluoadwjuu.supabase.co"
SUPABASE_KEY = "TU_KEY_ANON_DE_SUPABASE"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# Mapeo visual para renombrar "Sucursal Principal" a "Hugo Oliveros" en la interfaz sin alterar la BD
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
    """Obtiene la lista única de sucursales reales en Supabase"""
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
    st.set_page_config(page_title="Gestión y Auditoría Multi-Sucursal", layout="wide")
    
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
    
    menu = st.sidebar.radio(
        "Navegación", 
        [
            "📊 Auditoría y Sincronización", 
            "🚨 Alertas, Incidencias y Ausencias",
            "👥 Gestión de Personal",
            "📅 Gestión de Horarios", 
            "📜 Historial y Exportación",
            "⚙️ Gestión de Sucursales"
        ]
    )

    st.title("🏢 Panel Corporativo • Control de Asistencia")
    st.markdown(f"**Sucursal Activa en Vista:** `{sucursal_activa_display}`")
    st.divider()

    if menu == "📊 Auditoría y Sincronización":
        modulo_auditoria_completa(sucursal_activa_bd, sucursal_activa_display)
    elif menu == "🚨 Alertas, Incidencias y Ausencias":
        modulo_alertas_incidencias(sucursal_activa_bd, sucursal_activa_display)
    elif menu == "👥 Gestión de Personal":
        modulo_gestion_personal(sucursal_activa_bd, sucursal_activa_display)
    elif menu == "📅 Gestión de Horarios":
        modulo_gestion_horarios(sucursal_activa_bd, sucursal_activa_display)
    elif menu == "📜 Historial y Exportación":
        modulo_historial_exportacion(sucursal_activa_bd, sucursal_activa_display)
    elif menu == "⚙️ Gestión de Sucursales":
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
    st.markdown("## 🚨 Panel de Alertas, Incidencias y Ausencias del Día")

    if sucursal_activa_bd == "Todas las Sucursales":
        st.warning("⚠️ Por favor, selecciona una **sucursal específica** en la barra lateral para gestionar alertas o ausencias.")

    try:
        q_asis = supabase.table("asistencia").select("*")
        q_trab = supabase.table("trabajadores").select("*")
        q_hor = supabase.table("horarios").select("*")

        if sucursal_activa_bd != "Todas las Sucursales":
            q_asis = q_asis.eq("sucursal", sucursal_activa_bd)
            q_trab = q_trab.eq("sucursal_id", sucursal_activa_bd)
            q_hor = q_hor.eq("sucursal_id", sucursal_activa_bd)

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

            if incidencias:
                df_inc = pd.DataFrame(incidencias)
                cols_mostrar = [c for c in df_inc.columns if c != "ID"]
                st.dataframe(df_inc[cols_mostrar], use_container_width=True)

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_inc[cols_mostrar].to_excel(writer, index=False, sheet_name='Incidencias')
                    st.download_button(
                        "📥 Descargar Excel", 
                        data=output.getvalue(), 
                        file_name=f"incidencias_{sucursal_activa_display.lower().replace(' ', '_')}.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                with col_btn2:
                    if sucursal_activa_bd != "Todas las Sucursales":
                        if st.button("🧹 Limpiar Alertas"):
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
            else:
                st.success("✅ Sin incidencias registradas.")

        with col_al2:
            st.markdown("### 👤 Ausencias del Día")
            dias_map = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
            dia_hoy_nombre = dias_map.get(datetime.now().weekday())

            fichajes_hoy = []
            hoy_fecha_corta = datetime.now().date()
            for r in datos_asis:
                try:
                    f_dt = pd.to_datetime(r.get('fecha')).date()
                    if f_dt == hoy_fecha_corta and "Entrada" in str(r.get('tipo', '')):
                        fichajes_hoy.append(str(r.get('empleado')))
                except Exception:
                    pass

            ausentes = []
            for t in trabajadores_suc:
                id_emp = str(t.get('id_empleado', ''))
                nombre_emp = str(t.get('nombre', ''))

                if id_emp not in fichajes_hoy and nombre_emp not in fichajes_hoy:
                    tiene_horario_hoy = False
                    for h in horarios_suc:
                        if str(h.get('id_empleado')) == id_emp:
                            try:
                                detalle = ast.literal_eval(h.get('detalle_semana', '{}'))
                                if detalle.get(dia_hoy_nombre, "Libre") != "Libre":
                                    tiene_horario_hoy = True
                                    break
                            except Exception:
                                pass
                    
                    if tiene_horario_hoy:
                        ausentes.append({
                            "Sucursal":
