# Basket Analyzer v2.0 - Quantitative Tool for Equity-Linked Structured Notes

**Modelo Cuantitativo Avanzado para Análisis de Notas Estructuradas (Worst-of Basket)**  
**Desarrollado por Diego Montano**  
**Buy Side Investment Analyst (Market Strategy) — Capital Driver Asset Management**

---

## Descripción del Proyecto

Este repositorio contiene el **Basket Analyzer v2.0**, una herramienta cuantitativa completa con **interfaz gráfica (GUI)** que desarrollé en Python durante mi rol actual como Buy Side Investment Analyst en **Capital Driver Asset Management** (Lima, Perú — junio 2025 a la fecha).

El script analiza **notas estructuradas equity-linked tipo Worst-of Basket** (con barreras de cupón, barrera de capital, autocall, leveraged put, etc.). Utiliza simulación Monte Carlo correlacionada (GBM multivariado), calcula probabilidades de autocall, ruptura de capital, cupones esperados, drawdown máximo y realiza stress testing automático. Además, incorpora análisis histórico, scatter μ vs σ, y probabilidad de alcanzar targets de analistas (1 año).

Es 100 % interactivo: solo ingresa los tickers y parámetros y obtienes un **dashboard profesional completo** en tiempo real. Ideal para selección de estructurados, pitch books y optimización de cartera en asset management.

---

## Características Principales

- **Interfaz GUI completa** con Tkinter (4 pestañas interactivas)
- Descarga automática de datos históricos (yfinance)
- Simulación Monte Carlo correlacionada (GBM multivariado con 500.000 paths)
- Cálculo automático de:
  - Probabilidad de Autocall
  - Probabilidad de Break Capital al vencimiento
  - Proporción esperada de cupones
  - Redención esperada
  - Drawdown máximo promedio
- Stress testing automático (–5% μ y +50% σ)
- Análisis histórico con barrera inferior worst-of (95% confianza)
- Scatter plot μ vs σ y detección de activo más volátil / más estable
- Probabilidad de alcanzar target price de analistas (1 año) con gráfico de barras
- Totalmente parametrizable (barreras, duración, yield, leveraged put, autocall, etc.)

---

## Tecnologías y Habilidades Aplicadas

- **Python** (core del modelo y GUI)
- `yfinance`, `pandas`, `numpy`, `scipy` (estadística y distribuciones)
- `matplotlib` + `FigureCanvasTkAgg` (visualizaciones en vivo)
- `tkinter` + `ttk` (interfaz gráfica profesional)
- `requests` + `BeautifulSoup` (scraping inteligente de targets de analistas)
- Herramientas mencionadas en mi CV: **Python**, **Análisis Cuantitativo de Derivados**, **Modelos Estocásticos**, **Pricing de Opciones**, **Escenarios de Estrés**, **Finanzas Cuantitativas**

---

## Instalación y Uso

### 1. Clonar el repositorio
```bash
git clone https://github.com/diegomontano/basket-analyzer.git
cd basket-analyzer
```

### 2. Instalar dependencias
```bash
pip install yfinance pandas numpy scipy matplotlib beautifulsoup4 requests
```

### 3. Ejecutar el dashboard
```bash
python baket-analyzer-v2.0.py
```

> La aplicación se abre automáticamente con un formulario de inputs. Ingresa tickers separados por coma (ej: `AAPL, MSFT, NVDA`) y ajusta los parámetros según la nota estructurada deseada.

---

## Ejemplo de Salida

Al ejecutar con tickers de un basket típico (ej: tecnología global) se genera en tiempo real:

- **Pestaña Historical**: Gráfico de performance normalizada + portfolio worst-of + barrera histórica
- **Pestaña Simulations & Risk**: Resultados probabilísticos + stress test + 10 simulaciones GBM del worst-of
- **Pestaña Sensitivity**: Activo más volátil vs más estable + scatter μ vs σ
- **Pestaña Upside/Downside**: Gráfico de barras con % target price (1 año) y probabilidad de cumplimiento

Todos los cálculos se actualizan en vivo y son exportables para investment memos o reuniones con clientes institucionales / HNWI.

---

## Estructura del Proyecto

```
basket-analyzer/
├── baket-analyzer-v2.0.py      # Script principal con GUI completa
├── README.md                   # Este archivo
└── requirements.txt            # (opcional)
```

---

## Contexto Profesional

Este proyecto es una pieza clave de mi contribución actual en **Capital Driver Asset Management**, donde veo la estrategia de inversiones en mercados globales y soluciones de cartera multiactivos (cross-assets). La herramienta ha sido utilizada internamente para:

- Seleccionar y optimizar notas estructuradas equity-linked
- Incrementar el rendimiento ajustado al riesgo de la cartera (>6% en cupones)
- Apoyar la elaboración de pitch books y propuestas de financiamiento estructurado
- Realizar análisis de sensibilidad y stress testing para clientes HNWI e institucionales

---

## Autor

**Diego Montano**  
Economista | Inversiones y Mercados Globales  
- LinkedIn: [linkedin.com/in/diego-montano](https://www.linkedin.com/in/diego-montano/)  
- Email: montano.d@pucp.edu.pe  
- Teléfono: (+51) 998 720 030  

---

## Licencia

Este proyecto es de uso privado/académico y profesional. Si deseas utilizarlo en producción o adaptarlo para tu fondo o equipo de estructurados, por favor contáctame.

---

**¡Gracias por visitar el repositorio!**  
Si trabajas en asset management, derivados o notas estructuradas, no dudes en dar una estrella y contactarme. Estoy abierto a colaboraciones en proyectos de finanzas cuantitativas y optimización de portafolios cross-assets.

*Diego Montano — Marzo 2026*
```
