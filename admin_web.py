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
                            "Sucursal": sucursal_activa_display,
                            "ID": id_emp,
                            "Empleado": nombre_emp,
                            "Día": dia_hoy_nombre
                        })

            if ausentes:
                st.dataframe(pd.DataFrame(ausentes), use_container_width=True)
            else:
                st.success("✨ Todo el personal programado ha fichado hoy.")

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
    st.markdown("## 📅 Gestión y Asignación de Horarios")
    
    if sucursal_activa_bd == "Todas las Sucursales":
        st.warning("⚠️ Selecciona una **sucursal específica** en la barra lateral para configurar horarios.")
        return

    try:
        resp_trab = supabase.table("trabajadores").select("*").eq("sucursal_id", sucursal_activa_bd).execute()
        trabajadores_suc = resp_trab.data or []

        if not trabajadores_suc:
            st.warning(f"No hay empleados en {sucursal_activa_display}.")
            return

        empleado_opciones = {f"{t.get('id_empleado')} - {t.get('nombre')}": t.get('id_empleado') for t in trabajadores_suc}
        emp_key_sel = st.selectbox("Seleccionar Empleado:", list(empleado_opciones.keys()))
        id_emp_elegido = empleado_opciones[emp_key_sel]

        semana_input = st.text_input("Identificador de Semana:", value="Semana Actual (General)")

        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        with col_d1:
            lun = st.text_input("Lunes", value="08:00")
            mart = st.text_input("Martes", value="08:00")
        with col_d2:
            mier = st.text_input("Miércoles", value="08:00")
            juev = st.text_input("Jueves", value="08:00")
        with col_d3:
            vier = st.text_input("Viernes", value="08:00")
            sab = st.text_input("Sábado", value="08:00")
        with col_d4:
            dom = st.text_input("Domingo", value="Libre")

        if st.button("💾 Guardar Horario"):
            detalle = {"Lunes": lun, "Martes": mart, "Miércoles": mier, "Jueves": juev, "Viernes": vier, "Sábado": sab, "Domingo": dom}
            payload = {"id_empleado": str(id_emp_elegido), "sucursal_id": sucursal_activa_bd, "semana": semana_input, "detalle_semana": str(detalle)}
            try:
                supabase.table("horarios").upsert(payload, on_conflict="id_empleado,semana").execute()
                st.success("¡Horario guardado correctamente!")
            except Exception as e:
                st.error(f"Error: {e}")

        st.divider()
        resp_h = supabase.table("horarios").select("*").eq("sucursal_id", sucursal_activa_bd).execute()
        if resp_h.data:
            df_h = pd.DataFrame(resp_h.data)
            if "sucursal_id" in df_h.columns:
                df_h["sucursal_id"] = df_h["sucursal_id"].apply(to_display)
            st.dataframe(df_h, use_container_width=True)
    except Exception as e:
        st.error(f"Error en horarios: {e}")


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
                    if st.button("🗑️ Limpiar Historial de esta Sucursal", type="primary"):
                        try:
                            supabase.table("asistencia").delete().eq("sucursal", sucursal_activa_bd).execute()
                            st.success(f"¡Historial de {sucursal_activa_display} eliminado correctamente!")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error al limpiar historial: {ex}")
                else:
                    st.info("Para limpiar el historial, selecciona una sucursal específica.")
        else:
            st.info("No hay registros en el historial.")

    except Exception as e:
        st.error(f"Error cargando historial: {e}")


def modulo_gestion_sucursales():
    st.markdown("## ⚙️ Gestión y Creación de Sucursales")
    
    st.markdown("### ➕ Añadir Nueva Sucursal")
    nueva_suc_nombre = st.text_input("Nombre de la Nueva Sucursal (Ej. 'San Francisco'):")
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
