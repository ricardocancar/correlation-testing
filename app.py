import streamlit as st
import yfinance as yf
from fredapi import Fred
import pandas as pd
import datetime

def analizar_macro_mensual(start_hist, start_recent, end_date, fred_api_key):
    # Descargar Oro y agrupar por mes
    oro = yf.download('GC=F', start=start_hist, end=end_date)['Close']
    oro_mensual = oro.resample('ME').last()
    
    # Descargar M2 (Mensual) y Deuda Pública Total (Trimestral) de la FRED
    # M2SL: M2 Money Supply
    # GFDEBTN: Federal Debt: Total Public Debt (Trimestral)
    tickers_fred = {
        'M2SL': 'M2', 
        'GFDEBTN': 'Deuda_Publica', 
        'GDP': 'PIB_USA',
        'CPIAUCSL': 'IPC',
        'FEDFUNDS': 'Tasa_Fed'
    }
    
    # Usar FRED API para descargar datos
    fred = Fred(api_key=fred_api_key)
    macro_data = {}
    for ticker, name in tickers_fred.items():
        macro_data[name] = fred.get_series(ticker, start_date=start_hist, end_date=end_date)
    
    macro = pd.DataFrame(macro_data)
    macro.index = pd.to_datetime(macro.index)
    
    # Agrupar los datos macro a fin de mes y aplicar Forward Fill
    # Esto rellena los meses vacíos de la Deuda Pública con el último dato trimestral publicado
    macro_mensual = macro.resample('ME').ffill()
    
    # Unir todo en un solo DataFrame
    df_macro = oro_mensual.join(macro_mensual, how='outer').rename(columns={'GC=F': "Oro"})
    df_macro.ffill(inplace=True) # Rellenar cualquier hueco hasta la publicación más reciente
    df_macro.dropna(inplace=True)
    
    # Calcular Tasa Real (Tasa Fed - Inflación YoY)
    # El IPC es un índice, su cambio porcentual a 12 meses nos da la inflación anualizada
    df_macro['Tasa_Real'] = df_macro['Tasa_Fed'] - (df_macro['IPC'].pct_change(12) * 100)
    df_macro.dropna(inplace=True) # Eliminar los primeros 12 meses usados para el cálculo YoY
    
    # Calcular Correlaciones
    corr_macro_hist = df_macro.pct_change().dropna().corr()['Oro'].drop('Oro')
    df_macro_reciente = df_macro[df_macro.index >= start_recent]
    corr_macro_reciente = df_macro_reciente.pct_change().corr()['Oro'].drop('Oro')
    
    # Crear tabla estructurada para Streamlit
    tabla_macro = pd.DataFrame({
        'Valor Actual': df_macro.iloc[-1].drop('Oro'),
        'Corr. Histórica': corr_macro_hist,
        'Corr. Reciente': corr_macro_reciente
    })
    return tabla_macro, df_macro.iloc[-1]['Oro']

def analizar_mercado_frecuencias(start_hist, end_date):
    tickers_mercado = ['GC=F', 'DX-Y.NYB', '^TNX']
    nombres = {'GC=F': 'Oro', 'DX-Y.NYB': 'DXY', '^TNX': 'US10Y'}

    # A. Análisis Diario (Histórico 2005 - 2025)
    df_diario = yf.download(tickers_mercado, start=start_hist, end=end_date)['Close']
    df_diario.rename(columns=nombres, inplace=True)
    corr_diaria = df_diario.pct_change().corr()['Oro'].drop('Oro')

    # B. Análisis Intradía (Última hora, frecuencia de 1 minuto)
    # yfinance permite bajar datos de 1 minuto del último día cotizado ('1d')
    df_minuto = yf.download(tickers_mercado, period='1d', interval='1m')['Close']
    df_minuto.rename(columns=nombres, inplace=True)
    
    # Filtrar solo los últimos 60 minutos (la última hora cotizada)
    df_ultima_hora = df_minuto.tail(60)
    corr_ultima_hora = df_ultima_hora.pct_change().corr()['Oro'].drop('Oro')

    # Crear tabla estructurada para Streamlit
    tabla_mercado = pd.DataFrame({
        'Valor Actual': df_diario.iloc[-1].drop('Oro'),
        'Corr. Diaria (2005+)': corr_diaria,
        'Corr. Intradía (60m)': corr_ultima_hora
    })
    return tabla_mercado

if __name__ == "__main__":
    st.set_page_config(page_title="Monitor de Correlaciones Oro", layout="wide")
    st.title("📊 Monitor de Fundamentos y Correlaciones del Oro")

    # Definir fechas
    fecha_fin = datetime.datetime.today()
    fecha_inicio_hist = datetime.datetime(2005, 1, 1)
    fecha_inicio_reciente = datetime.datetime(2022, 1, 1) 

    # Obtener API key de FRED desde secrets
    fred_api_key = st.secrets["FRED_API_KEY"]
    
    with st.spinner('Descargando y procesando datos...'):
        # Ejecutar cálculos
        tabla_macro, precio_oro = analizar_macro_mensual(fecha_inicio_hist, fecha_inicio_reciente, fecha_fin, fred_api_key)
        tabla_mercado = analizar_mercado_frecuencias(fecha_inicio_hist, fecha_fin)

    # 1. Valor del Oro aparte
    st.metric(label="Precio Actual Oro (GC=F)", value=f"${precio_oro:,.2f}")

    # 2. Tablas de Indicadores
    st.subheader("📈 Indicadores Macroeconómicos y Correlación")
    st.dataframe(tabla_macro.style.format(precision=3), use_container_width=True)

    st.subheader("⚡ Indicadores de Mercado (Frecuencias Rápidas)")
    st.dataframe(tabla_mercado.style.format(precision=3), use_container_width=True)