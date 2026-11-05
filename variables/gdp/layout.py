"""State-level quarterly GDP comparison, display-only."""
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
from plotly.subplots import make_subplots
from config import CHART_HEIGHT
from variables.gdp.data import load_gdp_forecasts


def gdp_layout():
    return html.Div(className='population-page', children=[
        html.Header(className='header', style={'gridColumn': '1 / -1'}, children=[
            html.Div('GDP FORECASTING', className='eyebrow'),
            html.H1('Indiana GDP Forecasts'),
            html.P('Compare quarterly Indiana GDP forecasts with the corresponding U.S. GDP path.'),
        ]),
        html.Section(className='panel', children=[
            html.H2('GDP forecasts'),
            html.P('Quarterly statewide forecasts for Indiana and the United States, measured in millions of dollars.',
                   className='subtle'),
            html.P('Published forecasts only; counterfactual scenarios are not yet available.', className='subtle'),
        ]),
        html.Section(className='panel', children=[
            html.H2('Quarterly GDP forecast'),
            dcc.Graph(id='gdp-chart', figure=gdp_figure(), config={'displaylogo': False}),
            html.Div(className='implied', children=gdp_table()),
        ]),
    ])


def gdp_figure():
    """Separate Indiana and U.S. panels; retain the original U.S. GDP path."""
    data = load_gdp_forecasts()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.16,
                        subplot_titles=("Indiana GDP forecast", "U.S. GDP path"))
    fig.add_trace(go.Scatter(x=data['Quarter'], y=data['Indiana'], mode='lines+markers',
                             name='Indiana forecast', line={'color': '#2563eb', 'width': 2.5},
                             connectgaps=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['Quarter'], y=data['US path'], mode='lines+markers',
                             name='U.S. path', line={'color': '#ea580c', 'width': 2.5},
                             connectgaps=False), row=2, col=1)
    fig.update_layout(template='plotly_white', height=700,
                      margin={'l': 85, 'r': 30, 't': 65, 'b': 55},
                      legend={'orientation': 'h', 'y': 1.13, 'x': 0}, hovermode='x unified')
    fig.update_yaxes(title_text='Indiana GDP (million $)', tickformat=',.0f', row=1, col=1)
    fig.update_yaxes(title_text='U.S. GDP (million $)', tickformat=',.0f', row=2, col=1)
    fig.update_xaxes(type='category')
    fig.update_xaxes(title_text='Forecast quarter', row=2, col=1)
    return fig


def gdp_table():
    data = load_gdp_forecasts()
    def fmt(value):
        return 'N/A' if pd.isna(value) else f'{float(value):,.2f}'
    return html.Div(className='population-table-scroll', children=[
        html.Table([
            html.Thead(html.Tr([
                html.Th('Quarter'), html.Th('Indiana GDP (million $)'),
                html.Th('U.S. GDP (million $)'),
            ])),
            html.Tbody([
                html.Tr([html.Td(row['Quarter']), html.Td(fmt(row['Indiana'])),
                         html.Td(fmt(row['US path']))])
                for _, row in data.iterrows()
            ]),
        ])
    ])
