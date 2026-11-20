"""src/agentes/agente_reportes.py
Agente 2: Generador de Reportes Operativos
"""
import os
import pandas as pd


class AgenteReportes:
    def ejecutar(self, rutas_archivos: str) -> str:
        archivos = [r.strip().strip('"').strip("'") for r in rutas_archivos.split(",") if r.strip()]
        if not archivos:
            return "Error: No se proporcionaron rutas de archivos válidas."
        
        dfs = []
        for archivo in archivos:
            if not os.path.exists(archivo):
                return f"Error: archivo '{archivo}' no encontrado"
            try:
                df = pd.read_excel(archivo)
                df["_origen_archivo"] = os.path.basename(archivo)
                dfs.append(df)
                print(f"Procesado: {archivo} ({len(df)} filas, {len(df.columns)} columnas)")
            except Exception as e:
                return f"Error leyendo el archivo {archivo}: {e}"
        
        df_consolidado = pd.concat(dfs, ignore_index=True)
        
        # 1. Resumen de columnas numéricas (totales, promedios, min, max)
        cols_numericas = df_consolidado.select_dtypes(include=["number"]).columns.tolist()
        resumen_lineas = []
        df_resumen_num = pd.DataFrame()
        
        if cols_numericas:
            df_resumen_num = df_consolidado[cols_numericas].describe().T[["count", "mean", "std", "min", "50%", "max"]]
            df_resumen_num.rename(columns={"count": "Registros", "mean": "Promedio", "std": "Desv.Std", "min": "Mínimo", "50%": "Mediana", "max": "Máximo"}, inplace=True)
            for col in cols_numericas:
                suma_val = df_consolidado[col].sum()
                prom_val = df_consolidado[col].mean()
                resumen_lineas.append(f"     * Columna '{col}': Total = {suma_val:,.2f} | Promedio = {prom_val:,.2f}")
        
        # 2. Resumen de columnas categóricas (valores más comunes)
        cols_categoricas = [c for c in df_consolidado.select_dtypes(include=["object"]).columns if c != "_origen_archivo"]
        lineas_cat = []
        for col in cols_categoricas[:4]:  # Top columnas para la vista previa
            top_val = df_consolidado[col].value_counts().head(1)
            if not top_val.empty:
                val_nombre = top_val.index[0]
                val_freq = top_val.iloc[0]
                lineas_cat.append(f"     * '{col}': Valor más frecuente '{val_nombre}' ({val_freq} veces)")

        # 3. Guardar Excel con dos hojas: 'Datos_Consolidados' y 'Resumen_Estadistico'
        os.makedirs("salidas", exist_ok=True)
        ruta_salida = "salidas/reporte_consolidado.xlsx"
        
        with pd.ExcelWriter(ruta_salida, engine="openpyxl") as writer:
            df_consolidado.to_excel(writer, sheet_name="Datos_Consolidados", index=False)
            if not df_resumen_num.empty:
                df_resumen_num.to_excel(writer, sheet_name="Resumen_Estadistico")
        
        # Construir reporte textual
        reporte_texto = (
            f" Reporte consolidado generado exitosamente en: {ruta_salida}\n"
            f"  • Total de archivos consolidados: {len(archivos)}\n"
            f"  • Total de filas combinadas: {len(df_consolidado):,}\n"
            f"  • Total de columnas: {len(df_consolidado.columns)}\n"
        )
        if resumen_lineas:
            reporte_texto += "   • Resumen Métricas Numéricas:\n" + "\n".join(resumen_lineas[:5]) + "\n"
        if lineas_cat:
            reporte_texto += "   • Datos Categóricos Clave:\n" + "\n".join(lineas_cat)
            
        return reporte_texto
