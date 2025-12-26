import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components
import os
import json
import re
from datetime import datetime
import glob
import time
import io
import gc

# ===================== CONFIGURACIÓN DE PÁGINA =====================
st.set_page_config(
    page_title="IPS GOLEMAN APP",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===================== ESTILOS CSS =====================
def load_css():
    st.markdown("""
    <style>
    /* Estilo General de Botones */
    div.stButton > button {
        background-color: #005f73;
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: bold;
    }
    div.stButton > button:hover {
        background-color: #0a9396;
        color: white;
        border-color: #0a9396;
    }
    div.stButton > button:active {
        background-color: #94d2bd;
        color: #005f73;
    }
    
    /* Inputs */
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #94d2bd;
    }
    
    /* Login Box */
    .login-box {
        background-color: #e0fbfc;
        padding: 40px;
        border-radius: 20px;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 20px;
        border: 2px solid #94d2bd;
    }
    
    /* Header User Box */
    .user-box {
        background-color: #e0fbfc;
        padding: 10px 20px;
        border-radius: 12px;
        text-align: center;
        border: 1px solid #94d2bd;
        color: #005f73;
        font-weight: bold;
        display: inline-flex;
        align-items: center;
        gap: 10px;
    }
    
    /* Hover Row Effect (Solo afecta tablas HTML standard, no st.dataframe canvas) */
    tr:hover {
        background-color: #d0f0c0 !important;
        cursor: pointer;
    }
    
    /* Background Color Main App */
    .stApp {
        background-color: #f0f8ff; /* Azul claro muy suave */
    }
    
    /* Sidebar Background */
    section[data-testid="stSidebar"] {
        background-color: #e0fbfc; /* Color suave para el sidebar */
        border-right: 2px solid #94d2bd;
    }
    </style>
    """, unsafe_allow_html=True)

def load_login_css():
    st.markdown("""
    <style>
    div.stButton > button {
        width: 100%;
        padding: 10px;
        font-size: 16px;
    }
    </style>
    """, unsafe_allow_html=True)

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
    # Buscar el archivo consolidado más reciente
    archivos = glob.glob("archivo_consolidado*.xlsx")
    if archivos:
        # Ordenar por fecha de modificación (el más reciente al final)
        archivo_reciente = max(archivos, key=os.path.getmtime)
        timestamp = os.path.getmtime(archivo_reciente)
        return datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %I:%M:%S %p")
        
    elif os.path.exists(ARCHIVO_FECHA):
        with open(ARCHIVO_FECHA, "r") as f:
            return f.read().strip()
    return "Sin actualizaciones"

def generar_excel_filtros(df, nombre_prof, fecha_inicio, fecha_fin, procedimiento, ciudad):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # HOJA 1: DATOS FILTRADOS (RAW)
        df.to_excel(writer, sheet_name='Datos Filtrados', index=False)
        
        # HOJA 2: RESUMEN PROFESIONAL
        if not df.empty:
            col_profesional = next((c for c in df.columns if "profesional" in str(c).lower()), None)
            col_procedimiento = next((c for c in df.columns if "nombre procedimiento" in str(c).lower()), None)
            col_valor = next((c for c in df.columns if "valor" in str(c).lower()), None)
            
            if col_profesional and col_procedimiento and col_valor:
                try:
                    temp = df.copy()
                    temp["_valor"] = pd.to_numeric(temp[col_valor], errors='coerce').fillna(0)
                    agrupado = temp.groupby([col_profesional, col_procedimiento]).agg(
                        Total_Servicios=(col_procedimiento, 'count'),
                        Valor_Total=('_valor', 'sum')
                    ).reset_index()
                    agrupado.to_excel(writer, sheet_name='Resumen Profesional', index=False)
                except:
                    pass

        # HOJA 3: RESUMEN PACIENTE
        if not df.empty:
            col_paciente = next((c for c in df.columns if "paciente" in str(c).lower()), None)
            if col_paciente and col_procedimiento:
                try:
                    temp = df.copy()
                    pivot = temp.pivot_table(index=col_paciente, columns=col_procedimiento, aggfunc='size', fill_value=0)
                    pivot.to_excel(writer, sheet_name='Resumen Paciente')
                except:
                    pass
        
        # HOJA 4: TOTALES
        if not df.empty and col_procedimiento and col_valor:
             try:
                temp = df.copy()
                temp["_val"] = pd.to_numeric(temp[col_valor], errors='coerce').fillna(0)
                agrupado_total = temp.groupby(col_procedimiento)["_val"].sum().reset_index()
                agrupado_total.to_excel(writer, sheet_name='Totales', index=False)
             except:
                pass

        # HOJA 5: DASHBOARD
        if not df.empty and col_profesional:
             try:
                counts = df[col_profesional].value_counts().reset_index()
                counts.columns = ["Profesional", "Servicios"]
                counts.to_excel(writer, sheet_name='Dashboard', index=False)
             except:
                pass
                
    output.seek(0)
    return output

def guardar_excel(df, nombre_archivo="base_guardada.xlsx"):
    df.to_excel(nombre_archivo, index=False)

def cargar_excel(nombre_archivo="base_guardada.xlsx"):
    if os.path.exists(nombre_archivo):
        try:
            df = pd.read_excel(nombre_archivo)
            return clean_df_for_st(df)
        except:
            return None
    return None

# ===================== LÓGICA DE NEGOCIO =====================
def clean_df_for_st(df):
    """Limpia el DataFrame para evitar errores de PyArrow en Streamlit"""
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    # 1. Eliminar columnas Unnamed
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    # 2. Homogeneizar tipos de datos para evitar Mixed Types
    for col in df.columns:
        # Si es tipo objeto, forzar a string y limpiar caracteres raros
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).replace('nan', '')
            # Eliminar caracteres nulos o de control que rompen Arrow
            df[col] = df[col].apply(lambda x: re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', x) if isinstance(x, str) else x)
    
    return df

def find_col(df, candidates):
    for col in df.columns:
        if any(cand.lower() in str(col).lower() for cand in candidates):
            return col
    return None

def leer_excel(file_obj1, file_obj2=None):
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

        # Limpieza preliminar
        col_prof1 = find_col(df1, ["profesional", "nombre profesional"])
        if col_prof1:
             df1[col_prof1] = df1[col_prof1].astype(str).str.replace(r'^\d+\s*[-]?\s*', '', regex=True).str.strip()

        # Consolidación
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
            
                # Guardado seguro
                try:
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
                                df_export[col] = pd.to_datetime(df_export[col], errors='coerce', dayfirst=True, format='mixed')
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
                        with pd.ExcelWriter(output_path, engine='xlsxwriter', engine_kwargs={'options': {'nan_inf_to_errors': True}}, date_format='dd/mm/yyyy', datetime_format='dd/mm/yyyy') as writer:
                             df_export.to_excel(writer, index=False)
                    except:
                        df_export.to_excel(output_path, index=False, engine='openpyxl')
                    
                    st.success("✅ Archivo consolidado generado exitosamente.")
                    st.session_state['consolidado_path'] = output_path
                    
                    # Forzar actualización de timestamp para que otros usuarios recarguen
                    if os.path.exists(output_path):
                        # "Touch" el archivo para asegurar cambio de fecha si fue muy rápido
                        os.utime(output_path, None)

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
        # Limpiar columnas Unnamed que causan error Arrow
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        
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
    
    # Filtro Ciudad
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
# REMOVED GLOBAL SESSION STATE INIT to avoid top-level execution risks
# if 'usuario' not in st.session_state:
#     st.session_state.usuario = None

def login():
    load_css()
    load_login_css()
    
    st.markdown("""
    <div class='login-box'>
        <h1 style='color:#005f73; margin:0;'>🏥 IPS GOLEMAN</h1>
        <p style='color:#555; font-size:1.1em;'>Sistema de Facturación y Análisis</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.form("login_form"):
            st.markdown("<h3 style='text-align:center; color:#005f73;'>Iniciar Sesión</h3>", unsafe_allow_html=True)
            user = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            st.markdown("<br>", unsafe_allow_html=True)
            submit = st.form_submit_button("Acceder")
            
            if submit:
                if user in ["Admin", "Cristian", "Marta", "Alejandra"] and password == "123":
                    st.session_state.usuario = user
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")

def set_user_offline(username):
    """Marca a un usuario como desconectado inmediatamente"""
    try:
        status_data = {}
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, "r") as f:
                    status_data = json.load(f)
            except:
                pass
        
        # Establecer tiempo en 0 para desconexión inmediata
        status_data[username] = 0
        
        with open(STATUS_FILE, "w") as f:
            json.dump(status_data, f)
    except:
        pass

def logout():
    if st.session_state.usuario:
        set_user_offline(st.session_state.usuario)
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

# ===================== GESTIÓN DE USUARIOS Y ESTADO =====================
USERS_LIST = ["admin", "cristian"]
STATUS_FILE = "users_status.json"

def update_user_status(username):
    try:
        status_data = {}
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, "r") as f:
                    status_data = json.load(f)
            except:
                pass
        
        status_data[username] = time.time()
        
        with open(STATUS_FILE, "w") as f:
            json.dump(status_data, f)
    except:
        pass

def get_users_status():
    status_data = {}
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                status_data = json.load(f)
        except:
            pass
    
    current_time = time.time()
    results = []
    
    for user in USERS_LIST:
        last_seen = status_data.get(user, 0)
        # Si se ha visto en los últimos 5 minutos (300 segundos), está online
        is_online = (current_time - last_seen) < 300 
        results.append({"Usuario": user, "Estado": "En Línea" if is_online else "Desconectado", "Online": is_online})
        
    return pd.DataFrame(results)

@st.fragment(run_every=5)
def render_user_status_panel():
    df_status = get_users_status()
    
    # Mostrar como tarjetas o tabla estilizada
    col_u1, col_u2 = st.columns(2)
    
    for index, row in df_status.iterrows():
        with col_u1 if index % 2 == 0 else col_u2:
            color_status = "#2ec4b6" if row["Online"] else "#e63946" # Verde o Rojo
            bg_color = "#e0fbfc" if row["Online"] else "#ffe5d9"
            
            st.markdown(f"""
            <div style='padding:15px; background:{bg_color}; border-radius:10px; border:1px solid {color_status}; margin-bottom:10px; display:flex; align_items:center; justify-content:space-between;'>
                <div style='display:flex; align_items:center;'>
                    <span style='font-size:24px; margin-right:10px;'>👤</span>
                    <h3 style='margin:0; color:#005f73;'>{row['Usuario']}</h3>
                </div>
                <div style='display:flex; align_items:center;'>
                    <span style='height: 15px; width: 15px; background-color: {color_status}; border-radius: 50%; display: inline-block; margin-right:5px;'></span>
                    <b style='color:{color_status};'>{row['Estado']}</b>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ===================== APP PRINCIPAL =====================
def main_app():
    load_css()
    
    # Actualizar estado de usuario activo
    if st.session_state.usuario:
        update_user_status(st.session_state.usuario)
    
    # --- MENSAJE BIENVENIDA (JS 10s) ---
    if 'welcome_shown' not in st.session_state:
        st.session_state.welcome_shown = True
        components.html(f"""
        <script>
            var msg = document.createElement('div');
            msg.innerHTML = "👋 BIENVENIDO {st.session_state.usuario}";
            msg.style.position = 'fixed';
            msg.style.top = '20px';
            msg.style.left = '50%';
            msg.style.transform = 'translateX(-50%)';
            msg.style.backgroundColor = '#005f73';
            msg.style.color = 'white';
            msg.style.padding = '15px 30px';
            msg.style.borderRadius = '10px';
            msg.style.zIndex = '9999';
            msg.style.fontSize = '20px';
            msg.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
            msg.style.textAlign = 'center';
            document.body.appendChild(msg);
            setTimeout(function() {{
                msg.style.transition = 'opacity 1s';
                msg.style.opacity = '0';
                setTimeout(function() {{ document.body.removeChild(msg); }}, 1000);
            }}, 10000);
        </script>
        """, height=0)
    
    # --- HEADER ---
    col1, col2, col3, col4 = st.columns([2, 4, 2, 2])
    with col1:
        st.markdown(f"""
        <div class='user-box'>
            <span style='height: 12px; width: 12px; background-color: #2ec4b6; border-radius: 50%; display: inline-block;'></span>
            👤 {st.session_state.usuario}
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        pass 
                 
    with col4:
        # Botón de cerrar sesión con estilo
        if st.button("🔒 Cerrar sesión"):
            logout()
    
    st.markdown("---")
    
    # --- CARGAR DATOS EN MEMORIA ---
    if 'df' not in st.session_state or st.session_state.df is None:
        try:
            st.session_state.df = cargar_excel()
            if os.path.exists("archivo_consolidado.xlsx"):
                 try:
                     df_c = pd.read_excel("archivo_consolidado.xlsx", engine="openpyxl")
                     st.session_state.df_ciudades = clean_df_for_st(df_c)
                 except:
                     st.session_state.df_ciudades = st.session_state.df
            else:
                 st.session_state.df_ciudades = st.session_state.df
        except Exception as e:
            st.error(f"Error cargando datos iniciales: {e}")
            st.session_state.df = None
            st.session_state.df_ciudades = None

    df = st.session_state.df

    # --- FILTROS (Mover arriba para tener df_filtrado y botones disponibles) ---
    # Nota: Los filtros se renderizan en Sidebar, pero la lógica de filtrado se ejecuta aquí
    # para poder mostrar los botones de descarga ARRIBA.
    
    st.sidebar.header("🔍 Filtros de Análisis")
    
    profs = get_dropdown_options(df, ["profesional"])
    procs = get_dropdown_options(df, ["nombre procedimiento"])
    ciudades_df = st.session_state.get('df_ciudades', df)
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
    
    prof_arg = sel_prof if sel_prof != "Todos" else None
    proc_arg = sel_proc if sel_proc != "Todos" else None
    ciud_arg = sel_ciud if sel_ciud != "Todos" else None
    
    df_filtrado, aviso = filtrar_datos(df, prof_arg, f_ini, f_fin, proc_arg, ciud_arg)
    
    if aviso:
        st.sidebar.warning(aviso)

    # --- INFO ESTADO Y DESCARGAS (SUPERIOR) ---
    fecha_update = cargar_fecha_actualizacion()
    
    # Layout de botones e info
    col_info, col_btn1, col_btn2 = st.columns([2, 1, 1])
    with col_info:
        st.info(f"🕒 {fecha_update} | 📦 Consolidado")
    with col_btn1:
        if os.path.exists("archivo_consolidado.xlsx"):
            with open("archivo_consolidado.xlsx", "rb") as f:
                st.download_button("📥 Descargar Consolidado", f, file_name="archivo_consolidado.xlsx", use_container_width=True)
    with col_btn2:
        if not df_filtrado.empty:
            excel_data = generar_excel_filtros(df_filtrado, prof_arg, f_ini, f_fin, proc_arg, ciud_arg)
            st.download_button("📊 Descargar Filtros", excel_data, file_name="reporte_filtrado.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    # --- VALIDACIÓN DE DATOS ---
    if df is None:
        st.warning("No hay datos cargados. Por favor cargue archivos en la pestaña correspondiente (Admin).")
        # Mostrar tabs básicos si es admin para permitir carga
        if st.session_state.usuario != "admin":
            return

    # --- TABS DEFINITION ---
    tabs_names = ["📊 ANÁLISIS", "💰 TOTAL", "🏆 DASHBOARD", "✅ CUMPLIMIENTO", "🔄 CRUCES DE DATOS"]
    if st.session_state.usuario == "admin":
        tabs_names.insert(0, "📂 CONSOLIDACIÓN")
        tabs_names.insert(0, "👥 USUARIOS")
    
    tabs = st.tabs(tabs_names)
    
    # Asignar variables a tabs
    if st.session_state.usuario == "admin":
        tab_users = tabs[0]
        tab_consol = tabs[1]
        tab1 = tabs[2]
        tab2 = tabs[3]
        tab3 = tabs[4]
        tab4 = tabs[5]
        tab_cruces = tabs[6]
    else:
        tab1 = tabs[0]
        tab2 = tabs[1]
        tab3 = tabs[2]
        tab4 = tabs[3]
        tab_cruces = tabs[4]
    
    # TAB USUARIOS (Solo Admin)
    if st.session_state.usuario == "admin":
        with tab_users:
            st.subheader("👥 Gestión de Usuarios y Estado")
            # Panel auto-actualizable cada 5 segundos
            render_user_status_panel()

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
                    if st.button("🔄 Procesar y Consolidar Archivos"):
                        leer_excel(archivo1, archivo2)
                        st.rerun()
            with col_act2:
                if os.path.exists("archivo_consolidado.xlsx") or os.path.exists("base_guardada.xlsx"):
                     if st.button("🗑️ Eliminar Consolidado Totalmente"):
                         eliminar_consolidado()
    
    # TAB CRUCES DE DATOS
    with tab_cruces:
        st.subheader("🔄 Cruce de Información")
        st.markdown("Suba dos archivos para comparar registros y encontrar coincidencias o diferencias.")
        
        col_cruce1, col_cruce2 = st.columns(2)
        with col_cruce1:
            file_cruce1 = st.file_uploader("Archivo A (Base)", type=["xlsx"], key="cruce1")
        with col_cruce2:
            file_cruce2 = st.file_uploader("Archivo B (Comparar)", type=["xlsx"], key="cruce2")
            
        # Gestión de Estado de Archivos Cargados
        if 'cruce_df1' not in st.session_state:
            st.session_state.cruce_df1 = None
        if 'cruce_df2' not in st.session_state:
            st.session_state.cruce_df2 = None
            
        if file_cruce1 and file_cruce2:
            # Botón para Cargar (solo si no están cargados o si cambian archivos)
            # Nota: Streamlit reinicia file_uploader si se recarga la página, 
            # pero aquí queremos persistencia durante la sesión de análisis.
            
            if st.button("📥 Cargar Archivos para Análisis"):
                try:
                    with st.spinner("Leyendo archivos grandes... esto puede tardar unos momentos..."):
                        gc.collect()
                        
                        # Leer y guardar en Session State
                        st.session_state.cruce_df1 = pd.read_excel(file_cruce1, engine="openpyxl", dtype=str)
                        st.session_state.cruce_df2 = pd.read_excel(file_cruce2, engine="openpyxl", dtype=str)
                        
                        st.session_state.cruce_df1 = clean_df_for_st(st.session_state.cruce_df1)
                        st.session_state.cruce_df2 = clean_df_for_st(st.session_state.cruce_df2)
                        
                        st.success(f"Archivos cargados en memoria: {st.session_state.cruce_df1.shape[0]} filas en A, {st.session_state.cruce_df2.shape[0]} filas en B")
                        
                except Exception as e:
                    st.error(f"Error cargando archivos: {e}")
            
            # Si ya hay datos en memoria, mostrar opciones de cruce
            if st.session_state.cruce_df1 is not None and st.session_state.cruce_df2 is not None:
                df_c1 = st.session_state.cruce_df1
                df_c2 = st.session_state.cruce_df2
                
                common_cols = list(set(df_c1.columns) & set(df_c2.columns))
                
                if common_cols:
                    col_key = st.selectbox("Seleccione columna clave para cruzar (ej: Cédula, Código)", common_cols)
                    
                    # Botón para EJECUTAR el cruce (Usuario pidió explícitamente este botón)
                    if st.button("🚀 Iniciar Cruce de Datos"):
                        try:
                            # Optimización: Convertir a string vectorizado y strip
                            df_c1[col_key] = df_c1[col_key].astype(str).str.strip()
                            df_c2[col_key] = df_c2[col_key].astype(str).str.strip()
                            
                            with st.spinner("Realizando cruce de datos..."):
                                progress_bar = st.progress(0)
                                
                                # Paso 1: Lectura y Preparación (Simulado 30%)
                                progress_bar.progress(30, text="Analizando estructuras...")
                                
                                # Usar indicator=True para saber origen de manera más eficiente
                                # ESTRATEGIA OPTIMIZADA DE MEMORIA: NO USAR OUTER MERGE GIGANTE
                                
                                # 1. Identificar claves
                                keys_a = set(df_c1[col_key])
                                keys_b = set(df_c2[col_key])
                                
                                # 2. Filtrar "Solo en A" (No Repetidos) SIN hacer merge masivo
                                # Esto es mucho más ligero que un outer join
                                no_en_b = df_c1[~df_c1[col_key].isin(keys_b)].copy()
                                
                                # 3. Filtrar "Solo en B" (si se necesita métrica)
                                no_en_a = df_c2[~df_c2[col_key].isin(keys_a)].copy()
                                
                                # 4. Coincidencias (Repetidos) - Inner Merge
                                # Solo unimos lo que coincide
                                coincidencias = pd.merge(df_c1, df_c2, on=col_key, how='inner', suffixes=('_A', '_B'))
                                
                                progress_bar.progress(80, text="Generando reportes...")
                                
                                # Generar Buffer Excel para descarga
                                buffer_cruce = io.BytesIO()
                                with pd.ExcelWriter(buffer_cruce, engine='xlsxwriter') as writer:
                                    coincidencias.to_excel(writer, sheet_name='REPETIDOS', index=False)
                                    no_en_b.to_excel(writer, sheet_name='NO REPETIDOS', index=False)
                                buffer_cruce.seek(0)
                                
                                # Guardar resultados en Session State para que no desaparezcan
                                st.session_state.cruce_resultado = {
                                    'coincidencias': coincidencias,
                                    'no_en_b': no_en_b,
                                    'no_en_a': no_en_a,
                                    'buffer': buffer_cruce
                                }
                                
                                progress_bar.progress(100, text="¡Análisis Completado!")
                                time.sleep(0.5)
                                progress_bar.empty()
                                st.rerun()

                        except MemoryError:
                            st.error("⚠️ Error de Memoria: Los archivos son demasiado grandes.")
                        except Exception as e:
                            st.error(f"Error en el cruce: {e}")

                else:
                    st.warning("No se encontraron columnas con el mismo nombre para cruzar automáticamente.")
            
            # Mostrar Resultados si existen en Session State
            if 'cruce_resultado' in st.session_state:
                res = st.session_state.cruce_resultado
                
                st.divider()
                st.success("✅ Resultados del último cruce:")
                
                col_res1, col_res2, col_res3 = st.columns(3)
                with col_res1:
                    st.metric("Coincidencias", len(res['coincidencias']))
                with col_res2:
                    st.metric("Solo en Archivo A", len(res['no_en_b']))
                with col_res3:
                    st.metric("Solo en Archivo B", len(res['no_en_a']))
                    
                # Botón de Descarga
                st.download_button(
                    label="📥 Descargar Resultado del Cruce (Excel)",
                    data=res['buffer'],
                    file_name=f"cruce_datos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                tab_res1, tab_res2, tab_res3 = st.tabs(["✅ Coincidencias", "⚠️ Solo en A", "⚠️ Solo en B"])
                
                with tab_res1:
                    st.dataframe(res['coincidencias'])
                with tab_res2:
                    st.dataframe(res['no_en_b'])
                with tab_res3:
                    st.dataframe(res['no_en_a'])


    # Si no hay datos y no es admin, no mostrar resto
    if df is None:
        return

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
                    
                    agrupado = temp.groupby([col_profesional, col_procedimiento]).agg(
                        Total_Servicios=(col_procedimiento, 'count'),
                        Valor_Total=('_valor', 'sum')
                    ).reset_index()
                    
                    agrupado = agrupado.sort_values([col_profesional, "Total_Servicios"], ascending=[True, False])
                    
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
        st.subheader("Resumen Detallado por Paciente")
        
        if not df_filtrado.empty:
            col_paciente = next((c for c in df_filtrado.columns if "paciente" in str(c).lower()), None)
            col_procedimiento = next((c for c in df_filtrado.columns if "nombre procedimiento" in str(c).lower()), None)
            col_valor = next((c for c in df_filtrado.columns if "valor" in str(c).lower()), None)
            
            if col_paciente and col_procedimiento:
                try:
                    temp = df_filtrado.copy()
                    temp["_valor"] = pd.to_numeric(temp[col_valor], errors='coerce').fillna(0) if col_valor else 0
                    
                    # Agrupación por Paciente - Método Compatible
                    g = temp.groupby(col_paciente)
                    resumen_paciente = pd.DataFrame({
                        "Total_Procedimientos": g[col_procedimiento].count(),
                        "Tipos_Procedimientos": g[col_procedimiento].nunique(),
                        "Valor_Total": g['_valor'].sum()
                    }).reset_index()
                    
                    resumen_paciente = resumen_paciente.sort_values("Total_Procedimientos", ascending=False)
                    
                    # Formateo visual
                    st.dataframe(
                        resumen_paciente,
                        column_config={
                            col_paciente: "Nombre del Paciente",
                            "Total_Procedimientos": st.column_config.NumberColumn(
                                "Total Procedimientos",
                                help="Cantidad total de procedimientos realizados a este paciente",
                                format="%d"
                            ),
                            "Tipos_Procedimientos": st.column_config.NumberColumn(
                                "Tipos Únicos",
                                help="Cantidad de tipos de procedimientos diferentes",
                                format="%d"
                            ),
                            "Valor_Total": st.column_config.NumberColumn(
                                "Valor Facturado",
                                format="$ %d",
                            )
                        },
                        hide_index=True,
                        use_container_width=True,
                        height=500
                    )
                    
                    with st.expander("Ver Detalle Matricial (Tabla Cruzada)"):
                        pivot = temp.pivot_table(
                            index=col_paciente,
                            columns=col_procedimiento,
                            aggfunc='size',
                            fill_value=0
                        )
                        pivot = clean_df_for_st(pivot)
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
        st.markdown(f"<div style='text-align:center; background:#e0fbfc; padding:20px; border-radius:15px; border: 1px solid #94d2bd;'><h1 style='color:#005f73;'>💰 Total: {formato_pesos(total_val)}</h1></div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_proc = next((c for c in df_filtrado.columns if "nombre procedimiento" in str(c).lower()), None)
        col_val = next((c for c in df_filtrado.columns if "valor" in str(c).lower()), None)
        
        if col_proc and col_val and not df_filtrado.empty:
            temp = df_filtrado.copy()
            temp["_val"] = pd.to_numeric(temp[col_val], errors='coerce').fillna(0)
            
            # Agrupación más detallada
            agrupado = temp.groupby(col_proc).agg(
                Cantidad=(col_proc, 'count'),
                Valor_Num=('_val', 'sum')
            ).reset_index()
            
            agrupado = agrupado.sort_values("Valor_Num", ascending=False)
            
            # Calcular participación
            total_global = agrupado["Valor_Num"].sum()
            agrupado["Participacion"] = (agrupado["Valor_Num"] / total_global * 100) if total_global > 0 else 0
            
            # Formatear Valor (String con puntos)
            agrupado["Valor Total"] = agrupado["Valor_Num"].apply(formato_pesos)
            
            agrupado = clean_df_for_st(agrupado)
            
            st.subheader("Detalle por Procedimiento")
            
            st.dataframe(
                agrupado,
                column_config={
                    col_proc: "Procedimiento",
                    "Cantidad": st.column_config.NumberColumn(
                        "Frecuencia",
                        help="Cantidad de veces realizado",
                        format="%d"
                    ),
                    "Valor Total": st.column_config.TextColumn(
                        "Valor Total",
                        help="Valor facturado (COP)"
                    ),
                    "Participacion": st.column_config.ProgressColumn(
                        "Participación %",
                        format="%.1f%%",
                        min_value=0,
                        max_value=100,
                        help="Peso sobre el total facturado"
                    ),
                    "Valor_Num": None 
                },
                hide_index=True,
                use_container_width=True,
                height=600
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
            
            if meta_dash > 0:
                counts["Porcentaje"] = (counts["Servicios"] / meta_dash * 100)
            else:
                counts["Porcentaje"] = 0
            
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
                            format="%d"
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
                top_10 = counts.head(10).sort_values("Servicios", ascending=False)
                
                st.dataframe(
                    top_10,
                    column_config={
                        "Profesional": "Profesional",
                        "Servicios": st.column_config.NumberColumn(
                            "Servicios",
                            help="Total de servicios realizados",
                            format="%d"
                        ),
                        "Porcentaje": st.column_config.ProgressColumn(
                            "Cumplimiento",
                            help="Porcentaje respecto a la meta",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100
                        )
                    },
                    hide_index=True,
                    use_container_width=True,
                    height=600
                )
    
    # TAB 4: CUMPLIMIENTO
    with tab4:
        st.subheader("Cumplimiento de Meta")
        col_m1, col_m2 = st.columns([1, 2])
        with col_m1:
            meta_cump = st.number_input("Establecer Meta Mensual ($)", value=cargar_meta("meta_cumplimiento.txt"))
            if st.button("💾 Guardar Meta"):
                guardar_meta("meta_cumplimiento.txt", meta_cump)
        
        total_actual = calcular_totales(df_filtrado)
        pct = (total_actual / meta_cump * 100) if meta_cump > 0 else 0
        faltante = max(meta_cump - total_actual, 0)
        
        st.divider()
        
        # Métricas Principales
        col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
        with col_kpi1:
            st.markdown(f"<div style='padding:15px; background:#e0fbfc; border-radius:10px; border:1px solid #94d2bd; text-align:center;'><h3>💰 Recaudo Actual</h3><h2>{formato_pesos(total_actual)}</h2></div>", unsafe_allow_html=True)
        with col_kpi2:
            st.markdown(f"<div style='padding:15px; background:#ffddd2; border-radius:10px; border:1px solid #e29578; text-align:center;'><h3>📉 Faltante Meta</h3><h2>{formato_pesos(faltante)}</h2></div>", unsafe_allow_html=True)
        with col_kpi3:
             color_pct = "green" if pct >= 100 else "orange" if pct >= 80 else "red"
             st.markdown(f"<div style='padding:15px; background:#edf6f9; border-radius:10px; border:1px solid #83c5be; text-align:center;'><h3>🎯 Porcentaje</h3><h2 style='color:{color_pct};'>{pct:.1f}%</h2></div>", unsafe_allow_html=True)

        st.divider()

        # Gráficos Avanzados
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.markdown("### 📊 Medidor de Progreso")
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = total_actual,
                domain = {'x': [0, 1], 'y': [0, 1]},
                delta = {'reference': meta_cump, 'position': "top", 'valueformat': "$,.0f"},
                gauge = {
                    'axis': {'range': [0, meta_cump*1.2 if meta_cump > 0 else total_actual*1.2]},
                    'bar': {'color': "#005f73"},
                    'steps': [
                        {'range': [0, meta_cump*0.5], 'color': "#e0fbfc"},
                        {'range': [meta_cump*0.5, meta_cump*0.9], 'color': "#83c5be"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': meta_cump
                    }
                }
            ))
            fig_gauge.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        with col_g2:
            st.markdown("### 🥧 Distribución del Cumplimiento")
            fig_pie = px.pie(
                names=["Recaudado", "Faltante"], 
                values=[total_actual, faltante], 
                hole=0.6,
                color_discrete_sequence=["#005f73", "#ffddd2"]
            )
            fig_pie.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)

# ===================== MAIN EXECUTION =====================
if __name__ == "__main__":
    # Asegurar inicialización de estado
    if 'usuario' not in st.session_state:
        st.session_state.usuario = None

    try:
        if st.session_state.usuario:
            main_app()
        else:
            login()
    except Exception as e:
        st.error(f"Ocurrió un error crítico: {e}")
        # Intentar mostrar detalles si es posible
        import traceback
        st.code(traceback.format_exc())

