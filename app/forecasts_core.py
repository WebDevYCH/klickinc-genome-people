import datetime, json, os, re
from dateutil.relativedelta import relativedelta
import pandas as pd

from flask import render_template, request
from flask_login import login_required
from flask_admin import expose

from core import *
from model import *

from google.cloud import bigquery
import openpyxl

###################################################################
## MODEL

PortfolioForecast = Base.classes.portfolio_forecast

PortfolioLRForecast = Base.classes.portfolio_laborrole_forecast

PortfolioLRForecastSheet = Base.classes.portfolio_laborrole_forecast_sheet

LaborRoleHoursDayRatio = Base.classes.labor_role_hours_day_ratio

class PortfolioLRForecastSheetView(AdminModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('admin')
    column_searchable_list = ['portfolio.name','gsheet_url','tabname']
    column_sortable_list = ['gsheet_url','tabname']
    #column_filters = ['survey','survey_question_category']
    #can_export = True
    #export_types = ['csv', 'xlsx']

admin.add_view(PortfolioLRForecastSheetView(PortfolioLRForecastSheet, db.session, category='Forecasts'))
admin.add_view(AdminModelView(LaborRoleHoursDayRatio, db.session, category='Forecasts'))

###################################################################
## UTILITIES

def queryClientCst(clients, csts):
    if csts != None and csts != "":
        queryfilter = Portfolio.currcst.in_(csts.split(','))
    elif clients != None and clients != "":
        queryfilter = Portfolio.clientid.in_(clients.split(','))
    else:
        queryfilter = True
    return queryfilter

# get the portfolio forecasts (in dollars), returns a dictionary
def get_pfs(year, clients, csts, doforecasts=True, doactuals=True, dotargets=True):
    queryfilter = queryClientCst(clients, csts)

    pfs = db.session.query(PortfolioForecast).\
        join(Portfolio).\
        filter(PortfolioForecast.yearmonth >= datetime.date(year,1,1),\
            PortfolioForecast.yearmonth < datetime.date(year+1,1,1),\
            queryfilter,\
        ).\
        all()

    bypfid= {}
    for pf in pfs:
        # clients (as parent nodes)
        key = f"{pf.portfolio.clientid}"
        pfout = bypfid.get(key) or {}
        pfout['id'] = key
        pfout['name'] = pf.portfolio.clientname
        bypfid[key] = pfout

        # portfolios with forecasts
        if doforecasts:
            key = f"{pf.portfolioid}"
            pfout = bypfid.get(key) or {}
            pfout['id'] = key
            pfout['parent'] = f"{pf.portfolio.clientid}"
            pfout['name'] = pf.portfolio.name
            if pf.forecast != None:
                pfout[f"m{pf.yearmonth.month}"] = re.sub('\\...$','',pf.forecast)
                bypfid[key] = pfout

        # targets (as child nodes)
        if dotargets:
            key = f"t{pf.portfolioid}"
            pfout = bypfid.get(key) or {}
            pfout['id'] = key
            pfout['parent'] = f"{pf.portfolioid}"
            pfout['name'] = "Target"
            if pf.target != None:
                pfout[f"m{pf.yearmonth.month}"] = re.sub('\\...$','',pf.target)
                bypfid[key] = pfout

        # actuals (as child nodes)
        if doactuals:
            key = f"a{pf.portfolioid}"
            pfout = bypfid.get(key) or {}
            pfout['id'] = key
            pfout['parent'] = f"{pf.portfolioid}"
            pfout['name'] = "Actuals"
            if pf.actuals != None:
                pfout[f"m{pf.yearmonth.month}"] = re.sub('\\...$','',pf.actuals)
                bypfid[key] = pfout
    return bypfid

# get the portfolio labor role forecasts (in hours), returns a dictionary
def get_plrfs(year, clients, csts, showsources=True):
    queryfilter = queryClientCst(clients, csts)

    pflrs = db.session.query(PortfolioLRForecast).\
        join(Portfolio).\
        join(LaborRole).\
        filter(PortfolioLRForecast.yearmonth >= datetime.date(year,1,1),
            PortfolioLRForecast.yearmonth < datetime.date(year+1,1,1),
            queryfilter
        ).all()

    bypfid = {}
    for pflr in pflrs:
        # add the labor category under the portfolio
        catkey = f"LRCAT-{pflr.portfolioid}-"+re.sub('[^a-zA-Z0-9]','_',pflr.labor_role.categoryname)
        pfout = bypfid.get(catkey) or {}
        pfout['id'] = catkey
        pfout['parent'] = f"{pflr.portfolioid}"
        pfout['name'] = pflr.labor_role.categoryname
        bypfid[catkey] = pfout

        # add the labor role under the category, with the "main" forecast or "linear", with main taking precedence
        forecastkey = f"LR-(LRCAT{pflr.labor_role.categoryname})-{pflr.portfolioid}-{pflr.laborroleid}-MAIN"
        if pflr.forecastedhours != None :
            pfout = bypfid.get(forecastkey) or {}
            pfout['id'] = forecastkey
            pfout['parent'] = catkey
            pfout['name'] = pflr.labor_role.name
            pfout['lrname'] = pflr.labor_role.name
            pfout['source'] = 'MAIN'
            monthkey = f"m{pflr.yearmonth.month}"
            if pflr.source == 'MAIN' or (monthkey not in pfout and pflr.source == 'linear'):
                # TODO: have some hierarchy of the sources
                pfout[f"m{pflr.yearmonth.month}"] = pflr.forecastedhours
                pfout[f"m{pflr.yearmonth.month}-source"] = pflr.source
            bypfid[forecastkey] = pfout

        # if this isn't the main source, add a line underneath that gives the source's forecast
        if showsources and pflr.source != 'MAIN':
            fsourcekey = f"LR-(LRCAT{pflr.labor_role.categoryname})-{pflr.portfolioid}-{pflr.laborroleid}-{pflr.source}"
            pfout = bypfid.get(fsourcekey) or {}
            pfout['id'] = fsourcekey
            pfout['parent'] = forecastkey
            pfout['name'] = f"'{pflr.source}' Forecast"
            pfout['lrname'] = pflr.labor_role.name
            pfout['source'] = pflr.source
            if pflr.forecastedhours != None:
                pfout[f"m{pflr.yearmonth.month}"] = pflr.forecastedhours
            bypfid[fsourcekey] = pfout

    return bypfid

# get the department labor role forecasts (in hours), returns a dictionary
def get_dlrfs(year, lrcat, clients = None, csts = None, showportfolios=True, showsources=True):
    queryfilter = queryClientCst(clients, csts)

    hoursperfte = 1680

    # create a pandas dataframe of the portfolio labor role forecasts
    header = ['id','parent','name','detail',
    'm1','m2','m3','m4','m5','m6','m7','m8','m9','m10','m11','m12',
    'm1src','m2src','m3src','m4src','m5src','m6src','m7src','m8src','m9src','m10src','m11src','m12src']
    df = pd.DataFrame(columns=header)

    # get the portfolio labor role forecasts, querying by lrcat and optionally by client or cst
    if csts != None and csts != "":
        queryfilter = Portfolio.currcst.in_(csts.split(','))
    elif clients != None and clients != "":
        queryfilter = Portfolio.clientid.in_(clients.split(','))
    else:
        queryfilter = True

    # query the labor role forecasts
    pflrs = db.session.query(PortfolioLRForecast).join(Portfolio).join(LaborRole).filter(
            PortfolioLRForecast.yearmonth >= datetime.date(year,1,1),
            PortfolioLRForecast.yearmonth < datetime.date(year+1,1,1),
            LaborRole.categoryname == lrcat,
            queryfilter
        ).all()

    # add the portfolio labor role forecasts to the dataframe
    for pflr in pflrs:
        # we want the hierarchy to be: labor role -> portfolio -> source

        # add a row for the labor role as a root node, if it isn't already there
        lrmainkey = f"{pflr.laborroleid}"
        if lrmainkey not in df.id.values:
            df = pd.concat([df, 
                pd.DataFrame({ 'id': lrmainkey,
                'parent': None,
                'name': pflr.labor_role.name }, index=[0])])
        
        # add a row for the sum of the forecasted hours for the labor role by portfolio
        lrportfoliokey = f"{pflr.portfolioid}-{pflr.laborroleid}"
        if lrportfoliokey not in df.id.values:
            df = pd.concat([df, 
                pd.DataFrame({ 'id': lrportfoliokey,
                'parent': lrmainkey,
                'name': f"{pflr.portfolio.clientname} - {pflr.portfolio.name} (hrs)",
                'detail': 'portfolio' }, index=[0])])

        # add a row for the sum of the forecasted hours for the labor role by portfolio and source
        lrsourcekey = f"{pflr.portfolioid}-{pflr.laborroleid}-{pflr.source}"
        if lrsourcekey not in df.id.values:
            df = pd.concat([df,
                pd.DataFrame({ 'id': lrsourcekey,
                'parent': lrportfoliokey,
                'name': f"'{pflr.source}' Source (hrs)",
                'detail': 'source' }, index=[0])])

        # fill in the month columns in the source row
        if pflr.forecastedhours != None and pflr.forecastedhours != 0:
            df.loc[df['id'] == lrsourcekey, f"m{pflr.yearmonth.month}"] = pflr.forecastedhours
            df.loc[df['id'] == lrsourcekey, f"m{pflr.yearmonth.month}src"] = pflr.source

    # second pass in the dataframe: fill in portfolio totals with only gsheet source data
    for prow in df[df['detail'] == 'portfolio'].itertuples():
        # get the sum of the source rows for this portfolio, only for gsheet source
        psum = df[(df['parent'] == prow.id) & (df['detail'] == 'source')].sum(axis=0, numeric_only=True)
        # fill in the portfolio row with the sum of the source rows
        df.loc[df['id'] == prow.id, 'm1':'m12'] = psum['m1':'m12']

    # third pass in the dataframe: fill in labor role category totals with only gsheet source data
    for lrow in df[df['detail'] == None].itertuples():
        # get the sum of the portfolio rows for this labor role
        lsum = df[(df['parent'] == lrow.id) & (df['detail'] == 'portfolio')].sum(axis=0, numeric_only=True)
        # fill in the labor role row with the sum of the portfolio rows
        df.loc[df['id'] == lrow.id, 'm1':'m12'] = lsum['m1':'m12']

    # remove the portfolio and source rows if we don't want them
    if not showportfolios:
        df = df[df['detail'] != 'portfolio']
    if not showsources:
        df = df[df['detail'] != 'source']

    # switch dataframe nulls to blank
    df = df.fillna('')

    return df

# get the current rate for each client per labor role (in dollars)
# returns a dictionary of dictionaries, client -> laborroleid -> rate
def get_clrrates():
    # query from Genome Reports
    #https://genome.klick.com/querytemplate/report-tool.html#/templateID/2093?nocache=true
    json = retrieveGenomeReport(2093)

    rates = {}
    for row in json['Entries']:
        clientrate = rates.get(row['Client']) or {}
        clientrate[row['LaborRoleID']] = row['PerHour']
        rates[row['Client']] = clientrate

    return rates
