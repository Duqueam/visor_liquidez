import json
import time
import threading
import webbrowser
from threading import Timer
from collections import deque
import requests
import pandas as pd
import websocket
from dash import Dash, dcc, html, Input, Output

# ==============================================================================
# 1. MEMORIA EN TIEMPO REAL (WEBSOCKET PARA LIQUIDACIONES Y BOMBAS DE VOLUMEN)
# ==============================================================================
PARES = ('HYPEUSDT', 'BTCUSDT', 'ETHUSDT', 'SOLUSDT')

UMBRAL_BOMBA_USDT = {
    'HYPEUSDT': 15000,
    'BTCUSDT': 250000,
    'ETHUSDT': 100000,
    'SOLUSDT': 50000
}

UMBRAL_LIQ_USDT = {
    'HYPEUSDT': 1500,
    'BTCUSDT': 10000,
    'ETHUSDT': 5000,
    'SOLUSDT': 3000
}

liquidaciones_vivo = {p: deque(maxlen=150) for p in PARES}
bombas_vivo = {p: deque(maxlen=100) for p in PARES}
buffer_trades = {p: {'sec': 0, 'buy_usdt': 0.0, 'sell_usdt': 0.0, 'last_price': 0.0} for p in PARES}
ws_iniciado = False
libro_vivo = {p: {'bids': {}, 'asks': {}} for p in PARES}
velas_cache = {}

def iniciar_websocket_binance():
    global ws_iniciado
    if ws_iniciado:
        return
    ws_iniciado = True

    streams = ["!forceOrder@arr"] + [f"{p.lower()}@aggTrade" for p in PARES]
    url = "wss://://binance.com" + "/".join(streams)

    def on_message(ws, message):
        try:
            payload = json.loads(message)
            stream = payload.get('stream', '')
            data = payload.get('data', {})

            if stream == '!forceOrder@arr':
                orden = data.get('o', {})
                simbolo = orden.get('s', '')
                if simbolo in PARES:
                    precio = float(orden.get('ap') or orden.get('p') or 0)
                    qty = float(orden.get('q') or 0)
                    usdt = precio * qty
                    if usdt >= UMBRAL_LIQ_USDT.get(simbolo, 1500):
                        lado = orden.get('S')
                        ts_ms = int(orden.get('T', time.time() * 1000))
                        liquidaciones_vivo[simbolo].append({
                            'ts_ms': ts_ms,
                            'price': precio,
                            'usdt': usdt,
                            'es_short_liq': (lado == 'BUY')
                        })

            elif '@aggTrade' in stream:
                simbolo = data.get('s', '')
                if simbolo in PARES:
                    precio = float(data.get('p', 0))
                    qty = float(data.get('q', 0))
                    usdt = precio * qty
                    es_venta_agresiva = data.get('m', False)
                    ts_ms = int(data.get('T', time.time() * 1000))
                    ventana_3s = ts_ms // 3000

                    buf = buffer_trades[simbolo]
                    if buf['sec'] != ventana_3s:
                        umbral = UMBRAL_BOMBA_USDT.get(simbolo, 25000)
                        if buf['buy_usdt'] >= umbral:
                            bombas_vivo[simbolo].append({
                                'ts_ms': buf['sec'] * 3000,
                                'price': buf['last_price'],
                                'usdt': buf['buy_usdt'],
                                'tipo': 'COMPRA'
                            })
                        if buf['sell_usdt'] >= umbral:
                            bombas_vivo[simbolo].append({
                                'ts_ms': buf['sec'] * 3000,
                                'price': buf['last_price'],
                                'usdt': buf['sell_usdt'],
                                'tipo': 'VENTA'
                            })
                        buf['sec'] = ventana_3s
                        buf['buy_usdt'] = 0.0
                        buf['sell_usdt'] = 0.0

                    buf['last_price'] = precio
                    if es_venta_agresiva:
                        buf['sell_usdt'] += usdt
                    else:
                        buf['buy_usdt'] += usdt
        except Exception as e:
            print(f"Error WS Binance: {e}")

    def correr():
        while True:
            try:
                ws = websocket.WebSocketApp(url, on_message=on_message)
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                print(f"Reconectando WS por error: {e}")
            time.sleep(2)

    threading.Thread(target=correr, daemon=True).start()


# ==============================================================================
# 2. INTERFAZ DASH Y DISEÑO VISUAL
# ==============================================================================
app = Dash(
    __name__,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"}
    ]
)
server = app.server

app.title = "Visor Cripto Pro - Mapa de Calor + Order Flow + Bombas"

estilo_tarjeta = dict(
    backgroundColor='#131722',
    border='1px solid #242936',
    borderRadius='6px',
    padding='10px 14px',
    flex='1',
    minWidth='150px'
)

barra_superior = html.Div(
    style=dict(display='flex', justifyContent='space-between', alignItems='center', marginBottom='8px', backgroundColor='#131722', padding='8px 16px', borderRadius='6px', border='1px solid #242936', flexWrap='wrap', gap='8px'),
    children=[
        html.Div(
            style=dict(display='flex', alignItems='center', gap='10px'),
            children=[
                html.Span("Mapa de calor + Order Flow + Bombas", style=dict(fontWeight='bold', fontSize='15px', color='#ffffff')),
                html.Span("Binance Perp", style=dict(backgroundColor='#242936', color='#848e9c', padding='2px 8px', borderRadius='4px', fontSize='11px', fontWeight='bold'))
            ]
        ),
        html.Div(
            style=dict(display='flex', gap='10px', alignItems='center', flexWrap='wrap'),
            children=[
                dcc.Dropdown(
                    id='selector-moneda',
                    options=[
                        dict(label='HYPEUSDT Perp', value='HYPEUSDT'),
                        dict(label='BTCUSDT Perp', value='BTCUSDT'),
                        dict(label='ETHUSDT Perp', value='ETHUSDT'),
                        dict(label='SOLUSDT Perp', value='SOLUSDT')
                    ],
                    value='HYPEUSDT',
                    clearable=False,
                    style=dict(width='155px', color='#000', fontSize='12px', fontWeight='bold')
                ),
                dcc.Dropdown(
                    id='selector-tf',
                    options=[
                        dict(label='1m', value='1m'),
                        dict(label='5m', value='5m'),
                        dict(label='15m', value='15m'),
                        dict(label='1H', value='1h'),
                        dict(label='4H', value='4h'),
                        dict(label='1D', value='1d')
                    ],
                    value='15m',
                    clearable=False,
                    style=dict(width='80px', color='#000', fontSize='12px', fontWeight='bold')
                ),
                dcc.Dropdown(
                    id='selector-rango',
                    options=[
                        dict(label='Prof: ±1%', value=0.01),
                        dict(label='Prof: ±3%', value=0.03),
                        dict(label='Prof: ±5%', value=0.05),
                        dict(label='Prof: ±10%', value=0.10),
                        dict(label='Prof: Libro Completo', value=1.00)
                    ],
                    value=1.00,
                    clearable=False,
                    style=dict(width='170px', color='#000', fontSize='12px', fontWeight='bold')
                ),
                dcc.Dropdown(
                    id='selector-capa',
                    options=[
                        dict(label='Capa: Ambos', value='AMBOS'),
                        dict(label='Capa: Liq 10x-100x', value='LIQ'),
                        dict(label='Capa: Muros Libro', value='MUROS')
                    ],
                    value='AMBOS',
                    clearable=False,
                    style=dict(width='155px', color='#000', fontSize='12px', fontWeight='bold')
                ),
                html.Span("● WS En vivo", style=dict(color='#00e676', fontSize='12px', fontWeight='bold'))
            ]
        )
    ]
)
panel_tarjetas = html.Div(
    id='panel-6-tarjetas',
    style=dict(display='flex', gap='8px', marginBottom='8px', flexWrap='wrap'),
    children=[
        html.Div(style=estilo_tarjeta, children=[
            html.Div("Último precio · Binance Perp", style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t1-principal', style=dict(fontSize='20px', fontWeight='bold', color='#ffffff')),
            html.Div("Compra -- · Venta --", id='t1-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        ]),
        html.Div(style=estilo_tarjeta, children=[
            html.Div("Profundidad de compra", id='t2-titulo', style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t2-principal', style=dict(fontSize='20px', fontWeight='bold', color='#00e676')),
            html.Div("-- monedas", id='t2-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        ]),
        html.Div(style=estilo_tarjeta, children=[
            html.Div("Profundidad de venta", id='t3-titulo', style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t3-principal', style=dict(fontSize='20px', fontWeight='bold', color='#ff5252')),
            html.Div("-- monedas", id='t3-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        ]),
        html.Div(style=estilo_tarjeta, children=[
            html.Div("Desequilibrio libro", id='t4-titulo', style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t4-principal', style=dict(fontSize='20px', fontWeight='bold', color='#00e676')),
            html.Div("Presión en rango activo", id='t4-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        ]),
        html.Div(style=estilo_tarjeta, children=[
            html.Div("Mayor muro de compra", style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t5-principal', style=dict(fontSize='20px', fontWeight='bold', color='#00e676')),
            html.Div("-- del precio", id='t5-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        ]),
        html.Div(style=estilo_tarjeta, children=[
            html.Div("Mayor muro de venta", style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t6-principal', style=dict(fontSize='20px', fontWeight='bold', color='#ff5252')),
            html.Div("-- del precio", id='t6-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        ])
    ]
)

barra_leyenda = html.Div(
    style=dict(display='flex', justifyContent='space-between', alignItems='center', marginBottom='6px', backgroundColor='#131722', padding='5px 14px', borderRadius='4px', fontSize='11px', border='1px solid #1e222d', flexWrap='wrap', gap='8px'),
    children=[
        html.Div([
            html.Span("Calor libro: ", style=dict(fontWeight='bold', color='#d1d4dc', marginRight='6px')),
            html.Span("■ Bajo ", style=dict(color='#9575cd', marginRight='6px')),
            html.Span("■ Alto ", style=dict(color='#00e676', marginRight='6px')),
            html.Span("■ Máximo", style=dict(color='#ffeb3b'))
        ]),
        html.Div([
            html.Span("Liquidaciones WS: ", style=dict(fontWeight='bold', color='#d1d4dc', marginRight='6px')),
            html.Span("◆ Liq Shorts ", style=dict(color='#00e5ff', marginRight='8px')),
            html.Span("◆ Liq Longs", style=dict(color='#ffab00'))
        ]),
        html.Div([
            html.Span("Bombas Volumen (1s): ", style=dict(fontWeight='bold', color='#d1d4dc', marginRight='6px')),
            html.Span("● Bomba Compra ", style=dict(color='#00e676', marginRight='8px')),
            html.Span("● Bomba Venta", style=dict(color='#ff1744'))
        ]),
        html.Div([
            html.Span("Panel Inferior: ", style=dict(fontWeight='bold', color='#d1d4dc', marginRight='6px')),
            html.Span("Order Flow Delta", style=dict(color='#848e9c'))
        ])
    ]
)

app.layout = html.Div(
    style=dict(backgroundColor='#0b0e14', color='#e6edf3', fontFamily='Arial, sans-serif', padding='10px', minHeight='100vh'),
    children=[
        barra_superior,
        panel_tarjetas,
        barra_leyenda,
        dcc.Store(id='memoria-datos'),
        dcc.Store(id='velas-cliente'),
        dcc.Store(id='libro-cliente'),
        dcc.Graph(
            id='grafico-liquidez',
            style=dict(height='73vh'),
            config=dict(scrollZoom=True, displayModeBar=True)
        ),
        dcc.Interval(id='intervalo-actualizacion', interval=6000, n_intervals=0)
    ]
)
def fmt_coinglass(valor):
    if valor >= 1000000:
        return f"{valor / 1000000:.2f}M"
    elif valor >= 1000:
        return f"{valor / 1000:.0f}K"
    return f"{valor:.0f}"


def color_calor(intensidad):
    if intensidad >= 0.85:
        return "rgba(255, 235, 59, 0.50)"
    elif intensidad >= 0.65:
        return "rgba(255, 152, 0, 0.42)"
    elif intensidad >= 0.45:
        return "rgba(0, 230, 118, 0.32)"
    elif intensidad >= 0.25:
        return "rgba(0, 188, 212, 0.25)"
    else:
        return "rgba(103, 58, 183, 0.20)"


def alinear_a_vela(ts_ms, temporalidad):
    mapa_tf = {'1m': '1min', '5m': '5min', '15m': '15min', '1h': '1h', '4h': '4h', '1d': '1D'}
    freq = mapa_tf.get(temporalidad, '15min')
    return pd.to_datetime(ts_ms, unit='ms').floor(freq).strftime('%Y-%m-%d %H:%M:%S')


# ==============================================================================
# 3. CALLBACK DE DATOS Y PROCESAMIENTO
# ==============================================================================
@app.callback(
    [Output('memoria-datos', 'data'),
     Output('t1-principal', 'children'),
     Output('t1-sub', 'children'),
     Output('t2-titulo', 'children'),
     Output('t2-principal', 'children'),
     Output('t2-sub', 'children'),
     Output('t3-titulo', 'children'),
     Output('t3-principal', 'children'),
     Output('t3-sub', 'children'),
     Output('t4-titulo', 'children'),
     Output('t4-principal', 'children'),
     Output('t4-principal', 'style'),
     Output('t5-principal', 'children'),
     Output('t5-sub', 'children'),
     Output('t6-principal', 'children'),
     Output('t6-sub', 'children')],
    [Input('selector-moneda', 'value'),
     Input('selector-tf', 'value'),
     Input('selector-rango', 'value'),
     Input('selector-capa', 'value'),
     Input('intervalo-actualizacion', 'n_intervals'),
     Input('velas-cliente', 'data'),
     Input('libro-cliente', 'data')
    ]
)
def obtener_datos(simbolo, temporalidad, rango_prof, modo_capa, n, velas, libro):
    headers = {"Accept": "application/json"}
    moneda_base = simbolo.replace("USDT", "")
    etiqueta_rango = "Libro Completo" if rango_prof >= 1.0 else f"±{int(rango_prof * 100)}%"

    try:
        if not isinstance(velas, list) or len(velas) == 0:
            from dash import no_update
            return (no_update,) * 16

        cols = ('time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore')
        df = pd.DataFrame(velas, columns=cols)
        df = df.assign(
            time=pd.to_datetime(df.time, unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S'),
            open=df.open.astype(float),
            high=df.high.astype(float),
            low=df.low.astype(float),
            close=df.close.astype(float),
            volume=df.volume.astype(float),
            qav=df.qav.astype(float),
            taker_quote=df.taker_quote.astype(float)
        )
        df = df.assign(delta=df.taker_quote - (df.qav - df.taker_quote))
        precio_actual = float(df.close.iloc[-1])

        if not isinstance(libro, dict) or 'bids' not in libro:
            from dash import no_update
            return (no_update,) * 16
        bids = pd.DataFrame(libro.get('bids', []), columns=['price', 'qty']).astype(float)
        asks = pd.DataFrame(libro.get('asks', []), columns=['price', 'qty']).astype(float)

        bids = bids.assign(usdt=bids.price * bids.qty)
        asks = asks.assign(usdt=asks.price * asks.qty)
        bids['usdt'] = pd.to_numeric(bids['usdt'], errors='coerce').fillna(0.0)
        asks['usdt'] = pd.to_numeric(asks['usdt'], errors='coerce').fillna(0.0)

        mejor_compra = float(bids.price.max()) if not bids.empty else precio_actual
        mejor_venta = float(asks.price.min()) if not asks.empty else precio_actual

        if rango_prof < 1.0:
            bids_filtrados = bids[bids.price >= precio_actual * (1.0 - rango_prof)].copy()
            asks_filtrados = asks[asks.price <= precio_actual * (1.0 + rango_prof)].copy()
        else:
            bids_filtrados = bids.copy()
            asks_filtrados = asks.copy()

        prof_compra_usdt = float(bids_filtrados.usdt.sum())
        prof_compra_qty = float(bids_filtrados.qty.sum())
        prof_venta_usdt = float(asks_filtrados.usdt.sum())
        prof_venta_qty = float(asks_filtrados.qty.sum())

        total_rango = prof_compra_usdt + prof_venta_usdt
        desequilibrio = ((prof_compra_usdt - prof_venta_usdt) / total_rango * 100) if total_rango > 0 else 0.0
        signo_deseq = "+" if desequilibrio >= 0 else ""
        color_deseq = "#00e676" if desequilibrio >= 0 else "#ff5252"
        estilo_t4 = dict(fontSize='20px', fontWeight='bold', color=color_deseq)

                # Agrupación precisa sin cruzar compra y venta
        bids_filtrados = bids_filtrados[bids_filtrados.price < precio_actual].copy()
        asks_filtrados = asks_filtrados[asks_filtrados.price > precio_actual].copy()

        rango_real_bids = (precio_actual - bids_filtrados.price.min()) if not bids_filtrados.empty else precio_actual * 0.01
        rango_real_asks = (asks_filtrados.price.max() - precio_actual) if not asks_filtrados.empty else precio_actual * 0.01
        rango_max_libro = max(rango_real_bids, rango_real_asks, precio_actual * 0.005)
        paso = rango_max_libro / 18.0

        bids_filtrados = bids_filtrados.assign(zona=((bids_filtrados.price // paso) * paso) + (paso * 0.5))
        asks_filtrados = asks_filtrados.assign(zona=((asks_filtrados.price // paso) * paso) + (paso * 0.5))

        top_bids = bids_filtrados.groupby('zona', as_index=False).usdt.sum().nlargest(12, 'usdt')
        top_asks = asks_filtrados.groupby('zona', as_index=False).usdt.sum().nlargest(12, 'usdt')

        mayor_bid = top_bids.iloc[-len(top_bids)] if not top_bids.empty else pd.Series({'zona': precio_actual, 'usdt': 0})
        mayor_ask = top_asks.iloc[-len(top_asks)] if not top_asks.empty else pd.Series({'zona': precio_actual, 'usdt': 0})

        m_bid_precio = float(mayor_bid.zona)
        m_bid_vol = fmt_coinglass(float(mayor_bid.usdt))
        m_bid_dist = ((m_bid_precio - precio_actual) / precio_actual) * 100

        m_ask_precio = float(mayor_ask.zona)
        m_ask_vol = fmt_coinglass(float(mayor_ask.usdt))
        m_ask_dist = ((m_ask_precio - precio_actual) / precio_actual) * 100

        t1_p = f"{precio_actual:,.3f}"
        t1_s = f"Compra {mejor_compra:,.3f} · Venta {mejor_venta:,.3f}"
        t2_tit = f"Profundidad compra · {etiqueta_rango}"
        t2_p = fmt_coinglass(prof_compra_usdt)
        t2_s = f"{fmt_coinglass(prof_compra_qty)} {moneda_base}"
        t3_tit = f"Profundidad venta · {etiqueta_rango}"
        t3_p = fmt_coinglass(prof_venta_usdt)
        t3_s = f"{fmt_coinglass(prof_venta_qty)} {moneda_base}"
        t4_tit = f"Desequilibrio · {etiqueta_rango}"
        t4_p = f"{signo_deseq}{desequilibrio:.1f}%"
        t5_p = html.Span([f"{m_bid_precio:,.2f} ", html.Span(m_bid_vol, style=dict(fontSize='12px', color='#848e9c', fontWeight='normal'))])
        t5_s = f"{m_bid_dist:+.2f}% del precio"
        t6_p = html.Span([f"{m_ask_precio:,.2f} ", html.Span(m_ask_vol, style=dict(fontSize='12px', color='#848e9c', fontWeight='normal'))])
        t6_s = f"{m_ask_dist:+.2f}% del precio"

               # Rombos de Liquidaciones Reales capturados por WebSocket
        liq_x, liq_y, liq_colores, liq_tamanos, liq_textos = [], [], [], [], []
        t_min = str(df.time.iloc[-len(df)])
        t_max = str(df.time.iloc[-1])
        umbral_l = UMBRAL_LIQ_USDT.get(simbolo, 1500)

        for item in list(liquidaciones_vivo.get(simbolo, [])):
            t_vela = min(alinear_a_vela(item['ts_ms'], temporalidad), t_max)
            if t_vela >= t_min:
                usdt_liq = item['usdt']
                p_liq = item['price']
                es_short = item['es_short_liq']
                liq_x.append(t_vela)
                liq_y.append(p_liq)
                liq_colores.append('#00e5ff' if es_short else '#ffab00')
                liq_tamanos.append(min(max((usdt_liq / umbral_l) * 8, 10), 26))
                tipo_txt = "Liq Short (Compra forzada)" if es_short else "Liq Long (Venta forzada)"
                liq_textos.append(f"◆ {tipo_txt}<br>Monto: {fmt_coinglass(usdt_liq)} | Precio: {p_liq:,.3f}")

        # Bombas de Volumen en tiempo real capturadas por WebSocket
        bomba_x, bomba_y, bomba_colores, bomba_tamanos, bomba_textos = [], [], [], [], []
        umbral_b = UMBRAL_BOMBA_USDT.get(simbolo, 15000)

        for b in list(bombas_vivo.get(simbolo, [])):
            t_vela = min(alinear_a_vela(b['ts_ms'], temporalidad), t_max)
            if t_vela >= t_min:
                usdt_b = b['usdt']
                p_b = b['price']
                es_compra_b = (b['tipo'] == 'COMPRA')
                bomba_x.append(t_vela)
                bomba_y.append(p_b)
                bomba_colores.append('rgba(0, 230, 118, 0.78)' if es_compra_b else 'rgba(255, 23, 68, 0.78)')
                bomba_tamanos.append(min(max((usdt_b / umbral_b) * 16, 16), 42))
                titulo_b = "BOMBA COMPRA AGRESIVA (3s)" if es_compra_b else "BOMBA VENTA AGRESIVA (3s)"
                bomba_textos.append(f"● {titulo_b}<br>Volumen: {fmt_coinglass(usdt_b)} | Precio: {p_b:,.3f}")

                # Dibujo de muros y Mapa de Liquidaciones Estimadas (10x, 25x, 50x, 100x)
        formas = []
        anotaciones = []
        x_inicio = str(df.time.iloc[-len(df)])
        x_fin = str(df.time.iloc[-1])

        # A. Capa de Muros Reales del Libro de Órdenes
        if modo_capa in ('AMBOS', 'MUROS'):
            max_bid_usdt = float(top_bids.usdt.max()) if not top_bids.empty else 1.0
            max_ask_usdt = float(top_asks.usdt.max()) if not top_asks.empty else 1.0

            for _, fila in top_bids.iterrows():
                zona_val = float(fila.zona)
                intensidad = float(fila.usdt) / max_bid_usdt
                vol_cg = fmt_coinglass(float(fila.usdt))
                alpha_v = min(max(intensidad * 0.42, 0.12), 0.48)

                formas.append(dict(
                    type="rect", xref="paper", yref="y",
                    x0=0, x1=1,
                    y0=zona_val - paso * 0.42, y1=zona_val + paso * 0.42,
                    fillcolor=f"rgba(0, 230, 118, {alpha_v:.2f})", line=dict(width=0), layer="below"
                ))

                if intensidad >= 0.48:
                    anotaciones.append(dict(
                        xref="paper", x=0.84, y=zona_val,
                        text=f"Muro compra {vol_cg} ({zona_val:,.2f})",
                        showarrow=False, xanchor="right", yanchor="middle",
                        bgcolor="rgba(19, 23, 34, 0.88)", bordercolor="#00e676",
                        borderwidth=1, borderpad=2, font=dict(color="#00e676", size=10)
                    ))

            for _, fila in top_asks.iterrows():
                zona_val = float(fila.zona)
                intensidad = float(fila.usdt) / max_ask_usdt
                vol_cg = fmt_coinglass(float(fila.usdt))
                alpha_r = min(max(intensidad * 0.42, 0.12), 0.48)

                formas.append(dict(
                    type="rect", xref="paper", yref="y",
                    x0=0, x1=1,
                    y0=zona_val - paso * 0.42, y1=zona_val + paso * 0.42,
                    fillcolor=f"rgba(255, 82, 82, {alpha_r:.2f})", line=dict(width=0), layer="below"
                ))

                if intensidad >= 0.48:
                    anotaciones.append(dict(
                        xref="paper", x=0.84, y=zona_val,
                        text=f"Muro venta {vol_cg} ({zona_val:,.2f})",
                        showarrow=False, xanchor="right", yanchor="middle",
                        bgcolor="rgba(19, 23, 34, 0.88)", bordercolor="#ff5252",
                        borderwidth=1, borderpad=2, font=dict(color="#ff5252", size=10)
                    ))

        # B. Capa de Liquidaciones Estimadas (10x, 25x, 50x, 100x) con corte al ser barridas
        if modo_capa in ('AMBOS', 'LIQ'):
            df_liq = df.tail(90).reset_index(drop=True)
            vol_medio = float(df_liq.volume.mean()) if not df_liq.empty else 1.0
            apalancamientos = (10, 25, 50, 100)
            alto_bloque = precio_actual * 0.0018

            for i in range(len(df_liq) - 1):
                vol_v = float(df_liq.volume.iloc[i])
                if vol_v < vol_medio * 1.15:
                    continue

                t_origen = str(df_liq.time.iloc[i])
                p_ref = float(df_liq.close.iloc[i])
                futuros = df_liq.iloc[i + 1:]

                for apal in apalancamientos:
                    dist_liq = (1.0 / apal) * 0.90
                    p_liq_long = p_ref * (1.0 - dist_liq)
                    p_liq_short = p_ref * (1.0 + dist_liq)

                    # Color según concentración/apalancamiento (Verde -> Amarillo -> Rojo)
                    if apal >= 100:
                        color_pool = "rgba(255, 23, 68, 0.55)"
                    elif apal >= 50:
                        color_pool = "rgba(255, 235, 59, 0.48)"
                    elif apal >= 25:
                        color_pool = "rgba(0, 230, 118, 0.38)"
                    else:
                        color_pool = "rgba(0, 188, 212, 0.28)"

                    # Pool de Longs (abajo): se corta si alguna vela posterior baja hasta p_liq_long
                    barrido_long = futuros[futuros.low <= p_liq_long]
                    t_fin_long = str(barrido_long.time.iloc[-len(barrido_long)]) if not barrido_long.empty else x_fin
                    if t_fin_long > t_origen:
                        formas.append(dict(
                            type="rect", xref="x", yref="y",
                            x0=t_origen, x1=t_fin_long,
                            y0=p_liq_long - alto_bloque, y1=p_liq_long + alto_bloque,
                            fillcolor=color_pool, line=dict(width=0), layer="below"
                        ))

                    # Pool de Shorts (arriba): se corta si alguna vela posterior sube hasta p_liq_short
                    barrido_short = futuros[futuros.high >= p_liq_short]
                    t_fin_short = str(barrido_short.time.iloc[-len(barrido_short)]) if not barrido_short.empty else x_fin
                    if t_fin_short > t_origen:
                        formas.append(dict(
                            type="rect", xref="x", yref="y",
                            x0=t_origen, x1=t_fin_short,
                            y0=p_liq_short - alto_bloque, y1=p_liq_short + alto_bloque,
                            fillcolor=color_pool, line=dict(width=0), layer="below"
                        ))

        formas.append(dict(type="line", x0=x_inicio, x1=x_fin, y0=precio_actual, y1=precio_actual, line=dict(color="#ffffff", width=1.2, dash="dot")))
        anotaciones.append(dict(xref="paper", x=1.002, y=precio_actual, text=f"<b>{precio_actual:,.3f}</b>", showarrow=False, xanchor="left", yanchor="middle", bgcolor="#ffffff", bordercolor="#ffffff", borderwidth=1, borderpad=3, font=dict(color="#0b0e14", size=11)))

        perfil_y = tuple(float(v) for v in pd.concat((top_bids.zona, top_asks.zona)))
        perfil_x = tuple(float(v) / 1000 for v in pd.concat((top_bids.usdt, top_asks.usdt)))
        max_k = max(perfil_x) if perfil_x else 100.0
        colores_barra = tuple('#00e676' if p < precio_actual else '#ff5252' for p in perfil_y)

        delta_vals = tuple(float(v) / 1000 for v in df.delta)
        delta_colores = tuple('#089981' if v >= 0 else '#f23645' for v in delta_vals)

        datos_fig = dict(
            clave=f"{simbolo}-{temporalidad}-{rango_prof}",
            titulo=f"{moneda_base} · Binance Perp · {temporalidad.upper()} · {etiqueta_rango} | Compra {mejor_compra:,.3f} · Venta {mejor_venta:,.3f}",
            time=tuple(df.time),
            open=tuple(df.open),
            high=tuple(df.high),
            low=tuple(df.low),
            close=tuple(df.close),
            perfil_x=perfil_x,
            perfil_y=perfil_y,
            max_k=max_k,
            colores_barra=colores_barra,
            delta_vals=delta_vals,
            delta_colores=delta_colores,
            liq_x=tuple(liq_x),
            liq_y=tuple(liq_y),
            liq_colores=tuple(liq_colores),
            liq_tamanos=tuple(liq_tamanos),
            liq_textos=tuple(liq_textos),
            bomba_x=tuple(bomba_x),
            bomba_y=tuple(bomba_y),
            bomba_colores=tuple(bomba_colores),
            bomba_tamanos=tuple(bomba_tamanos),
            bomba_textos=tuple(bomba_textos),
            formas=formas,
            anotaciones=anotaciones
        )
        return datos_fig, t1_p, t1_s, t2_tit, t2_p, t2_s, t3_tit, t3_p, t3_s, t4_tit, t4_p, estilo_t4, t5_p, t5_s, t6_p, t6_s

    except Exception as e:
        import traceback
        traceback.print_exc()
        from dash import no_update
        return (no_update,) * 16



# ==============================================================================
# 4. RENDERIZADO EN CLIENTE (PLOTLY JAVASCRIPT)
# ==============================================================================
app.clientside_callback(
    """
    function(datos, figActual) {
        if (!datos) return window.dash_clientside.no_update;
        if (datos.error) {
            return {data: [], layout: {template: 'plotly_dark', title: 'Error: ' + datos.error}};
        }

        if (!window.cursorTvListo) {
            window.cursorTvListo = true;
            var etiqueta = document.createElement('div');
            etiqueta.id = 'etiqueta-cursor-derecha';
            etiqueta.style.position = 'fixed';
            etiqueta.style.display = 'none';
            etiqueta.style.backgroundColor = '#2a2e39';
            etiqueta.style.color = '#ffffff';
            etiqueta.style.border = '1px solid #787b86';
            etiqueta.style.padding = '2px 6px';
            etiqueta.style.fontSize = '11px';
            etiqueta.style.fontWeight = 'bold';
            etiqueta.style.fontFamily = 'Arial, sans-serif';
            etiqueta.style.borderRadius = '3px';
            etiqueta.style.pointerEvents = 'none';
            etiqueta.style.zIndex = '99999';
            document.body.appendChild(etiqueta);

            document.addEventListener('mousemove', function(ev) {
                var plot = document.querySelector('#grafico-liquidez .js-plotly-plot');
                if (!plot || !plot._fullLayout || !plot._fullLayout.yaxis) return;
                var ya = plot._fullLayout.yaxis;
                var xa = plot._fullLayout.xaxis;
                var caja = plot.getBoundingClientRect();
                var escalaY = caja.height / plot._fullLayout.height;
                var escalaX = caja.width / plot._fullLayout.width;

                var yLocal = (ev.clientY - caja.top) / escalaY - ya._offset;
                var xLocal = (ev.clientX - caja.left) / escalaX - xa._offset;

                if (xLocal >= 0 && xLocal <= xa._length && yLocal >= 0 && yLocal <= ya._length) {
                    var precio = ya.p2d(yLocal);
                    etiqueta.textContent = precio.toLocaleString('en-US', {minimumFractionDigits: 3, maximumFractionDigits: 3});
                    etiqueta.style.display = 'block';
                    etiqueta.style.left = (caja.left + (xa._offset + xa._length) * escalaX + 4) + 'px';
                    etiqueta.style.top = (ev.clientY - 10) + 'px';
                } else {
                    etiqueta.style.display = 'none';
                }
            });
        }

        var data = [
            {
                type: 'candlestick',
                x: datos.time,
                open: datos.open,
                high: datos.high,
                low: datos.low,
                close: datos.close,
                name: 'Precio',
                yaxis: 'y',
                hoverinfo: 'skip',
                increasing: {line: {color: '#089981'}, fillcolor: '#089981'},
                decreasing: {line: {color: '#f23645'}, fillcolor: '#f23645'}
            },
            {
                type: 'bar',
                x: datos.perfil_x,
                y: datos.perfil_y,
                orientation: 'h',
                xaxis: 'x2',
                yaxis: 'y',
                hoverinfo: 'skip',
                marker: {color: datos.colores_barra, opacity: 0.45},
                name: 'Muros'
            },
            {
                type: 'scatter',
                mode: 'markers',
                x: datos.bomba_x,
                y: datos.bomba_y,
                yaxis: 'y',
                text: datos.bomba_textos,
                marker: {symbol: 'circle', size: datos.bomba_tamanos, color: datos.bomba_colores, line: {width: 1.5, color: '#ffffff'}},
                name: 'Bombas',
                hovertemplate: '%{text}<extra></extra>'
            },
            {
                type: 'scatter',
                mode: 'markers',
                x: datos.liq_x,
                y: datos.liq_y,
                yaxis: 'y',
                text: datos.liq_textos,
                marker: {symbol: 'diamond', size: datos.liq_tamanos, color: datos.liq_colores, line: {width: 1.2, color: '#ffffff'}},
                name: 'Liquidaciones',
                hovertemplate: '%{text}<extra></extra>'
            },
            {
                type: 'bar',
                x: datos.time,
                y: datos.delta_vals,
                yaxis: 'y2',
                marker: {color: datos.delta_colores, opacity: 0.85},
                name: 'Delta',
                hovertemplate: 'Delta: %{y:,.0f}K USDT<extra></extra>'
            }
        ];

        var layout = {
            template: 'plotly_dark',
            paper_bgcolor: '#0b0e14',
            plot_bgcolor: '#0b0e14',
            showlegend: false,
            dragmode: 'pan',
            uirevision: datos.clave,
            hovermode: 'closest',
            hoverlabel: {bgcolor: '#1e222d', bordercolor: '#434651', font: {color: '#ffffff', size: 11, family: 'Arial'}},
            spikedistance: 20,
            shapes: datos.formas,
            annotations: datos.anotaciones,
            margin: {l: 10, r: 75, t: 30, b: 20},
            yaxis: {
                domain: [0.24, 1.0],
                side: 'right',
                gridcolor: '#1c202a',
                fixedrange: false,
                tickformat: ',.3f',
                uirevision: datos.clave,
                showspikes: true,
                spikemode: 'across',
                spikesnap: 'cursor',
                spikecolor: '#9598a1',
                spikethickness: 1,
                spikedash: 'dash'
            },
            yaxis2: {
                domain: [0.0, 0.20],
                side: 'right',
                gridcolor: '#1c202a',
                fixedrange: false,
                uirevision: datos.clave,
                title: {text: 'Delta (K)', font: {size: 10, color: '#848e9c'}}
            },
            xaxis: {
                rangeslider: {visible: false},
                gridcolor: '#1c202a',
                uirevision: datos.clave,
                showspikes: true,
                spikemode: 'across',
                spikesnap: 'cursor',
                spikecolor: '#9598a1',
                spikethickness: 1,
                spikedash: 'dash'
            },
            xaxis2: {
                overlaying: 'x',
                side: 'top',
                range: [datos.max_k * 6, 0],
                showgrid: false,
                showticklabels: false,
                fixedrange: true
            },
            title: {text: datos.titulo, font: {size: 12, color: '#848e9c'}, x: 0.01}
        };

        if (figActual && figActual.layout && figActual.layout.uirevision === datos.clave) {
            if (figActual.layout.xaxis && figActual.layout.xaxis.range) {
                layout.xaxis.range = figActual.layout.xaxis.range;
                layout.xaxis.autorange = false;
            }
            if (figActual.layout.yaxis && figActual.layout.yaxis.range) {
                layout.yaxis.range = figActual.layout.yaxis.range;
                layout.yaxis.autorange = false;
            }
        }
        return {data: data, layout: layout};
    }
    """,
    Output('grafico-liquidez', 'figure'),
    Input('memoria-datos', 'data'),
    Input('grafico-liquidez', 'figure')
)
app.clientside_callback(
    """
    async function(simbolo, tf, n) {
        if (!simbolo || !tf) return [window.dash_clientside.no_update, window.dash_clientside.no_update];
        window._ultimaVelas = window._ultimaVelas || {};
        const clave = simbolo + '_' + tf;
        const ahora = Date.now();
        let velasOut = window.dash_clientside.no_update;
        let libroOut = window.dash_clientside.no_update;
        try {
            if (!window._ultimaVelas[clave] || (ahora - window._ultimaVelas[clave]) >= 10000) {
                const uV = 'https:' + '//fapi.binance.com/fapi/v1/klines?symbol=' + simbolo + '&interval=' + tf + '&limit=1000';
                const dV = await (await fetch(uV)).json();
                if (Array.isArray(dV) && dV.length > 0) {
                    window._ultimaVelas[clave] = ahora;
                    velasOut = dV;
                }
            }
            const uL = 'https:' + '//fapi.binance.com/fapi/v1/depth?symbol=' + simbolo + '&limit=500';
            const dL = await (await fetch(uL)).json();
            if (dL && Array.isArray(dL.bids) && dL.bids.length > 0) {
                libroOut = dL;
            }
        } catch (e) {}
        return [velasOut, libroOut];
    }
    """,
    [Output('velas-cliente', 'data'),
     Output('libro-cliente', 'data')],
    [Input('selector-moneda', 'value'),
     Input('selector-tf', 'value'),
     Input('intervalo-actualizacion', 'n_intervals')]
)
app.clientside_callback(
    """
    function(fig, n) {
        window._vivo = window._vivo || {
            liq: {HYPEUSDT: [], BTCUSDT: [], ETHUSDT: [], SOLUSDT: []},
            bombas: {HYPEUSDT: [], BTCUSDT: [], ETHUSDT: [], SOLUSDT: []},
            buf: {},
            estado: 'Conectando...'
        };
        const UMB_B = {HYPEUSDT: 5000, BTCUSDT: 25000, ETHUSDT: 15000, SOLUSDT: 10000};
        const UMB_L = {HYPEUSDT: 500, BTCUSDT: 2000, ETHUSDT: 1500, SOLUSDT: 1000};

        if (!window._wsClienteOK) {
            window._wsClienteOK = true;
            const streams = ['!forceOrder@arr', 'hypeusdt@aggTrade', 'btcusdt@aggTrade', 'ethusdt@aggTrade', 'solusdt@aggTrade'].join('/');
            function conectar() {
                const urlWs = 'wss:' + '//fstream.binance.com/stream?streams=' + streams;
                const ws = new WebSocket(urlWs);
                ws.onopen = function() { window._vivo.estado = 'WS Vivo'; };
                ws.onerror = function() { window._vivo.estado = 'Error WS'; };
                ws.onmessage = function(ev) {
                    try {
                        const msg = JSON.parse(ev.data);
                        const st = msg.stream || '', d = msg.data || {};
                        if (st === '!forceOrder@arr' && d.o) {
                            const o = d.o, sim = o.s;
                            if (window._vivo.liq[sim]) {
                                const p = parseFloat(o.ap || o.p || 0), usdt = p * parseFloat(o.q || 0);
                                if (usdt >= (UMB_L[sim] || 1000)) {
                                    window._vivo.liq[sim].push({ts: o.T || Date.now(), price: p, usdt: usdt, esShort: o.S === 'BUY'});
                                    if (window._vivo.liq[sim].length > 150) window._vivo.liq[sim].shift();
                                }
                            }
                        } else if (st.includes('@aggTrade')) {
                            const sim = d.s;
                            if (window._vivo.bombas[sim]) {
                                const p = parseFloat(d.p || 0), usdt = p * parseFloat(d.q || 0);
                                const win = Math.floor((d.T || Date.now()) / 3000);
                                window._vivo.buf[sim] = window._vivo.buf[sim] || {w: win, buy: 0, sell: 0, p: p};
                                const b = window._vivo.buf[sim];
                                if (b.w !== win) {
                                    const umb = UMB_B[sim] || 10000;
                                    if (b.buy >= umb) window._vivo.bombas[sim].push({ts: b.w * 3000, price: b.p, usdt: b.buy, tipo: 'COMPRA'});
                                    if (b.sell >= umb) window._vivo.bombas[sim].push({ts: b.w * 3000, price: b.p, usdt: b.sell, tipo: 'VENTA'});
                                    if (window._vivo.bombas[sim].length > 100) window._vivo.bombas[sim].shift();
                                    b.w = win; b.buy = 0; b.sell = 0;
                                }
                                b.p = p;
                                if (d.m === true) b.sell += usdt; else b.buy += usdt;
                            }
                        }
                    } catch (e) {}
                };
                ws.onclose = function() { window._vivo.estado = 'Reconectando'; setTimeout(conectar, 2000); };
            }
            conectar();
        }

        const gd = document.querySelector('#grafico-liquidez .js-plotly-plot');
        if (!gd || !gd.data || gd.data.length < 4) return window.dash_clientside.no_update;

        const tit = (gd.layout && gd.layout.title && gd.layout.title.text) || '';
        const sim = tit.startsWith('HYPE') ? 'HYPEUSDT' : (tit.startsWith('BTC') ? 'BTCUSDT' : (tit.startsWith('ETH') ? 'ETHUSDT' : 'SOLUSDT'));
        const tf = tit.includes('1M ') ? '1m' : (tit.includes('5M ') ? '5m' : (tit.includes('15M ') ? '15m' : (tit.includes('1H ') ? '1h' : (tit.includes('4H ') ? '4h' : '1d'))));
        const step = {'1m': 60000, '5m': 300000, '15m': 900000, '1h': 3600000, '4h': 14400000, '1d': 86400000}[tf] || 60000;

        const velasX = gd.data.at(0).x || [];
        if (velasX.length === 0) return window.dash_clientside.no_update;
        const tMin = velasX.at(0), tMax = velasX.at(-1);

        const aStr = ms => {
            const d = new Date(Math.floor(ms / step) * step), p = x => String(x).padStart(2, '0');
            return `${d.getUTCFullYear()}-${p(d.getUTCMonth()+1)}-${p(d.getUTCDate())} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}`;
        };
        const fmt = v => v >= 1e6 ? (v/1e6).toFixed(2)+'M' : (v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v.toFixed(0));

        let bX=[], bY=[], bC=[], bS=[], bT=[];
        (window._vivo.bombas[sim] || []).forEach(b => {
            let tv = aStr(b.ts); if (tv > tMax) tv = tMax;
            if (tv >= tMin) {
                bX.push(tv); bY.push(b.price);
                bC.push(b.tipo === 'COMPRA' ? 'rgba(0,230,118,0.85)' : 'rgba(255,23,68,0.85)');
                bS.push(Math.min(Math.max((b.usdt / UMB_B[sim]) * 14, 15), 38));
                bT.push(`● BOMBA ${b.tipo} (3s)<br>Vol: ${fmt(b.usdt)} | Precio: ${b.price.toFixed(3)}`);
            }
        });

        let lX=[], lY=[], lC=[], lS=[], lT=[];
        (window._vivo.liq[sim] || []).forEach(l => {
            let tv = aStr(l.ts); if (tv > tMax) tv = tMax;
            if (tv >= tMin) {
                lX.push(tv); lY.push(l.price);
                lC.push(l.esShort ? '#00e5ff' : '#ffab00');
                lS.push(Math.min(Math.max((l.usdt / UMB_L[sim]) * 10, 12), 28));
                lT.push(`◆ ${l.esShort ? 'Liq Short' : 'Liq Long'}<br>Monto: ${fmt(l.usdt)} | Precio: ${l.price.toFixed(3)}`);
            }
        });

        setTimeout(() => {
            Plotly.restyle(gd, {x: [bX, lX], y: [bY, lY], text: [bT, lT], 'marker.color': [bC, lC], 'marker.size': [bS, lS]}, Array.of(2, 3));
        }, 150);

               const totB = (window._vivo.bombas[sim] || []).length;
        const totL = (window._vivo.liq[sim] || []).length;
        return `● ${window._vivo.estado} | Bombas: ${totB} (${bX.length}) · Liq: ${totL} (${lX.length})`;
    }
    """,
    Output('t1-sub', 'children'),
    [Input('grafico-liquidez', 'figure'),
     Input('intervalo-actualizacion', 'n_intervals')]
)

import os

iniciar_websocket_binance()

if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=puerto)

