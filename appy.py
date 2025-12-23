import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
import re
from datetime import datetime
import glob
import time

# ===================== CONFIGURACIÓN DE PÁGINA =====================
st.set_page_config(
    page_title="IPS GOLEMAN APP",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===================== FORMATOS =====================
def formato_pesos(x):
    try:
        return "$ {:,.0f}".format(x).replace(",", ".")
    except:
        return x

def formato_cedula(x):
    try:
        return "Cédula: {:,.0f}".format(x).replace(",", ".")
    except:
        return x

def formato_edad(x):
    try:
        return f"{int(x)} años"
    except:
        return x

# ===================== PERSISTENCIA =====================
STATE_FILE = "user_state.json"
ARCHIVO_FECHA = "fecha_update.txt"

def guardar_meta(nombre_archivo, valor):
    with open(nombre_archivo, "w") as f:
        f.write(str(valor))

def cargar_meta(nombre_archivo):
    if os.path.exists(nombre_archivo):
        with open(nombre_archivo, "r") as f:
            try:
                return float(f.read().strip())
            except:
                return 0
    return 0

def guardar_fecha_actualizacion():
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with open(ARCHIVO_FECHA, "w") as f:
        f.write(now)
    return now

def cargar_fecha_actualizacion():
    if os.path.exists(ARCHIVO_FECHA):
        with open(ARCHIVO_FECHA, "r") as f:
            return f.read().strip()
    return "Sin actualizaciones"

def guardar_excel(df, nombre_archivo="base_guardada.xlsx"):
    df.to_excel(nombre_archivo, index=False)

def cargar_excel(nombre_archivo="base_guardada.xlsx"):
    if os.path.exists(nombre_archivo):
        try:
            return pd.read_excel(nombre_archivo)
        except:
            return None
    return None

# ===================== LÓGICA DE NEGOCIO (MIGRADA) =====================
def find_col(df, candidates):
    for col in df.columns:
        if any(cand.lower() in str(col).lower() for cand in candidates):
            return col
    return None

def leer_excel(file_obj1, file_obj2=None):
    # En Streamlit, file_obj1 y file_obj2 son objetos UploadedFile
    
    # Si no se sube nada, intentar cargar de memoria o disco
    if file_obj1 is None and file_obj2 is None:
        if 'df' in st.session_state and st.session_state.df is not None:
            return st.session_state.df
        return cargar_excel()

    try:
        df1 = pd.DataFrame()
        df2 = pd.DataFrame()

        if file_obj1 is not None:
            df1 = pd.read_excel(file_obj1, engine="openpyxl")
        
        if file_obj2 is not None:
            df2 = pd.read_excel(file_obj2, engine="openpyxl")

        # --- LIMPIEZA PRELIMINAR DE PROFESIONAL EN DF1 ---
        col_prof1 = find_col(df1, ["profesional", "nombre profesional"])
        if col_prof1:
             df1[col_prof1] = df1[col_prof1].astype(str).str.replace(r'^\d+\s*[-]?\s*', '', regex=True).str.strip()

        # Lógica de unión / consolidación
        if not df1.empty and not df2.empty:
            col_code1 = find_col(df1, ["codigo procedimiento", "cod procedimiento", "codigo", "cups"])
            col_code2 = find_col(df2, ["codigo procedimiento", "cod procedimiento", "codigo", "cups"])
            
            col_name1 = find_col(df1, ["nombre procedimiento", "procedimiento", "descripcion", "nombre"])
            col_name2 = find_col(df2, ["nombre procedimiento", "procedimiento", "descripcion", "nombre"])
            
            col_val_unit2 = find_col(df2, ["valor unitario", "valor_unitario", "precio", "valor"])

            if col_val_unit2 and (col_code1 and col_code2 or col_name1 and col_name2):
                st.info(f"Consolidando archivos con búsqueda inteligente...")
                
                if col_code1: df1['_temp_code'] = df1[col_code1].astype(str).str.strip()
                if col_code2: df2['_temp_code'] = df2[col_code2].astype(str).str.strip()
                
                if col_name1: df1['_temp_name'] = df1[col_name1].astype(str).str.strip().str.lower()
                if col_name2: df2['_temp_name'] = df2[col_name2].astype(str).str.strip().str.lower()
                
                df1['__Valor_Encontrado__'] = None
                
                if col_code1 and col_code2:
                    df2_clean = df2.dropna(subset=[col_val_unit2])
                    df2_unique = df2_clean.drop_duplicates(subset=['_temp_code'])
                    price_map_code = df2_unique.set_index('_temp_code')[col_val_unit2].to_dict()
                    df1['__Valor_Encontrado__'] = df1['_temp_code'].map(price_map_code)
                
                if col_name1 and col_name2:
                    df2_clean = df2.dropna(subset=[col_val_unit2])
                    df2_unique = df2_clean.drop_duplicates(subset=['_temp_name'])
                    price_map_name = df2_unique.set_index('_temp_name')[col_val_unit2].to_dict()
                    mask_missing = df1['__Valor_Encontrado__'].isna()
                    df1.loc[mask_missing, '__Valor_Encontrado__'] = df1.loc[mask_missing, '_temp_name'].map(price_map_name)
                
                col_val_unit1 = find_col(df1, ["valor unitario", "valor_unitario", "precio unitario"])
                if not col_val_unit1:
                     col_val_unit1 = "Valor Unitario"
                     if col_val_unit1 not in df1.columns:
                        df1[col_val_unit1] = 0.0
                
                vals_nuevos = pd.to_numeric(df1['__Valor_Encontrado__'], errors='coerce')
                vals_actuales = pd.to_numeric(df1[col_val_unit1], errors='coerce').fillna(0)
                df1[col_val_unit1] = vals_nuevos.combine_first(vals_actuales)
                
                col_qty1 = find_col(df1, ["cantidad", "cant"])
                if col_qty1:
                    qtys = pd.to_numeric(df1[col_qty1], errors='coerce').fillna(1)
                else:
                    qtys = 1
                
                col_total1 = find_col(df1, ["valor total", "total", "valor neto", "neto", "valor"])
                if not col_total1:
                    col_total1 = "Valor"
                
                val_unit_safe = pd.to_numeric(df1[col_val_unit1], errors='coerce').fillna(0)
                df1[col_total1] = val_unit_safe * qtys
                
                for tmp in ['_temp_code', '_temp_name', '__Valor_Encontrado__']:
                    if tmp in df1.columns:
                        df1.drop(columns=[tmp], inplace=True)
                
                df = df1
            
                # --- LIMPIEZA Y GUARDADO SEGURO DEL CONSOLIDADO ---
                try:
                    # Limpieza de archivos antiguos
                    consolidados_viejos = glob.glob("archivo_consolidado*.xlsx")
                    for f_old in consolidados_viejos:
                        try:
                            os.remove(f_old)
                        except:
                            pass

                    if 'Valor_Unitario_Ref' in df.columns:
                        df = df.drop(columns=['Valor_Unitario_Ref'])
                    
                    df_export = df.copy()
                    df_export = df_export.loc[:, ~df_export.columns.duplicated()]
                    df_export.columns = df_export.columns.astype(str).str.strip()

                    for col in df_export.columns:
                        col_lower = col.lower()
                        if "fecha" in col_lower or "inicio" in col_lower or "fin" in col_lower or pd.api.types.is_datetime64_any_dtype(df_export[col]):
                            try:
                                # Convertir a datetime real
                                df_export[col] = pd.to_datetime(df_export[col], errors='coerce', dayfirst=True, format='mixed')
                                # NO convertir a string (strftime) para mantener funcionalidad de filtro de fecha en Excel
                            except:
                                pass
                        elif "profesional" in col_lower:
                            try:
                                df_export[col] = df_export[col].astype(str).str.replace(r'^\d+\s*[-]?\s*', '', regex=True).str.strip()
                            except:
                                pass
                        elif col == col_val_unit1 or col == col_total1:
                             df_export[col] = pd.to_numeric(df_export[col], errors='coerce').fillna(0)
                        elif df_export[col].dtype == 'object':
                            df_export[col] = df_export[col].fillna("").astype(str)
                            df_export[col] = df_export[col].apply(lambda x: re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', x))
                            df_export[col] = df_export[col].apply(lambda x: "'" + x if str(x).startswith("=") else x)
                            df_export[col] = df_export[col].str.slice(0, 32700)

                    output_path = "archivo_consolidado.xlsx"
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            output_path = f"archivo_consolidado_{int(datetime.now().timestamp())}.xlsx"

                    try:
                        # Usar xlsxwriter con formato de fecha explícito
                        with pd.ExcelWriter(output_path, engine='xlsxwriter', engine_kwargs={'options': {'nan_inf_to_errors': True}}, date_format='dd/mm/yyyy', datetime_format='dd/mm/yyyy') as writer:
                             df_export.to_excel(writer, index=False)
                    except:
                        df_export.to_excel(output_path, index=False, engine='openpyxl')
                    
                    st.success("✅ Archivo consolidado generado exitosamente.")
                    st.session_state['consolidado_path'] = output_path

                except Exception as e:
                    st.error(f"Error generando consolidado: {e}")
            
            else:
                st.warning("No se encontraron columnas para consolidar. Concatenando...")
                df = pd.concat([df1, df2], ignore_index=True)

        elif not df1.empty:
            df = df1
        elif not df2.empty:
            df = df2
        else:
            return st.session_state.get('df') or cargar_excel()

        df.columns = df.columns.astype(str).str.strip()
        
        st.session_state.df = df
        guardar_excel(df)
        guardar_fecha_actualizacion()
        
        return df
    except Exception as e:
        st.error(f"Error leyendo archivos: {e}")
        return st.session_state.get('df')

# ===================== HELPERS DROPDOWNS =====================
def get_dropdown_options(df, keywords):
    if df is None:
        return []
    col = next((c for c in df.columns if any(k in str(c).lower() for k in keywords)), None)
    if col:
        serie = df[col]
        if isinstance(serie, pd.DataFrame): serie = serie.iloc[:, 0]
        serie = serie.astype(str).str.strip()
        mapa = {v.lower(): v for v in serie.dropna()}
        return sorted(mapa.values())
    return []

# ===================== FILTROS =====================
def filtrar_datos(df, nombre_prof, fecha_inicio, fecha_fin, procedimiento, ciudad):
    aviso = ""
    if df is None:
        return pd.DataFrame(), aviso

    df_filtrado = df.copy()

    # Filtro Profesional
    col_profesional = next((c for c in df.columns if "profesional" in str(c).lower()), None)
    if nombre_prof and col_profesional:
        df_filtrado = df_filtrado[df_filtrado[col_profesional].astype(str).str.strip().str.lower() == str(nombre_prof).strip().lower()]

    # Filtro Procedimiento
    col_procedimiento = next((c for c in df.columns if "nombre procedimiento" in str(c).lower()), None)
    if procedimiento and col_procedimiento:
        df_filtrado = df_filtrado[df_filtrado[col_procedimiento].astype(str).str.strip().str.lower() == str(procedimiento).strip().lower()]
    
    # Filtro Ciudad (Prioridad: Ciudad/Municipio > Sede)
    col_ciudad = next((c for c in df.columns if "ciudad" in str(c).lower() or "municipio" in str(c).lower()), None)
    if not col_ciudad:
        col_ciudad = next((c for c in df.columns if "sede" in str(c).lower()), None)
        
    if ciudad and col_ciudad:
        df_filtrado = df_filtrado[df_filtrado[col_ciudad].astype(str).str.strip().str.lower() == str(ciudad).strip().lower()]

    # Filtro Fechas
    col_fecha = next((c for c in df.columns if "fecha" in str(c).lower()), None)
    if col_fecha:
        try:
            fechas_series = pd.to_datetime(df_filtrado[col_fecha], errors="coerce", dayfirst=True).dt.date
            mask = pd.Series(True, index=df_filtrado.index)
            if fecha_inicio:
                mask = mask & (fechas_series >= fecha_inicio)
            if fecha_fin:
                mask = mask & (fechas_series <= fecha_fin)
            df_filtrado = df_filtrado[mask]
        except Exception as e:
            aviso += f"⚠️ Error con fechas: {e}"
    else:
        aviso += "⚠️ No hay columna de fecha."
        
    return df_filtrado, aviso

def calcular_totales(df):
    col_valor = next((c for c in df.columns if str(c).strip().lower() == "valor"), None)
    if not col_valor:
         col_valor = next((c for c in df.columns if "valor" in str(c).lower()), None)
    
    if col_valor:
        serie = pd.to_numeric(df[col_valor], errors="coerce")
        total_valor = serie[serie > 0].sum(skipna=True)
        return total_valor
    return 0

# ===================== UI LOGIN =====================
if 'usuario' not in st.session_state:
    st.session_state.usuario = None

def login():
    st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        background-color: #005f73;
        color: white;
        border-radius: 10px;
    }
    .stTextInput>div>div>input {
        border-radius: 10px;
    }
    .login-box {
        background-color: #e0fbfc;
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class='login-box'>
        <h1 style='color:#005f73; margin:0;'>🏥 IPS GOLEMAN</h1>
        <p style='color:#555;'>Sistema de Facturación y Análisis</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.form("login_form"):
            user = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Acceder")
            
            if submit:
                if user in ["admin", "cristian"] and password == "123":
                    st.session_state.usuario = user
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")

def logout():
    st.session_state.usuario = None
    st.rerun()

def eliminar_consolidado():
    try:
        if os.path.exists("archivo_consolidado.xlsx"):
            os.remove("archivo_consolidado.xlsx")
        if os.path.exists("base_guardada.xlsx"):
            os.remove("base_guardada.xlsx")
        st.session_state.df = None
        st.session_state.df_ciudades = None
        st.success("✅ Consolidado eliminado y datos reiniciados.")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Error al eliminar: {e}")

# ===================== APP PRINCIPAL =====================
def main_app():
    # --- HEADER ---
    col1, col2, col3, col4 = st.columns([2, 4, 2, 2])
    with col1:
        st.markdown(f"""
        <div style='background-color:#e0fbfc; padding:10px; border-radius:10px; text-align:center;'>
            <span style='color:#005f73; font-weight:bold;'>� {st.session_state.usuario}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        pass # Botón eliminado del header
                 
    with col4:
        if st.button("🔒 Cerrar sesión", type="secondary"):
            logout()
    
    st.markdown("---")
    
    # --- INFO ESTADO ---
    fecha_update = cargar_fecha_actualizacion()
    st.info(f"🕒 Última actualización: {fecha_update}")
    
    if os.path.exists("archivo_consolidado.xlsx"):
        with open("archivo_consolidado.xlsx", "rb") as f:
            st.download_button("📥 Descargar Consolidado", f, file_name="archivo_consolidado.xlsx")

    # --- CARGAR DATOS EN MEMORIA ---
    if 'df' not in st.session_state or st.session_state.df is None:
        st.session_state.df = cargar_excel()
        # Intentar cargar consolidado si existe para el filtro de ciudad
        if os.path.exists("archivo_consolidado.xlsx"):
             try:
                 st.session_state.df_ciudades = pd.read_excel("archivo_consolidado.xlsx", engine="openpyxl")
             except:
                 st.session_state.df_ciudades = st.session_state.df
        else:
             st.session_state.df_ciudades = st.session_state.df

    df = st.session_state.df
    
    if df is None:
        st.warning("No hay datos cargados. Por favor suba un archivo.")
        return

    # --- FILTROS ---
    st.sidebar.header("🔍 Filtros de Análisis")
    
    # Opciones
    profs = get_dropdown_options(df, ["profesional"])
    procs = get_dropdown_options(df, ["nombre procedimiento"])
    # Para ciudades, usar consolidado si está disponible
    ciudades_df = st.session_state.get('df_ciudades', df)
    # Prioridad: Ciudad/Municipio > Sede
    ciuds = get_dropdown_options(ciudades_df, ["ciudad", "municipio"])
    if not ciuds:
         ciuds = get_dropdown_options(ciudades_df, ["sede"])
    
    sel_prof = st.sidebar.selectbox("Profesional", ["Todos"] + profs)
    sel_proc = st.sidebar.selectbox("Procedimiento", ["Todos"] + procs)
    sel_ciud = st.sidebar.selectbox("Ciudad / Municipio", ["Todos"] + ciuds)
    
    col_d1, col_d2 = st.sidebar.columns(2)
    with col_d1:
        f_ini = st.date_input("Fecha Inicio", value=None)
    with col_d2:
        f_fin = st.date_input("Fecha Fin", value=None)
    
    # Aplicar filtros
    prof_arg = sel_prof if sel_prof != "Todos" else None
    proc_arg = sel_proc if sel_proc != "Todos" else None
    ciud_arg = sel_ciud if sel_ciud != "Todos" else None
    
    df_filtrado, aviso = filtrar_datos(df, prof_arg, f_ini, f_fin, proc_arg, ciud_arg)
    
    if aviso:
        st.sidebar.warning(aviso)
    
    # --- TABS ---
    # Definir tabs dinámicamente según rol
    tabs_names = ["📊 ANÁLISIS", "💰 TOTAL", "🏆 DASHBOARD", "✅ CUMPLIMIENTO", "🔄 CRUCES DE DATOS"]
    if st.session_state.usuario == "admin":
        tabs_names.insert(0, "📂 CONSOLIDACIÓN")
    
    tabs = st.tabs(tabs_names)
    
    # Asignar variables a tabs
    if st.session_state.usuario == "admin":
        tab_consol = tabs[0]
        tab1 = tabs[1]
        tab2 = tabs[2]
        tab3 = tabs[3]
        tab4 = tabs[4]
        tab_cruces = tabs[5]
    else:
        tab1 = tabs[0]
        tab2 = tabs[1]
        tab3 = tabs[2]
        tab4 = tabs[3]
        tab_cruces = tabs[4]
    
    # TAB CONSOLIDACIÓN (Solo Admin)
    if st.session_state.usuario == "admin":
        with tab_consol:
            st.subheader("Gestión de Archivos")
            st.markdown("Cargue los archivos para consolidar o actualizar la base de datos.")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                archivo1 = st.file_uploader("Archivo 1 (Base Principal)", type=["xlsx"])
            with col_f2:
                archivo2 = st.file_uploader("Archivo 2 (Información Complementaria)", type=["xlsx"])
            
            col_act1, col_act2 = st.columns(2)
            with col_act1:
                if archivo1:
                    if st.button("🔄 Procesar y Consolidar Archivos", type="primary"):
                        leer_excel(archivo1, archivo2)
                        st.rerun()
            with col_act2:
                if os.path.exists("archivo_consolidado.xlsx"):
                     if st.button("🗑️ Eliminar Consolidado Totalmente", type="secondary"):
                         eliminar_consolidado()
            
    # TAB 1: ANÁLISIS
    with tab1:
        st.subheader("Resumen Profesional por Procedimiento")
        
        if not df_filtrado.empty:
            col_profesional = next((c for c in df_filtrado.columns if "profesional" in str(c).lower()), None)
            col_procedimiento = next((c for c in df_filtrado.columns if "nombre procedimiento" in str(c).lower()), None)
            col_valor = next((c for c in df_filtrado.columns if "valor" in str(c).lower()), None)

            if col_profesional and col_procedimiento and col_valor:
                try:
                    temp = df_filtrado.copy()
                    temp["_valor"] = pd.to_numeric(temp[col_valor], errors='coerce').fillna(0)
                    
                    # Agrupar por Profesional y Procedimiento
                    agrupado = temp.groupby([col_profesional, col_procedimiento]).agg(
                        Total_Servicios=(col_procedimiento, 'count'),
                        Valor_Total=('_valor', 'sum')
                    ).reset_index()
                    
                    # Ordenar y formatear
                    agrupado = agrupado.sort_values([col_profesional, "Total_Servicios"], ascending=[True, False])
                    
                    # Estilización de dataframe
                    st.dataframe(
                        agrupado, 
                        column_config={
                            col_profesional: "Profesional",
                            col_procedimiento: "Procedimiento",
                            "Total_Servicios": st.column_config.ProgressColumn(
                                "Total Servicios",
                                help="Cantidad de servicios realizados",
                                format="%d",
                                min_value=0,
                                max_value=int(agrupado["Total_Servicios"].max()),
                            ),
                            "Valor_Total": st.column_config.NumberColumn(
                                "Valor Total",
                                help="Valor monetario total",
                                format="$ %d"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Error generando resumen profesional: {e}")
            else:
                st.warning("No se encontraron columnas de profesional, procedimiento o valor para generar el resumen.")

        st.markdown("---")
        st.subheader("Resumen por Paciente")
        
        # Lógica de agrupación (simplificada de appy.py)
        if not df_filtrado.empty:
            col_paciente = next((c for c in df_filtrado.columns if "paciente" in str(c).lower()), None)
            col_procedimiento = next((c for c in df_filtrado.columns if "nombre procedimiento" in str(c).lower()), None)
            col_valor = next((c for c in df_filtrado.columns if "valor" in str(c).lower()), None)
            
            if col_paciente and col_procedimiento:
                try:
                    temp = df_filtrado.copy()
                    temp["_valor"] = pd.to_numeric(temp[col_valor], errors='coerce').fillna(0) if col_valor else 0
                    
                    pivot = temp.pivot_table(
                        index=col_paciente,
                        columns=col_procedimiento,
                        aggfunc='size',
                        fill_value=0
                    )
                    pivot["TOTAL SERVICIOS"] = pivot.sum(axis=1)
                    pivot["VALOR TOTAL"] = temp.groupby(col_paciente)["_valor"].sum()
                    
                    # Formato
                    pivot["VALOR TOTAL"] = pivot["VALOR TOTAL"].apply(formato_pesos)
                    pivot = pivot.sort_values("TOTAL SERVICIOS", ascending=False)
                    
                    st.dataframe(pivot, use_container_width=True)
                except Exception as e:
                    st.error(f"Error agrupando: {e}")
                    st.dataframe(df_filtrado)
            else:
                st.dataframe(df_filtrado)
        else:
            st.info("Sin resultados para mostrar")

    # TAB 2: TOTAL
    with tab2:
        total_val = calcular_totales(df_filtrado)
        st.markdown(f"<div style='text-align:center; background:#e0fbfc; padding:20px; border-radius:15px;'><h1 style='color:#005f73;'>💰 Total: {formato_pesos(total_val)}</h1></div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Tabla por procedimiento en lugar de gráfico
        col_proc = next((c for c in df_filtrado.columns if "nombre procedimiento" in str(c).lower()), None)
        col_val = next((c for c in df_filtrado.columns if "valor" in str(c).lower()), None)
        
        if col_proc and col_val and not df_filtrado.empty:
            temp = df_filtrado.copy()
            temp["_val"] = pd.to_numeric(temp[col_val], errors='coerce').fillna(0)
            agrupado = temp.groupby(col_proc)["_val"].sum().reset_index().sort_values("_val", ascending=False)
            
            st.subheader("Detalle por Procedimiento")
            
            # Formatear valor para visualización
            agrupado["Valor Formateado"] = agrupado["_val"].apply(formato_pesos)
            
            st.dataframe(
                agrupado[[col_proc, "Valor Formateado"]], # Mostrar columnas limpias
                column_config={
                    col_proc: "Nombre del Procedimiento",
                    "Valor Formateado": st.column_config.TextColumn(
                        "Valor Total",
                        help="Valor total facturado por este procedimiento"
                    )
                },
                hide_index=True,
                use_container_width=True,
                height=500
            )

    # TAB 3: DASHBOARD
    with tab3:
        st.subheader("Dashboard Profesional")
        meta_dash = st.number_input("Meta General", value=cargar_meta("meta_dashboard.txt"))
        if st.button("Guardar Meta Dashboard"):
            guardar_meta("meta_dashboard.txt", meta_dash)
            
        col_prof = next((c for c in df_filtrado.columns if "profesional" in str(c).lower()), None)
        if col_prof and not df_filtrado.empty:
            counts = df_filtrado[col_prof].value_counts().reset_index()
            counts.columns = ["Profesional", "Servicios"]
            
            # Calcular porcentajes
            if meta_dash > 0:
                counts["Porcentaje"] = (counts["Servicios"] / meta_dash * 100)
            else:
                counts["Porcentaje"] = 0
            
            # Dividir pantalla
            col_dash_left, col_dash_right = st.columns(2)
            
            with col_dash_left:
                st.markdown("### 📋 Rendimiento General")
                st.dataframe(
                    counts,
                    column_config={
                        "Profesional": "Profesional",
                        "Servicios": st.column_config.NumberColumn(
                            "Servicios",
                            help="Total de servicios realizados",
                            format="%d 🏥"
                        ),
                        "Porcentaje": st.column_config.ProgressColumn(
                            "Cumplimiento Meta",
                            help="Porcentaje respecto a la meta",
                            format="%.1f%%",
                            min_value=0,
                            max_value=max(100, int(counts["Porcentaje"].max()) if not counts.empty else 100),
                        )
                    },
                    hide_index=True,
                    use_container_width=True,
                    height=600
                )
                
            with col_dash_right:
                st.markdown("### 🏆 Top 10 Profesionales")
                top_10 = counts.head(10).sort_values("Servicios", ascending=True) # Sort for chart
                fig_top = px.bar(
                    top_10, 
                    x="Servicios", 
                    y="Profesional", 
                    orientation='h',
                    text="Porcentaje",
                    title="Top 10 Rendimiento",
                    color="Profesional", # Color distinto para cada uno
                )
                fig_top.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_top.update_layout(height=600, showlegend=False)
                st.plotly_chart(fig_top, use_container_width=True)
    
    # TAB 4: CUMPLIMIENTO
    with tab4:
        st.subheader("Cumplimiento de Meta")
        meta_cump = st.number_input("Meta Cumplimiento", value=cargar_meta("meta_cumplimiento.txt"))
        if st.button("Guardar Meta Cumplimiento"):
            guardar_meta("meta_cumplimiento.txt", meta_cump)
            
        total_actual = calcular_totales(df_filtrado)
        pct = (total_actual / meta_cump * 100) if meta_cump > 0 else 0
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.metric("Total Actual", formato_pesos(total_actual))
            st.metric("Meta", formato_pesos(meta_cump))
            st.metric("Porcentaje", f"{pct:.2f}%")
        
        with col_c2:
            fig_pie = px.pie(names=["Logrado", "Faltante"], values=[min(total_actual, meta_cump), max(meta_cump - total_actual, 0)], hole=0.5)
            st.plotly_chart(fig_pie)

    # TAB 5: CRUCES DE DATOS
    with tab_cruces:
        st.subheader("🔄 Cruce de Información")
        st.markdown("Suba dos archivos para comparar registros y encontrar coincidencias o diferencias.")
        
        col_cruce1, col_cruce2 = st.columns(2)
        with col_cruce1:
            file_cruce1 = st.file_uploader("Archivo A (Base)", type=["xlsx"], key="cruce1")
        with col_cruce2:
            file_cruce2 = st.file_uploader("Archivo B (Comparar)", type=["xlsx"], key="cruce2")
            
        if file_cruce1 and file_cruce2:
            if st.button("🔍 Comparar Archivos", type="primary"):
                try:
                    df_c1 = pd.read_excel(file_cruce1, engine="openpyxl")
                    df_c2 = pd.read_excel(file_cruce2, engine="openpyxl")
                    
                    st.success(f"Archivos cargados: {df_c1.shape[0]} filas en A, {df_c2.shape[0]} filas en B")
                    
                    # Identificar columnas comunes
                    common_cols = list(set(df_c1.columns) & set(df_c2.columns))
                    
                    if common_cols:
                        col_key = st.selectbox("Seleccione columna clave para cruzar (ej: Cédula, Código)", common_cols)
                        
                        # Realizar cruce
                        df_c1[col_key] = df_c1[col_key].astype(str).str.strip()
                        df_c2[col_key] = df_c2[col_key].astype(str).str.strip()
                        
                        # Coincidencias
                        coincidencias = pd.merge(df_c1, df_c2, on=col_key, how='inner', suffixes=('_A', '_B'))
                        
                        # Diferencias (En A pero no en B)
                        no_en_b = df_c1[~df_c1[col_key].isin(df_c2[col_key])]
                        
                        # Diferencias (En B pero no en A)
                        no_en_a = df_c2[~df_c2[col_key].isin(df_c1[col_key])]
                        
                        st.divider()
                        
                        col_res1, col_res2, col_res3 = st.columns(3)
                        with col_res1:
                            st.metric("Coincidencias", len(coincidencias))
                        with col_res2:
                            st.metric("Solo en Archivo A", len(no_en_b))
                        with col_res3:
                            st.metric("Solo en Archivo B", len(no_en_a))
                            
                        tab_res1, tab_res2, tab_res3 = st.tabs(["✅ Coincidencias", "⚠️ Solo en A", "⚠️ Solo en B"])
                        
                        with tab_res1:
                            st.dataframe(coincidencias, use_container_width=True)
                        with tab_res2:
                            st.dataframe(no_en_b, use_container_width=True)
                        with tab_res3:
                            st.dataframe(no_en_a, use_container_width=True)
                            
                    else:
                        st.warning("No se encontraron columnas con el mismo nombre para cruzar automáticamente.")
                        
                except Exception as e:
                    st.error(f"Error en el cruce: {e}")

# ===================== MAIN EXECUTION =====================
if st.session_state.usuario:
    main_app()
else:
    login()
