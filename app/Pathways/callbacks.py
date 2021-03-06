from Pathways.server import app, db, CONFIG
from Pathways.models import Aphis, Disp, City, Country
from Pathways.utils import Utils
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
import os
import json
from copy import deepcopy


risklevel_json = os.path.abspath(
    os.path.join(
        os.path.dirname('__file__'),
        'Pathways/RiskLevel.json'))
PEST_RISK_LEVEL = None
with open(risklevel_json, 'r') as f:
    PEST_RISK_LEVEL = json.load(f)

U = Utils()


@app.callback(Output('group-by-outputs', 'children'),
              [Input('db-column-dropdown', 'value')])
def group_by(column):
    # The value shows in chart. Less than this values consolidated into one
    # category.
    grater_than = 1
    # Condition - set the value by db columns.  Otherwise pie chart will be
    # busy to look at.
    if column == 'COMMODITY':
        grater_than = 3
    elif column == 'MON':
        grater_than = None
    # Args (db column, count/quantity/both, percentage=yes/no)
    df = U.query_group_by_one(column, 'both', 'yes')

    disp_group_name = CONFIG['DB_COLUMNS'][column]['name']
    # Get data for count and quantity
    count_pie_vals = U.consolidate_values(df, column, 'CountPer', grater_than)
    quantity_pie_vals = U.consolidate_values(
        df, column, 'QuantityPer', grater_than)
    # // Pie subplots //
    pie_one = U.pie_value_generator(
        column, 'CountPer', count_pie_vals, 'Count')
    pie_two = U.pie_value_generator(
        column,
        'QuantityPer',
        quantity_pie_vals,
        'Quantity')

    htmldiv = U.chart_count_quantity_subplots(
        pie_one, pie_two, df, f'Group by {disp_group_name}: Count and Quantity')

    return htmldiv


@app.callback(Output('country-dropdown', 'options'),
              [Input('count-or-quantity', 'value')])
def country_dropdown(count_quantity):
    # print('aggregate', aggregate)
    if count_quantity == 'count':
        df = U.query_group_by_one('ORIGIN_NM', 'count')
        ld_options = [{'label': f'{c["ORIGIN_NM"]} ({"{:,}".format(c["Count"])})', 'value': c["ORIGIN_NM"]}
                      for c in df.to_dict('rows')]
    elif count_quantity == 'quantity':
        df = U.query_group_by_one('ORIGIN_NM', 'quantity')
        ld_options = [{'label': f'{c["ORIGIN_NM"]} ({"{:,}".format(c["Quantity"])[:-2]})', 'value': c["ORIGIN_NM"]}
                      for c in df.to_dict('rows')]
    ld_options.insert(0, {'label': 'All', 'value': 'All'})

    return ld_options


@app.callback(Output('temporal-outputs', 'children'),
              [Input('disp-or-pest-found', 'value'),
               Input('yearmonth-or-month', 'value'),
               Input('count-or-quantity', 'value'),
               Input('country-dropdown', 'value'),
               Input('disp-group-dropdown', 'value'),
               ])
def temporal_line_chart(pest_found, date_group,
                        count_quantity, country, disp_group):
    # print('date_group', date_group, 'country', country)
    trace = []

    # Layout for line chart ---------------------------------
    disp_group_name = CONFIG['DISP_GROUP_DESC'][disp_group]['name']

    layout = {
        'title': '',
        'xaxis': dict(
            title='By Year and Month',
            showgrid=True,
            zeroline=False
        ),
        'yaxis': dict(
            title='Count',
            showgrid=True)
    }

    if date_group == 'month':
        layout['xaxis']['tickmode'] = 'linear'
        layout['xaxis']['title'] = 'By Month'
    else:
        layout['xaxis']['rangeslider'] = dict(visible=True)
        layout['xaxis']['type'] = 'date'

    if count_quantity == 'count':
        layout['yaxis']['title'] = 'Count'
        c_title = 'Shipments Count'

        if disp_group_name == 'All':
            if country == 'All':
                layout['title'] = f'{c_title} by All Disposition Code'
            else:
                layout['title'] = f'{c_title} from {country} by All Disposition Code'
        else:
            if country == 'All':
                layout['title'] = f'{c_title} by {disp_group_name}'
            else:
                layout['title'] = f'{c_title} from {country} by {disp_group_name}'

    elif count_quantity == 'quantity':
        layout['yaxis']['title'] = 'Quantity'
        q_title = 'Sum of Commodity Quantity'
        if disp_group_name == 'All':
            if country == 'All':
                layout['title'] = f'{q_title} by All Disposition Code'
            else:
                layout['title'] = f'{q_title} from {country} by All Disposition Code'
        else:
            if country == 'All':
                layout['title'] = f'{q_title} by {disp_group_name} and {date_group}'
            else:
                layout['title'] = f'{q_title} from {country} by {disp_group_name}'

    # --------------------------------------------------------

    if pest_found:
        return U.chart_pest_found_temporal(
            date_group, country, count_quantity, layout)

    else:
        df = U.data_disp_temporal(date_group, country, disp_group)

        if disp_group == 'All':
            for g in df['DISPGroup'].unique():
                subset = df[df.DISPGroup == g]
                x = [d for d in subset['Date']]
                y = [c for c in subset[count_quantity.capitalize()]]

                plot = go.Scatter(
                    x=x,
                    y=y,
                    name=CONFIG['DISP_GROUP_DESC'][g]['name'],
                    line=dict(
                        color=CONFIG['DISP_GROUP_DESC'][g]['color'],
                        dash=CONFIG['DISP_GROUP_DESC'][g]['dash']
                    )
                )
                trace.append(plot)
        else:
            x = [d for d in df['Date']]
            y = [c for c in df[count_quantity.capitalize()]]

            trace.append(go.Scatter(
                x=x,
                y=y,
                name=disp_group,
                line=dict(
                    color=CONFIG['DISP_GROUP_DESC'][disp_group]['color'],
                    dash=CONFIG['DISP_GROUP_DESC'][disp_group]['dash']
                )
            ))

        return html.Div([
            dcc.Graph(
                id='temporal-line',
                figure={
                    'data': trace,
                    'layout': layout
                }
            )
        ])


@app.callback(Output('section-title-country-output', 'children'),
              [Input('country-dropdown', 'value')])
def section_country_title(country):
    selected_country = country
    if selected_country != 'All':
        return html.H2(country)


@app.callback(Output('by-country-outputs', 'children'),
              [Input('disp-or-pest-found', 'value'),
               Input('count-or-quantity', 'value'),
               Input('country-dropdown', 'value'),
               Input('disp-group-dropdown', 'value')])
# Port and DISP code by country
def by_country_port_and_disp(pest_found, count_quantity, country, disp_group):
    # // Pest Found selected //
    if country != 'All':
        if pest_found:
            return U.chart_pest_found_by_country(country, count_quantity)

        # // DISP Code selected
        else:
            trace = []
            plot = go.Bar(orientation='h')
            layout = dict(
                barmode='stack',
                height=700,
                margin=dict(t=50),
                yaxis=dict(automargin=True),
                xaxis=dict(title=count_quantity.capitalize())
            )
            # Get data
            df = U.data_ports_by_country(country, disp_group)
            ports = df['PortCity'].unique()
            dispg = df['DISPGroup'].unique()
            busiest = U.data_busiest_port_by_country(country)

            # // Show all DISP code by port //
            if disp_group == 'All':

                for dg in dispg:
                    subset = df[df['DISPGroup'] == dg]
                    pval = dict.fromkeys(ports, 0)

                    if count_quantity == 'count':
                        layout[
                            'title'] = f'All Disposition Code Group by Port for Shipments Count from {country}'
                        for s in subset.to_dict('rows'):
                            pval[s['PortCity']] = s['Count']
                    elif count_quantity == 'quantity':
                        layout[
                            'title'] = f'All Disposition Code Group by Port for Sum of Commodity Quantity from {country}'
                        for s in subset.to_dict('rows'):
                            pval[s['PortCity']] = s['Quantity']

                    # Set stacked bar chart variables
                    plot = go.Bar(
                        y=[key for key, val in pval.items()],
                        x=[val for key, val in pval.items()],
                        name=CONFIG['DISP_GROUP_DESC'][dg]['name'],
                        orientation='h',
                        marker=dict(
                            color=CONFIG['DISP_GROUP_DESC'][dg]['color'])
                    )

                    trace.append(plot)
            # // Show selected DISP code by port //
            else:
                y = [p for p in df['PortCity']]
                disp_group_name = CONFIG['DISP_GROUP_DESC'][disp_group]['name']

                if count_quantity == 'count':
                    layout['title'] = f'{disp_group_name} by Port for Shipments Count from {country}'
                    x = [c for c in df['Count']]
                elif count_quantity == 'quantity':
                    layout['title'] = f'{disp_group_name} by Port for Sum of Commodity Quantity from {country}'
                    x = [q for q in df['Quantity']]
                # Set stacked bar chart variables
                plot = go.Bar(
                    y=y,
                    x=x,
                    orientation='h',
                    marker=dict(
                        color=CONFIG['DISP_GROUP_DESC'][disp_group]['color'])
                )

                trace.append(plot)

            htmldiv = [
                html.Div([
                    dcc.Graph(
                        id='ports-stack-bar',
                        figure={
                            'data': trace,
                            'layout': layout
                        }
                    )
                ], className='six columns'),

                html.Div([
                    dcc.Dropdown(
                        id='ports-dropdown',
                        options=[{'label': p, 'value': p} for p in ports],
                        value=busiest
                    ),
                    html.Div(id='pest-risk-high-low-outputs')
                ], className='six columns')
            ]

            return htmldiv


@app.callback(Output('pest-risk-high-low-outputs', 'children'),
              [Input('disp-or-pest-found', 'value'),
               Input('count-or-quantity', 'value'),
               Input('country-dropdown', 'value'),
               Input('disp-group-dropdown', 'value'),
               Input('ports-dropdown', 'value')])
def by_country_port_flowers_and_disp(
        pest_found, count_quantity, country, disp_group, port):
    trace_high = []
    trace_low = []
    title = count_quantity.capitalize()

    layout_high = dict(
        barmode='stack',
        title='',
        yaxis=dict(automargin=True),
        xaxis=dict(title=count_quantity.capitalize())
    )
    layout_low = deepcopy(layout_high)

    if count_quantity == 'count':
        layout_high[
            'title'] = f'Pest High-Risk Commodities Shipments Count by Disposition Code in {port} Port'
        layout_low[
            'title'] = f'Pest Low-Risk Commodities Shipments Count by Disposition Code in {port} Port'
    elif count_quantity == 'quantity':
        layout_high[
            'title'] = f'Pest High-Risk Commodities Sum of Quantity by Disposition Code in {port} Port'
        layout_low[
            'title'] = f'Pest Low-Risk Commodities Sum of Quantity by Disposition Code in {port} Port'

    if country != 'All':
        # Get flowers listed on Pest Risk Level json file
        risk_levels = U.data_pest_risk_level(PEST_RISK_LEVEL, country)
        # Get high risk flowers by port
        df_high = U.data_high_risk_flowers_by_country(
            country, port, disp_group, risk_levels['high'])
        # Get low risk flowers by port
        df_low = U.data_low_risk_flowers_by_country(
            country, port, disp_group, risk_levels['low'])

        if disp_group == 'All':
            # // Risk high barchart //
            trace_high = U.data_high_low_pest_risk_flowers(
                count_quantity, df_high, risk_levels['high'])
            # // Risk low barchart //
            trace_low = U.data_high_low_pest_risk_flowers(
                count_quantity, df_low, risk_levels['low'])

        else:
            disp_group_name = CONFIG['DISP_GROUP_DESC'][disp_group]['name']

            if count_quantity == 'count':
                layout_high[
                    'title'] = f'Pest High-Risk Commodities Shipments Count by {disp_group_name} in {port} Port'
                layout_low[
                    'title'] = f'Pest Low-Risk Commodities Shipments Count by {disp_group_name} in {port} Port'
            elif count_quantity == 'quantity':
                layout_high[
                    'title'] = f'Pest High-Risk Commodities Sum of Quantity by {disp_group_name} in {port} Port'
                layout_low[
                    'title'] = f'Pest Low-Risk Commodities Sum of Quantity by {disp_group_name} in {port} Port'
            trace_high = U.data_high_low_pest_risk_flowers_disp(
                title, df_high, disp_group)
            trace_low = U.data_high_low_pest_risk_flowers_disp(
                title, df_low, disp_group)

        # flowers = df['Flower'].unique()
        # print(f'Number of flowers: {len(flowers)}')

        return html.Div([

            dcc.Graph(
                id='risk-high-flowers',
                figure={
                    'data': trace_high,
                    'layout': layout_high
                }
            ),

            dcc.Graph(
                id='risk-low-flowers',
                figure={
                    'data': trace_low,
                    'layout': layout_low
                }
            )
        ])


@app.callback(Output('disp-group-dropdown', 'style'),
              [Input('disp-or-pest-found', 'value')])
def pest_found_switch(pest_found):
    if (pest_found):
        return {'display': 'none'}
