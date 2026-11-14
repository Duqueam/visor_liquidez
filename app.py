import webbrowser
from threading import Timer
import requests
import pandas as pd
from dash import Dash, dcc, html, Input, Output

app = Dash(__name__)
server = app.server
app.title = "Visor Cripto Pro - Mapa de Calor + Order Flow"

estilo_tarjeta = dict(
    backgroundColor='#131722',
    border='1px solid #242936',
    borderRadius='6px',
    padding='10px 14px',
    flex='1',
    minWidth='150px'
)

app.layout = html.Div(style=dict(backgroundColor='#0b0e14', color='#e6edf3', fontFamily='Arial, sans-serif', padding='10px', minHeight='100vh'), children=(
    html.Div(style=dict(display='flex', justifyContent='space-between', alignItems='center', marginBottom='8px', backgroundColor='#131722', padding='8px 16px', borderRadius='6px', border='1px solid #242936'), children=(
        html.Div(style=dict(display='flex', alignItems='center', gap='10px'), children=(
            html.Span("Mapa de calor + Order Flow", style=dict(fontWeight='bold', fontSize='15px', color='#ffffff')),
            html.Span("Binance Perp", style=dict(backgroundColor='#242936', color='#848e9c', padding='2px 8px', borderRadius='4px', fontSize='11px', fontWeight='bold'))
        )),
        html.Div(style=dict(display='flex', gap='12px', alignItems='center'), children=(
            dcc.Dropdown(
                id='selector-moneda',
                options=(
                    dict(label='HYPEUSDT Perp', value='HYPEUSDT'),
                    dict(label='BTCUSDT Perp', value='BTCUSDT'),
                    dict(label='ETHUSDT Perp', value='ETHUSDT'),
                    dict(label='SOLUSDT Perp', value='SOLUSDT'),
                ),
                value='HYPEUSDT',
                clearable=False,
                style=dict(width='155px', color='#000', fontSize='12px', fontWeight='bold')
            ),
            dcc.Dropdown(
                id='selector-tf',
                options=(
                    dict(label='15m', value='15m'),
                    dict(label='1H', value='1h'),
                    dict(label='4H', value='4h'),
                    dict(label='1D', value='1d'),
                ),
                value='4h',
                clearable=False,
                style=dict(width='80px', color='#000', fontSize='12px', fontWeight='bold')
            ),
            html.Span("● En vivo", style=dict(color='#00e676', fontSize='12px', fontWeight='bold'))
        ))
    )),

    html.Div(id='panel-6-tarjetas', style=dict(display='flex', gap='8px', marginBottom='8px', flexWrap='wrap'), children=(
        html.Div(style=estilo_tarjeta, children=(
            html.Div("Último precio · Binance Perp", style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t1-principal', style=dict(fontSize='20px', fontWeight='bold', color='#ffffff')),
            html.Div("Compra -- · Venta --", id='t1-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        )),
        html.Div(style=estilo_tarjeta, children=(
            html.Div("Profundidad de compra · 1%", style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t2-principal', style=dict(fontSize='20px', fontWeight='bold', color='#00e676')),
            html.Div("-- monedas", id='t2-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        )),
        html.Div(style=estilo_tarjeta, children=(
            html.Div("Profundidad de venta · 1%", style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t3-principal', style=dict(fontSize='20px', fontWeight='bold', color='#ff5252')),
            html.Div("-- monedas", id='t3-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        )),
        html.Div(style=estilo_tarjeta, children=(
            html.Div("Desequilibrio · ±1%", style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t4-principal', style=dict(fontSize='20px', fontWeight='bold', color='#00e676')),
            html.Div("Presión libro cercano", id='t4-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        )),
        html.Div(style=estilo_tarjeta, children=(
            html.Div("Mayor muro de compra", style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t5-principal', style=dict(fontSize='20px', fontWeight='bold', color='#00e676')),
            html.Div("-- del precio", id='t5-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        )),
        html.Div(style=estilo_tarjeta, children=(
            html.Div("Mayor muro de venta", style=dict(fontSize='11px', color='#848e9c', marginBottom='4px')),
            html.Div("--", id='t6-principal', style=dict(fontSize='20px', fontWeight='bold', color='#ff5252')),
            html.Div("-- del precio", id='t6-sub', style=dict(fontSize='11px', color='#848e9c', marginTop='3px'))
        )),
    )),

    html.Div(style=dict(display='flex', justifyContent='space-between', alignItems='center', marginBottom='6px', backgroundColor='#131722', padding='5px 14px', borderRadius='4px', fontSize='11px', border='1px solid #1e222d'), children=(
        html.Div((
            html.Span("Calor libro: ", style=dict(fontWeight='bold', color='#d1d4dc', marginRight='6px')),
            html.Span("■ Bajo ", style=dict(color='#9575cd', marginRight='6px')),
            html.Span("■ Alto ", style=dict(color='#00e676', marginRight='6px')),
            html.Span("■ Máximo", style=dict(color='#ffeb3b')),
        )),
        html.Div((
            html.Span("Rombos Liq Reales: ", style=dict(fontWeight='bold', color='#d1d4dc', marginRight='6px')),
            html.Span("◆ Liq Shorts ", style=dict(color='#00e5ff', marginRight='8px')),
            html.Span("◆ Liq Longs", style=dict(color='#ffab00')),
        )),
        html.Div((
            html.Span("Panel Inferior: ", style=dict(fontWeight='bold', color='#d1d4dc', marginRight='6px')),
            html.Span("Order Flow (Delta Compras vs Ventas a Mercado)", style=dict(color='#848e9c')),
        ))
    )),

    dcc.Store(id='memoria-datos'),
    dcc.Graph(
        id='grafico-liquidez',
        style=dict(height='74vh'),
        config=dict(scrollZoom=True, displayModeBar=True)
    ),
    dcc.Interval(id='intervalo-actualizacion', interval=6000, n_intervals=0)
))

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
@app.callback(
    (Output('memoria-datos', 'data'),
     Output('t1-principal', 'children'),
     Output('t1-sub', 'children'),
     Output('t2-principal', 'children'),
     Output('t2-sub', 'children'),
     Output('t3-principal', 'children'),
     Output('t3-sub', 'children'),
     Output('t4-principal', 'children'),
     Output('t4-principal', 'style'),
     Output('t5-principal', 'children'),
     Output('t5-sub', 'children'),
     Output('t6-principal', 'children'),
     Output('t6-sub', 'children')),
    (Input('selector-moneda', 'value'),
     Input('selector-tf', 'value'),
     Input('intervalo-actualizacion', 'n_intervals'))
)
def obtener_datos(simbolo, temporalidad, n):
    headers = dict(**{"User-Agent": "Mozilla/5.0"})
    moneda_base = simbolo.replace("USDT", "")
    try:
        base = "https://" + "fapi." + "binance." + "com"
        velas = requests.get(base + "/fapi/v1/klines", params=dict(symbol=simbolo, interval=temporalidad, limit=120), headers=headers, timeout=8).json()

        cols = ('time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore')
        df = pd.DataFrame(velas, columns=cols)
        df = df.assign(
            time=pd.to_datetime(df.time, unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S'),
            open=df.open.astype(float),
            high=df.high.astype(float),
            low=df.low.astype(float),
            close=df.close.astype(float),
            qav=df.qav.astype(float),
            taker_quote=df.taker_quote.astype(float)
        )
        # Cálculo de Order Flow (Delta = Compras a mercado - Ventas a mercado en USDT)
        df = df.assign(delta=df.taker_quote - (df.qav - df.taker_quote))
        precio_actual = float(df.close.iloc[-1])

        libro = requests.get(base + "/fapi/v1/depth", params=dict(symbol=simbolo, limit=1000), headers=headers, timeout=8).json()
        bids = pd.DataFrame(libro.get('bids'), columns=('price', 'qty'), dtype=float)
        asks = pd.DataFrame(libro.get('asks'), columns=('price', 'qty'), dtype=float)

        bids = bids.assign(usdt=bids.price * bids.qty)
        asks = asks.assign(usdt=asks.price * asks.qty)

        mejor_compra = float(bids.price.max()) if not bids.empty else precio_actual
        mejor_venta = float(asks.price.min()) if not asks.empty else precio_actual

        bids_1pct = bids[bids.price >= precio_actual * 0.99]
        asks_1pct = asks[asks.price <= precio_actual * 1.01]

        prof_compra_usdt = float(bids_1pct.usdt.sum())
        prof_compra_qty = float(bids_1pct.qty.sum())
        prof_venta_usdt = float(asks_1pct.usdt.sum())
        prof_venta_qty = float(asks_1pct.qty.sum())

        total_1pct = prof_compra_usdt + prof_venta_usdt
        desequilibrio = ((prof_compra_usdt - prof_venta_usdt) / total_1pct * 100) if total_1pct > 0 else 0.0
        signo_deseq = "+" if desequilibrio >= 0 else ""
        color_deseq = "#00e676" if desequilibrio >= 0 else "#ff5252"
        estilo_t4 = dict(fontSize='20px', fontWeight='bold', color=color_deseq)

        paso = precio_actual * 0.0025
        bids = bids.assign(zona=(bids.price // paso) * paso)
        asks = asks.assign(zona=(asks.price // paso) * paso)

        top_bids = bids.groupby('zona', as_index=False).usdt.sum().nlargest(12, 'usdt')
        top_asks = asks.groupby('zona', as_index=False).usdt.sum().nlargest(12, 'usdt')

        mayor_bid = top_bids.iloc[-len(top_bids)]
        mayor_ask = top_asks.iloc[-len(top_asks)]

        m_bid_precio = float(mayor_bid.zona)
        m_bid_vol = fmt_coinglass(float(mayor_bid.usdt))
        m_bid_dist = ((m_bid_precio - precio_actual) / precio_actual) * 100

        m_ask_precio = float(mayor_ask.zona)
        m_ask_vol = fmt_coinglass(float(mayor_ask.usdt))
        m_ask_dist = ((m_ask_precio - precio_actual) / precio_actual) * 100

        t1_p = f"{precio_actual:,.3f}"
        t1_s = f"Compra {mejor_compra:,.3f} · Venta {mejor_venta:,.3f}"
        t2_p = fmt_coinglass(prof_compra_usdt)
        t2_s = f"{fmt_coinglass(prof_compra_qty)} {moneda_base}"
        t3_p = fmt_coinglass(prof_venta_usdt)
        t3_s = f"{fmt_coinglass(prof_venta_qty)} {moneda_base}"
        t4_p = f"{signo_deseq}{desequilibrio:.1f}%"
        t5_p = html.Span((f"{m_bid_precio:,.2f} ", html.Span(m_bid_vol, style=dict(fontSize='12px', color='#848e9c', fontWeight='normal'))))
        t5_s = f"{m_bid_dist:+.2f}% del precio"
        t6_p = html.Span((f"{m_ask_precio:,.2f} ", html.Span(m_ask_vol, style=dict(fontSize='12px', color='#848e9c', fontWeight='normal'))))
        t6_s = f"{m_ask_dist:+.2f}% del precio"

        # Rombos de Liquidaciones Reales en tiempo real
        liq_x = []
        liq_y = []
        liq_colores = []
        liq_tamanos = []
        liq_textos = []
        try:
            ordenes_liq = requests.get(base + "/fapi/v1/allForceOrders", params=dict(symbol=simbolo, limit=50), headers=headers, timeout=4).json()
            if isinstance(ordenes_liq, list):
                t_min = str(df.time.iloc[-len(df)])
                for item in ordenes_liq:
                    t_liq = pd.to_datetime(item.get('time'), unit='ms').strftime('%Y-%m-%d %H:%M:%S')
                    if t_liq >= t_min:
                        p_liq = float(item.get('averagePrice') or item.get('price'))
                        q_liq = float(item.get('origQty'))
                        usdt_liq = p_liq * q_liq
                        lado_liq = item.get('side')
                        es_short_liq = (lado_liq == 'BUY')
                        liq_x.append(t_liq)
                        liq_y.append(p_liq)
                        liq_colores.append('#00e5ff' if es_short_liq else '#ffab00')
                        liq_tamanos.append(min(max(usdt_liq / 15000, 9), 22))
                        tipo_txt = "Liq Short (Compra forzada)" if es_short_liq else "Liq Long (Venta forzada)"
                        liq_textos.append(f"◆ {tipo_txt}<br>Monto: {fmt_coinglass(usdt_liq)} | Precio: {p_liq:,.3f}")
        except Exception:
            pass

        todos_muros = pd.concat((top_bids, top_asks), ignore_index=True)
        max_usdt = float(todos_muros.usdt.max()) if not todos_muros.empty else 1.0

        formas = []
        anotaciones = []
        x_inicio = str(df.time.iloc[-len(df)])
        x_fin = str(df.time.iloc[-1])

        for _, fila in todos_muros.iterrows():
            intensidad = float(fila.usdt) / max_usdt
            zona_val = float(fila.zona)
            vol_cg = fmt_coinglass(float(fila.usdt))
            es_compra = zona_val < precio_actual
            lado = "Muro compra" if es_compra else "Muro venta"

            formas.append(dict(type="rect", xref="x", yref="y", x0=x_inicio, x1=x_fin, y0=zona_val - paso * 0.4, y1=zona_val + paso * 0.4, fillcolor=color_calor(intensidad), line=dict(width=0), layer="below"))

            if intensidad >= 0.50:
                color_txt = "#00e676" if es_compra else "#ff5252"
                anotaciones.append(dict(xref="paper", x=0.84, y=zona_val, text=f"{lado} {vol_cg} ({zona_val:,.2f})", showarrow=False, xanchor="right", yanchor="middle", bgcolor="rgba(19, 23, 34, 0.88)", bordercolor=color_txt, borderwidth=1, borderpad=2, font=dict(color=color_txt, size=10)))

        formas.append(dict(type="line", x0=x_inicio, x1=x_fin, y0=precio_actual, y1=precio_actual, line=dict(color="#ffffff", width=1.2, dash="dot")))
        anotaciones.append(dict(xref="paper", x=1.002, y=precio_actual, text=f"<b>{precio_actual:,.3f}</b>", showarrow=False, xanchor="left", yanchor="middle", bgcolor="#ffffff", bordercolor="#ffffff", borderwidth=1, borderpad=3, font=dict(color="#0b0e14", size=11)))

        perfil_y = tuple(float(v) for v in pd.concat((top_bids.zona, top_asks.zona)))
        perfil_x = tuple(float(v) / 1000 for v in pd.concat((top_bids.usdt, top_asks.usdt)))
        max_k = max(perfil_x) if perfil_x else 100.0
        colores_barra = tuple('#00e676' if p < precio_actual else '#ff5252' for p in perfil_y)

        delta_vals = tuple(float(v) / 1000 for v in df.delta)
        delta_colores = tuple('#089981' if v >= 0 else '#f23645' for v in delta_vals)

        datos_fig = dict(
            clave=f"{simbolo}-{temporalidad}",
            titulo=f"{moneda_base} · Binance Perp · {temporalidad.upper()} | Compra {mejor_compra:,.3f} · Venta {mejor_venta:,.3f}",
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
            formas=formas,
            anotaciones=anotaciones
        )
        return datos_fig, t1_p, t1_s, t2_p, t2_s, t3_p, t3_s, t4_p, estilo_t4, t5_p, t5_s, t6_p, t6_s

    except Exception as error:
        estilo_err = dict(fontSize='20px', fontWeight='bold', color='#ff5252')
        return dict(error=str(error)), "Error", str(error), "--", "--", "--", "--", "--", estilo_err, "--", "--", "--", "--"

app.clientside_callback(
    """
    function(datos, figActual) {
        if (!datos) return window.dash_clientside.no_update;
       if (datos.error) {
    return window.dash_clientside.no_update;
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

        var data = new Array(
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
                x: datos.liq_x,
                y: datos.liq_y,
                yaxis: 'y',
                text: datos.liq_textos,
                marker: {symbol: 'diamond', size: datos.liq_tamanos, color: datos.liq_colores, line: {width: 1, color: '#ffffff'}},
                name: 'Liquidaciones',
                hovertemplate: '%{text}<extra></extra>'
            },
            {
                type: 'bar',
                x: datos.time,
                y: datos.delta_vals,
                yaxis: 'y2',
                marker: {color: datos.delta_colores, opacity: 0.85},
                name: 'Order Flow Delta',
                hovertemplate: 'Delta: %{y:,.0f}K USDT<extra></extra>'
            }
        );
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
                domain: new Array(0.24, 1.0),
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
                domain: new Array(0.0, 0.20),
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
                range: new Array(datos.max_k * 6, 0),
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

def abrir_navegador():
    webbrowser.open_new("http://" + "localhost:8050/")

if __name__ == '__main__':
    Timer(2.0, abrir_navegador).start()
    app.run(debug=False, host="127.0.0.1", port=8050)
