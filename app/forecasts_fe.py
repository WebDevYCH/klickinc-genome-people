import datetime, json, os, re
from dateutil.relativedelta import relativedelta
import pandas as pd

from flask import render_template, request
from flask_login import login_required
from flask_admin import expose

from core import *
from model import *
from forecasts_core import *

from google.cloud import bigquery
import openpyxl

###################################################################
## LABOR FORECASTS FRONTEND PAGES

# GET /forecasts/portfolio-forecasts
@app.route('/forecasts/portfolio-forecasts')
@login_required
def portfolio_forecasts():
    thisyear = datetime.date.today().year
    # if it's after October, show the next year's forecasts
    if datetime.date.today().month > 10:
        thisyear += 1

    startyear = thisyear-2
    endyear = thisyear+1
    return render_template('forecasts/portfolio-forecasts.html', 
        title='Portfolio Forecasts', 
        startyear=startyear, endyear=endyear, thisyear=thisyear)

# GET /forecasts/portfolio-lr-forecasts
@app.route('/forecasts/portfolio-lr-forecasts')
@login_required
def portfolio_lr_forecasts():
    thisyear = datetime.date.today().year
    # if it's after October, show the next year's forecasts
    if datetime.date.today().month > 10:
        thisyear += 1

    startyear = thisyear-2
    endyear = thisyear+1
    return render_template('forecasts/portfolio-lr-forecasts.html', 
        title='Labor Role Forecasts by Portfolio', 
        startyear=startyear, endyear=endyear, thisyear=thisyear)

# GET /forecasts/dept-lr-forecasts
@app.route('/forecasts/dept-lr-forecasts')
@login_required
def dept_lr_forecasts():
    thisyear = datetime.date.today().year
    # if it's after October, show the next year's forecasts
    if datetime.date.today().month > 10:
        thisyear += 1

    startyear = thisyear-2
    endyear = thisyear+1
    return render_template('forecasts/dept-lr-forecasts.html', 
        title='Labor Role Forecasts', 
        startyear=startyear, endyear=endyear, thisyear=thisyear)

# GET /forecasts/portfolio-forecasts-data
@app.route('/forecasts/portfolio-forecasts-data')
@login_required
def portfolio_forecasts_data():
    year = int(request.args.get('year'))
    clients = request.args.get('clients')
    csts = request.args.get('csts')

    bypfid = get_pfs(year, clients, csts)
    app.logger.info(f"portfolio_forecasts_data size: {len(bypfid)}")

    retval = list(bypfid.values())
    retval.sort(key=lambda x: x['name'])
    return retval

# GET /forecasts/portfolio-lr-forecasts-data
@app.route('/forecasts/portfolio-lr-forecasts-data')
@login_required
def portfolio_forecasts_lr_data():
    year = int(request.args.get('year'))
    clients = request.args.get('clients')
    csts = request.args.get('csts')

    bypfid = get_pfs(year, clients, csts, doactuals=False, dotargets=False) | get_plrfs(year, clients, csts, showsources=True)
    app.logger.info(f"portfolio_lr_forecasts_data size: {len(bypfid)}")
    if len(bypfid) > 2000:
        bypfid = get_pfs(year, clients, csts, doactuals=False, dotargets=False) | get_plrfs(year, clients, csts, showsources=False)
        app.logger.info(f"portfolio_lr_forecasts_data minimized size: {len(bypfid)}")

    # TODO: incorporate headcount
    # TODO: incorporate requisitions

    retval = list(bypfid.values())
    retval.sort(key=lambda x: x['name'])

    return retval

# GET /forecasts/dept-lr-forecasts-data
@app.route('/forecasts/dept-lr-forecasts-data')
@login_required
def dept_lr_forecasts_data():
    year = int(request.args.get('year'))
    clients = request.args.get('clients')
    csts = request.args.get('csts')
    lrcat = request.args.get('lrcat')
    showportfolios = request.args.get('showportfolios') == 'true'
    showsources = request.args.get('showsources') == 'true'

    # cache the results for 5 minutes
    df = Cache.get(f"dept_lr_forecasts_data_{year}_{clients}_{csts}_{lrcat}_{showportfolios}_{showsources}")
    if df is None:
        df = get_dlrfs(year, lrcat, clients, csts, showportfolios, showsources)
        app.logger.info(f"dept_lr_forecasts_data size: {len(df)}")
        df.sort_values(by=['name'], inplace=True)
        app.logger.info(f"dept_lr_forecasts_data sorted size: {len(df)}")
        Cache.set(f"dept_lr_forecasts_data_{year}_{clients}_{csts}_{lrcat}_{showportfolios}_{showsources}", df, timeout=300)

    retval = df.to_dict('records')
    # remove any null values for the parent column
    for r in retval:
        if r['parent'] == None or r['parent'] == "":
            r.pop('parent')

    return retval


# GET /forecasts/client-list
@app.route('/forecasts/client-list')
@login_required
def pf_client_list():
    year = int(request.args.get('year'))
    clients = db.session.query(Portfolio).\
        distinct(Portfolio.clientid,Portfolio.clientname).\
        join(PortfolioForecast).\
        filter(PortfolioForecast.yearmonth >= datetime.date(year,1,1)).\
        filter(PortfolioForecast.yearmonth < datetime.date(year+1,1,1)).\
        order_by(Portfolio.clientname).\
        all()

    return [{"id":c.clientid, "value":c.clientname } for c in clients]

# GET /forecasts/cst-list
@app.route('/forecasts/cst-list')
@login_required
def pf_cst_list():
    year = int(request.args.get('year'))
    csts = db.session.query(Portfolio).\
        distinct(Portfolio.currcst).\
        join(PortfolioForecast).\
        filter(PortfolioForecast.yearmonth >= datetime.date(year,1,1)).\
        filter(PortfolioForecast.yearmonth < datetime.date(year+1,1,1)).\
        order_by(Portfolio.currcst).\
        all()

    return [{"id":c.currcst, "value":c.currcst } for c in csts]

# GET /forecasts/lrcat-list
@app.route('/forecasts/lrcat-list')
@login_required
def pf_lrcat_list():
    year = int(request.args.get('year'))
    lrcats = db.session.query(LaborRole).\
        distinct(LaborRole.categoryname).\
        join(PortfolioLRForecast).\
        filter(PortfolioLRForecast.yearmonth >= datetime.date(year,1,1)).\
        filter(PortfolioLRForecast.yearmonth < datetime.date(year+1,1,1)).\
        order_by(LaborRole.categoryname).\
        all()

    return [{"id":c.categoryname, "value":c.categoryname } for c in lrcats]

# POST /forecasts/portfolio-forecast-save
@app.post('/forecasts/portfolio-lr-forecast-save')
@login_required
def portfolio_lr_forecast_save():
    data = request.get_json()
    app.logger.info(f"portfolio_lr_forecast_save: {data}")
    # id is based on forecastkey = f"{pflr.portfolioid}-{pflr.laborroleid}-MAIN"
    portfolioid = int(data['id'].split('-')[1])
    laborroleid = data['id'].split('-')[2]
    source = data['id'].split('-')[3]
    if source != 'MAIN':
        return "ERROR: Only MAIN source is allowed"
    year = int(data['year'])
    month = int(data['month'])
    yearmonth = datetime.date(year, month, 1)

    pflr = db.session.query(PortfolioLRForecast).filter_by(portfolioid=portfolioid, laborroleid=laborroleid, yearmonth=yearmonth, source=source).first()
    if data['value'] == '':
        # blank value means they're removing the override (0 to override with 0 hours)
        if pflr:
            db.session.delete(pflr)
        db.session.commit()
        return "OK"
    else:
        # non-blank value means they're setting or changing the override
        if not pflr:
            pflr = PortfolioLRForecast(portfolioid=portfolioid, laborroleid=laborroleid, yearmonth=yearmonth, source='MAIN')
            db.session.add(pflr)
        pflr.forecastedhours = float(data['value'])
        pflr.updateddate = datetime.datetime.now()
        pflr.userid = current_user.userid
        db.session.commit()
    return "OK"


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
