import os
import requests
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html
from dash.dependencies import Input, Output

app = Dash(__name__)
server = app.server  # Indispensable para la nube

app.layout = html.Div(style={'backgroundColor': '#0d1117', 'height': '100vh', 'margin': '0'}, children=[
    dcc.Graph(
        id='heatmap-orderflow',
        style={'height': '96vh'},
        config={'displayModeBar': False}
    ),
    dcc.Interval(id='intervalo', interval=2500, n_intervals=0)
])

@app.callback(
    Output('heatmap-orderflow', 'figure'),
    Input('intervalo', 'n_intervals')
)
def actualizar_grafica(n):
    url = "https://binance.com"
    params = {"symbol": "BTCUSDT", "limit": 50}
    datos = requests.get(url, params=params).json()
    
    bids = pd.DataFrame(datos['bids'], columns=['precio', 'volumen'], dtype=float)
    asks = pd.DataFrame(datos['asks'], columns=['precio', 'volumen'], dtype=float)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=bids['precio'], x=bids['volumen'],
        orientation='h', name='Compras',
        marker=dict(color='rgba(0, 255, 136, 0.75)')
    ))
    
    fig.add_trace(go.Bar(
        y=asks['precio'], x=asks['volumen'],
        orientation='h', name='Ventas',
        marker=dict(color='rgba(255, 68, 68, 0.75)')
    ))
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0d1117',
        plot_bgcolor='#0d1117',
        margin=dict(l=10, r=65, t=35, b=20),
        uirevision='fijo',  # Evita que el gráfico se centre solo al moverlo
        yaxis=dict(
            side='right',
            tickformat=',.1f',
            title=''
        ),
        xaxis=dict(title='Volumen BTC', showgrid=False),
        showlegend=False,
        title=dict(text='Order Flow BTC/USDT', x=0.05, font=dict(size=15))
    )
    return fig

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    app.run(host='0.0.0.0', port=port)
