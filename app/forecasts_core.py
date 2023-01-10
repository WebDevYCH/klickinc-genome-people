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

# utility to add to a cell in a dataframe, even if it's null
def addtocell(df, id, col, val):
    loc = df.loc[df['id'] == id, col]
    if pd.isnull(df.loc[df['id'] == id, col]).bool():
        df.loc[df['id'] == id, col] = val
    else:
        df.loc[df['id'] == id, col] += val

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
    primarysource = 'linear'

    # create a pandas dataframe of the portfolio labor role forecasts
    header = ['id','parent','name','detail','source','altid',
    'm1','m2','m3','m4','m5','m6','m7','m8','m9','m10','m11','m12']
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
        # but also labor role -> source sum

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
                'altid': f"{pflr.laborroleid}-{pflr.source}",
                'source': pflr.source,
                'detail': 'source' }, index=[0])])

        # add a row for the sum of the forecasted hours for the labor role by source
        lrsourcesumkey = f"{pflr.laborroleid}-{pflr.source}"
        if lrsourcesumkey not in df.id.values:
            df = pd.concat([df,
                pd.DataFrame({ 'id': lrsourcesumkey,
                'parent': lrmainkey,
                'name': f"'{pflr.source}' Source Sum (hrs)",
                'source': pflr.source,
                'detail': 'sourcesum' }, index=[0])])

        # fill in the month columns in the source row
        mkey = f"m{pflr.yearmonth.month}"
        if pflr.forecastedhours != None and pflr.forecastedhours != 0:
            df.loc[df['id'] == lrsourcekey, mkey] = pflr.forecastedhours
            addtocell(df, lrsourcesumkey, mkey, pflr.forecastedhours)

            # also add to the portfolio and labor role sum rows if this is the primary source
            if pflr.source == primarysource:
                addtocell(df, lrportfoliokey, mkey, pflr.forecastedhours)
                addtocell(df, lrmainkey, mkey, pflr.forecastedhours / hoursperfte)

    # remove the portfolio and source rows if we don't want them
    if showportfolios and showsources:
        pass
    elif showportfolios and not showsources:
        df = df[df['detail'] != 'source']
        df = df[df['detail'] != 'sourcesum']
    elif not showportfolios and showsources:
        df = df[df['detail'] != 'portfolio']
        df = df[df['detail'] != 'source']
    else:
        df = df[df['detail'] != 'portfolio']
        df = df[df['detail'] != 'source']
        df = df[df['detail'] != 'sourcesum']

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
