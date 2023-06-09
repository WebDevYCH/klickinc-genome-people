import calendar
import datetime, re
from statistics import mean
import pandas as pd
from sklearn.metrics import mean_squared_error, r2_score

from flask import render_template, request
from flask_login import login_required

from core import *
from model import *
from forecasts_core import *

autobill_lookback = 4

# rough conversion for project overages, as reflected in RC/EAHR
# 1.15 as target based on 2020 experience
# RCHR/EAHR: 2023=1.326, 2022=1.204, 2021=1.445, 2020=1.123
mdou_pct = 1.15


###################################################################
## LABOR FORECASTS FRONTEND PAGES

# GET /p/forecasts/portfolio-forecasts
@app.route('/p/forecasts/portfolio-forecasts')
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

# GET /p/forecasts/portfolio-lr-forecasts
@app.route('/p/forecasts/portfolio-lr-forecasts')
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

# GET /p/forecasts/dept-lr-forecasts
@app.route('/p/forecasts/dept-lr-forecasts')
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
@app.route('/p/forecasts/portfolio-forecasts-data')
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

# GET /p/forecasts/portfolio-lr-forecasts-data
@app.route('/p/forecasts/portfolio-lr-forecasts-data')
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

    # TODO: incorporate requisitions

    retval = list(bypfid.values())
    retval.sort(key=lambda x: x['name'])

    return retval

# GET /p/forecasts/dept-lr-forecasts-data
@app.route('/p/forecasts/dept-lr-forecasts-data')
@login_required
def dept_lr_forecasts_data():
    year = int(request.args.get('year'))
    lrcat = request.args.get('lrcat')
    showportfolios = request.args.get('showportfolios') == 'true'
    showsources = request.args.get('showsources') == 'true'
    showfullyear = request.args.get('showyear') == 'true'
    showhours = request.args.get('showhours') == 'true'
    showlaborroles = request.args.get('showlaborroles') == 'true'

    # cache the results (sorting is slow)
    cachekey = f"dept_lr_forecasts_data_{year}_{lrcat}_{showportfolios}_{showsources}_{showfullyear}_{showhours}_{showlaborroles}"
    df = Cache.get(cachekey)
    if df is None:
        app.logger.info(f"dept_lr_forecasts_data cache miss, reloading")
        df = get_dlrfs(year, lrcat, showportfolios, showsources, showfullyear, showhours, showlaborroles)
        app.logger.info(f"dept_lr_forecasts_data size: {len(df)}")
        try:
            df.sort_values(by=['name'], inplace=True)
        except:
            app.logger.info(f"dept_lr_forecasts_data sort failed, leaving alone")
        app.logger.info(f"dept_lr_forecasts_data sorted size: {len(df)}")
        Cache.set(cachekey, df, timeout_seconds=300)

    retval = df.to_dict('records')
    # remove any null values for the parent column
    for r in retval:
        if r['parent'] == None or r['parent'] == "":
            r.pop('parent')

    return retval


# GET /p/forecasts/client-list
@app.route('/p/forecasts/client-list')
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

# GET /p/forecasts/cst-list
@app.route('/p/forecasts/cst-list')
@login_required
def pf_cst_list():
    year = int(request.args.get('year'))
    csts = db.session.query(Portfolio).\
        distinct(Portfolio.currbusinessunit).\
        join(PortfolioForecast).\
        filter(PortfolioForecast.yearmonth >= datetime.date(year,1,1)).\
        filter(PortfolioForecast.yearmonth < datetime.date(year+1,1,1)).\
        order_by(Portfolio.currbusinessunit).\
        all()

    retval = [{"id":c.currbusinessunit, "value":c.currbusinessunit } for c in csts]
    retval.sort(key=lambda x: x['value'])
    return retval

# GET /p/forecasts/lrcat-list
@app.route('/p/forecasts/lrcat-list')
@login_required
def pf_lrcat_list():
    year = int(request.args.get('year'))
    cachekey = f"pf_lrcat_list_{year}"
    lrcats = Cache.get(cachekey)
    if lrcats is None:
        app.logger.info(f"pf_lrcat_list cache miss, reloading")
        lrcats = db.session.query(LaborRole).\
            distinct(LaborRole.categoryname).\
            join(PortfolioLRForecast).\
            filter(PortfolioLRForecast.yearmonth >= datetime.date(year,1,1)).\
            filter(PortfolioLRForecast.yearmonth < datetime.date(year+1,1,1)).\
            order_by(LaborRole.categoryname).\
            all()
        Cache.set(cachekey, lrcats)

    return [{"id":c.categoryname, "value":c.categoryname } for c in lrcats]

###################################################################
## UTILITIES

# utility to add to a cell in a dict-dict, even if it's null
def addtocell(dict, id, col, val):
    if dict[id].get(col) == None:
        dict[id][col] = val
    else:
        dict[id][col] += val

def settocell(dict, id, col, val):
    dict[id][col] = val

def getfromcell(dict, id, col):
    return dict[id].get(col)

def queryClientCst(clients, csts):
    if csts != None and csts != "":
        queryfilter = Portfolio.currbusinessunit.in_(csts.split(','))
    elif clients != None and clients != "":
        queryfilter = Portfolio.clientid.in_(clients.split(','))
    else:
        queryfilter = True
    return queryfilter

def sourcename_from_source(source):
    sourcename = f"'{source}' Source"
    if source == 'actuals':
        sourcename = 'Actuals'
    elif source == 'linear':
        sourcename = 'Linear Forecast'
    elif source.startswith('linear'):
        sourcename = f'Linear Forecast ({source[6:]}m lookback)'
    elif source == 'cilinear':
        sourcename = 'Linear Forecast by CI Tags'
    elif source == 'linreg':
        sourcename = 'Linear Regression Forecast'
    elif source.startswith('linreg'):
        sourcename = f'Linear Regression Forecast ({source[6:]}m lookback)'
    elif source == 'gsheet':
        sourcename = 'Line of Sight Forecast'
    elif source == 'mljar':
        sourcename = 'AutoML Forecast'
    return sourcename

def monthly_hours_to_fte(hours, yearmonth, laborroleid, cst, source):
    if source == 'gsheet':
        if autobill_lookback > 0:
            # add hours to account for typical autobilling, by laborrole and cst over the last X months
            outercachekey = 'autobill_pct'
            autobill_pct = Cache.get(outercachekey)
            if autobill_pct is None:
                app.logger.info(f"autobill_pct cache miss, reloading")
                autobill_pct = {}
                startdate = datetime.date(yearmonth.year, yearmonth.month, 1) - relativedelta(autobill_lookback)
                for lrhc in db.session.query(LaborRoleHeadcount).filter(LaborRoleHeadcount.yearmonth >= startdate).all():
                    innercachekey = f"{lrhc.laborroleid}-{lrhc.cstname}"
                    innercachekey_autobill = f"{lrhc.laborroleid}-{lrhc.cstname}-autobill"
                    innercachekey_bill = f"{lrhc.laborroleid}-{lrhc.cstname}-bill"
                    # save hours billed and autobilled separate, and calculate percentage of autobilled/(billed-autobilled) on the fly
                    if lrhc.autobill_hours != None and lrhc.billed_hours != None:
                        if innercachekey_autobill not in autobill_pct: autobill_pct[innercachekey_autobill] = 0
                        if innercachekey_bill not in autobill_pct: autobill_pct[innercachekey_bill] = 0
                        autobill_pct[innercachekey_autobill] += lrhc.autobill_hours
                        autobill_pct[innercachekey_bill] += lrhc.billed_hours

                        # note divide by zero but move on from it (it happens when a role is purely autobill)
                        if autobill_pct[innercachekey_bill] - autobill_pct[innercachekey_autobill] != 0:
                            autobill_pct[innercachekey] = autobill_pct[innercachekey_autobill] / (autobill_pct[innercachekey_bill] - autobill_pct[innercachekey_autobill])
                        else:
                            app.logger.info(f"  autobill_pct divide by zero because role is purely autobill: {innercachekey}")
                            autobill_pct[innercachekey] = -0.1

                Cache.set(outercachekey, autobill_pct, timeout_seconds=3600*12)
            innercachekey = f"{laborroleid}-{cst}"
            # TODO: account for 99% autobill edge cases
            # rule: schedule assist can't account for more than 4% of that craft's hours
            # rule: total of schedule assist 
            if innercachekey in autobill_pct:
                if autobill_pct[innercachekey] < 0:
                    app.logger.info(f"  autobill_pct was negative due to role being pure autobill for {innercachekey} --> {hours}")
                elif autobill_pct[innercachekey] > 50:
                    app.logger.info(f"  autobill_pct was >50 for {innercachekey} --> {hours}")
                else:
                    #app.logger.info(f"  autobill_pct cache HIT for {innercachekey} --> {hours}*{1+autobill_pct[innercachekey]}")
                    hours *= 1 + autobill_pct[innercachekey]
            else:
                #app.logger.info(f"  autobill_pct cache miss for {innercachekey}")
                pass
        else:
            # no lookback, so just assume 6% autobilling
            hours *= 1.06

        # rough MDOU% adjustment based on target
        # TODO: gather portfolio-specific MDOU% targets and apply them here
        hours *= mdou_pct

        # simplistic model, as LoS forecasts are simplistic
        business_days = 249/12 # PM's are not accounting for shorter months in their forecasts
        business_hours_per_day = 7.26
        fte = hours / (business_days * business_hours_per_day)

        return fte
    elif source == 'mljar' or source.startswith('linreg') or source.startswith('linear'):
        # this is the only model that theoretically has an understanding of business days per month
        # and typical vacation time

        # calculate FTEs based on monthly hours, but do it twice and take the average
        # first time is based on the actual number of business days in the month, calibrated against typical vacation+sick time
        business_days = calendar.monthrange(yearmonth.year, yearmonth.month)[1]
        business_hours_per_day = 7.26
        # rough accounting for typical vacation and sick time
        if yearmonth.month == 5: business_hours_per_day /= 1.09
        elif yearmonth.month == 6: business_hours_per_day /= 1.12
        elif yearmonth.month == 7: business_hours_per_day /= 1.23
        elif yearmonth.month == 8: business_hours_per_day /= 1.16
        elif yearmonth.month == 9: business_hours_per_day /= 1.10
        else: business_hours_per_day /= 1.07
        fte = hours / (business_days * business_hours_per_day)

        return fte
    else:
        # simplistic models
        business_days = 249/12 # PM's are not accounting for shorter months in their forecasts
        business_hours_per_day = 7.26
        fte = hours / (business_days * business_hours_per_day)

        return fte


def clean_dictarray(dictarray):
    parentlookup = {}
    for d in dictarray:
        parentlookup[d['parent']] = True
    filtdictarray = []
    for d in dictarray:
        if f"{d['hc']}{d['m1']}{d['m2']}{d['m3']}{d['m4']}{d['m5']}{d['m6']}{d['m7']}{d['m8']}{d['m9']}{d['m10']}{d['m11']}{d['m12']}" != "" or d['id'] in parentlookup or d['detail'] == 'errorrates':
            filtdictarray.append(d)
    return filtdictarray


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
        if doforecasts:
            key = f"f{pf.portfolioid}"
            pfout = bypfid.get(key) or {}
            pfout['id'] = key
            pfout['parent'] = f"{pf.portfolioid}"
            pfout['name'] = "Forecast"
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
    # return from cache if possible
    cachekey = f"plrfs:{year}-{clients}-{csts}-{showsources}"
    bypfid = Cache.get(cachekey)
    if bypfid != None:
        return bypfid

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

    Cache.set(cachekey, bypfid)

    return bypfid

def fill_dr_nodes(rowdict, rowtemplate, lrcat, lr_or_jf, lr_or_jf_name, portfolioid, clientname, portfolioname, source, cstname):
    # Hierarchies:
    # lrcat -> lr/jf -> portfolio -> source
    ## lrcat -> lr/jf -> source sum
    # lrcat -> lr/jr -> fte
    # cst -> lr/jf -> portfolio -> source
    ## cst -> lr/jf -> source sum
    # cst -> lr/jf -> fte
    # errorrates -> source
    # also if sources are shown, display error rates

    keys = {}
    keys["lrcat"] = f"lcat"
    keys["lrcat_lrjf"] = f"lcat-{lrcat}-{lr_or_jf}"
    keys["lrcat_lrjf_source"] = f"lcat-{lrcat}-{lr_or_jf}-{source}"
    keys["lrcat_lrjf_portfolio"] = f"lcat-{lrcat}-{lr_or_jf}-{portfolioid}"
    keys["lrcat_lrjf_portfolio_source"] = f"lcat-{lrcat}-{lr_or_jf}-{portfolioid}-{source}"
    keys["lrcat_lfjr_fte"] = f"lcat-{lrcat}-{lr_or_jf}-fte"
    keys["cst_root"] = f"cst"
    keys["cst"] = f"cst{cstname}"
    keys["cst_lrjf"] = f"cst{cstname}-{lr_or_jf}"
    keys["cst_lrjf_source"] = f"cst{cstname}-{lr_or_jf}-{source}"
    keys["cst_lrjf_portfolio"] = f"cst{cstname}-{lr_or_jf}-{portfolioid}"
    keys["cst_lrjf_portfolio_source"] = f"cst{cstname}-{lr_or_jf}-{portfolioid}-{source}"
    keys["cst_lrjf_fte"] = f"cst{cstname}-{lr_or_jf}-fte"

    sourcename = None
    sourcetype = 'source'
    if source != None:
        sourcename = sourcename_from_source(source)
        if source == 'actuals':
            sourcetype = 'actuals'
        if source == 'gsheet':
            sourcetype = 'gsheet'

    fill_dr_node(rowdict, rowtemplate, keys["lrcat"], None, f"{lrcat}", 'lcat', None)
    fill_dr_node(rowdict, rowtemplate, keys["lrcat_lrjf"], keys["lrcat"], f"{lr_or_jf_name}", 'lrjf', None)
    if source != None and sourcename != None:
        fill_dr_node(rowdict, rowtemplate, keys["lrcat_lrjf_source"], keys["lrcat_lrjf"], f"{sourcename}", sourcetype, source)
    if clientname != None and portfolioname != None:
        fill_dr_node(rowdict, rowtemplate, keys["lrcat_lrjf_portfolio"], keys["lrcat_lrjf"], f"{clientname} - {portfolioname}", 'portfolio', None)
        if source != None and sourcename != None:
            fill_dr_node(rowdict, rowtemplate, keys["lrcat_lrjf_portfolio_source"], keys["lrcat_lrjf_portfolio"], f"{sourcename}", sourcetype, source)
    fill_dr_node(rowdict, rowtemplate, keys["lrcat_lfjr_fte"], keys["lrcat_lrjf"], f"FTE", 'fte', None)
    fill_dr_node(rowdict, rowtemplate, keys["cst_root"], None, f"CST's", 'cst', None)
    fill_dr_node(rowdict, rowtemplate, keys["cst"], keys["cst_root"], f"{cstname}", 'cst', None)
    fill_dr_node(rowdict, rowtemplate, keys["cst_lrjf"], keys["cst"], f"{lr_or_jf_name}", 'lrjf', None)
    if source != None and sourcename != None:
        fill_dr_node(rowdict, rowtemplate, keys["cst_lrjf_source"], keys["cst_lrjf"], f"{sourcename}", sourcetype, source)
    if clientname != None and portfolioname != None:
        fill_dr_node(rowdict, rowtemplate, keys["cst_lrjf_portfolio"], keys["cst_lrjf"], f"{clientname} - {portfolioname}", 'portfolio', None)
        if source != None and sourcename != None:
            fill_dr_node(rowdict, rowtemplate, keys["cst_lrjf_portfolio_source"], keys["cst_lrjf_portfolio"], f"{sourcename}", sourcetype, source)
    fill_dr_node(rowdict, rowtemplate, keys["cst_lrjf_fte"], keys["cst_lrjf"], f"FTE", 'fte', None)

    return keys

def fill_dr_node(rowdict, rowtemplate, nodekey, parentkey, name, detail, source):
    if nodekey not in rowdict:
        newrow = rowtemplate.copy()
        newrow['id'] = nodekey
        newrow['parent'] = parentkey
        newrow['name'] = name
        newrow['detail'] = detail
        newrow['source'] = source
        rowdict[newrow['id']] = newrow

# get the department labor role forecasts (in hours), returns a cached dataframe
def get_dlrfs(year, lrcat, showportfolios=True, showsources=True, showfullyear=True, showhours=False, showlaborroles=False):

    if showsources:
        showfullyear = True

    primarysource = 'gsheet'
    skipcsts = ['Brave Consulting']
    thisyear = datetime.date.today().year
    thismonth = datetime.date.today().month

    app.logger.info(f"get_dlrfs: {year} {lrcat} {showportfolios} {showsources} {showfullyear} {showhours} {showlaborroles}")

    # working with a dictionary of dictionaries
    columns = ['id','parent','name','detail','source','hc','fte','billedpct',
    'm1','m2','m3','m4','m5','m6','m7','m8','m9','m10','m11','m12']
    rowtemplate = dict.fromkeys(columns, None)

    # query the labor role forecasts
    pflrs = db.session.query(PortfolioLRForecast).join(Portfolio).join(LaborRole).filter(
            PortfolioLRForecast.yearmonth >= datetime.date(year,1,1),
            PortfolioLRForecast.yearmonth < datetime.date(year+1,1,1),
            LaborRole.categoryname == lrcat,
            PortfolioLRForecast.forecastedhours != None,
            ~PortfolioLRForecast.source.like('linear%'),
            ~PortfolioLRForecast.source.like('linreg%'),
        ).all()

    app.logger.info(f"  query done, rowcount: {len(pflrs)}")
    rowdict = {}
    sources = {}

    # ADD PREDICTED HOURS
    app.logger.info(f"  adding predicted hours")
    for pflr in pflrs:

        if pflr.portfolio.currbusinessunit in skipcsts:
            continue

        # skip rows with no forecasted hours
        if pflr.forecastedhours == None or pflr.forecastedhours == 0:
            continue

        # skip rows with source 'actuals' and it's this year and month
        if pflr.source == 'actuals' and pflr.yearmonth.year == thisyear and pflr.yearmonth.month == thismonth:
            continue

        # gather list of sources we found in this view
        sourcename = sourcename_from_source(pflr.source)
        sources[pflr.source] = sourcename

        if showlaborroles:
            lr_or_jf = pflr.labor_role.id
            lr_or_jf_name = pflr.labor_role.name
        else:
            lr_or_jf = pflr.labor_role.jobfunction
            lr_or_jf_name = pflr.labor_role.jobfunction

        keys = fill_dr_nodes(rowdict, rowtemplate, lrcat, lr_or_jf, lr_or_jf_name, pflr.portfolioid, pflr.portfolio.clientname, pflr.portfolio.name, pflr.source, pflr.portfolio.currbusinessunit)

        # fill in the month columns in the source row
        mkey = f"m{pflr.yearmonth.month}"
        if pflr.forecastedhours != None and pflr.forecastedhours != 0:
            fte = monthly_hours_to_fte(pflr.forecastedhours, pflr.yearmonth, pflr.laborroleid, pflr.portfolio.currbusinessunit, pflr.source)

            # possible override to hours
            if showhours:
                fte = pflr.forecastedhours

            # add fte/hours to the source row, and also any above them if this is the primary source
            if pflr.source == primarysource:
                addtocell(rowdict, keys["lrcat"], mkey, fte)
                addtocell(rowdict, keys["lrcat_lrjf"], mkey, fte)
                addtocell(rowdict, keys["lrcat_lrjf_portfolio"], mkey, fte)
                addtocell(rowdict, keys["cst"], mkey, fte)
                addtocell(rowdict, keys["cst_lrjf"], mkey, fte)
                addtocell(rowdict, keys["cst_lrjf_portfolio"], mkey, fte)

            addtocell(rowdict, keys["lrcat_lrjf_portfolio_source"], mkey, fte)
            addtocell(rowdict, keys["lrcat_lrjf_source"], mkey, fte)
            addtocell(rowdict, keys["cst_lrjf_portfolio_source"], mkey, fte)
            addtocell(rowdict, keys["cst_lrjf_source"], mkey, fte)

    # ADD FTE, HEADCOUNT, AND BILLED PCT
    app.logger.info(f"  adding fte, headcount, and billed pct data")
    lrhcs = db.session.query(LaborRoleHeadcount).join(LaborRole).filter(
            LaborRoleHeadcount.yearmonth >= datetime.date(year,1,1),
            LaborRoleHeadcount.yearmonth < datetime.date(year+1,1,1),
            LaborRole.categoryname == lrcat
        ).all()
    for lrhc in lrhcs:
        # we can't count the CST's that don't have forecasts in this system
        if lrhc.cstname in skipcsts:
            continue

        if showlaborroles:
            lr_or_jf = lrhc.labor_role.id
            lr_or_jf_name = lrhc.labor_role.name
        else:
            lr_or_jf = lrhc.labor_role.jobfunction
            lr_or_jf_name = lrhc.labor_role.jobfunction

        keys = fill_dr_nodes(rowdict, rowtemplate, lrcat, lr_or_jf, lr_or_jf_name, None, None, None, None, lrhc.cstname)

        # fill in the month column in the headcount rows
        mkey = f"m{lrhc.yearmonth.month}"
        addtocell(rowdict, keys["lrcat_lfjr_fte"], mkey, lrhc.billablealloc_eom)
        addtocell(rowdict, keys["cst_lrjf_fte"], mkey, lrhc.billablealloc_eom)

        for key in [keys["lrcat"], keys["lrcat_lrjf"], keys["cst"], keys["cst_lrjf"]]:
            # if it's this month, fill in the hc column in other rows
            if lrhc.yearmonth >= datetime.date(thisyear, thismonth, 1) and lrhc.yearmonth < datetime.date(thisyear,thismonth,1) + relativedelta(months=1):
                addtocell(rowdict, key, "hc", lrhc.headcount_eom)
                addtocell(rowdict, key, "fte", lrhc.billablealloc_eom)

            # if it's this month or the previous 2 months, save target and billable hours and calculate billed pct
            if lrhc.yearmonth >= datetime.date.today() - relativedelta(months=3):
                addtocell(rowdict, key, f"targethours", lrhc.target_hours)
                addtocell(rowdict, key, f"billedhours", lrhc.billed_hours)
                targethours = getfromcell(rowdict, key, "targethours")
                billedhours = getfromcell(rowdict, key, "billedhours")
                if targethours != None and targethours != 0:
                    billedpct = billedhours / targethours * 100
                    settocell(rowdict, key, "billedpct", billedpct)
                else:
                    settocell(rowdict, key, "billedpct", None)

    # ADD SOURCE ERROR RATES
    app.logger.info(f"  adding source error rates")
    # calculate the RMSE and R2 for each source in rowdict, and adds rows to the treegrid to display this
    if showsources:
        newrow = rowtemplate.copy()
        newrow['id'] = 'errorrates'
        newrow['parent'] = None
        newrow['name'] = 'Source error rates'
        newrow['source'] = 'errorrates'
        newrow['detail'] = 'errorrates'
        newrow['m1'] = 'R2*100'
        newrow['m2'] = 'EMSA/stddev*100'
        newrow['m3'] = 'EMSA*100'
        rowdict[newrow['id']] = newrow

        app.logger.info(f"    sources={sources}")

        # for each source that is visible in this dataset
        for source in sources.keys():
            if source == 'actuals':
                continue
            # gather each data point for that source, save its info in the predictionsdf, and also save the equivalent 'actuals' value
            predictionsdf = pd.DataFrame(columns=['predictionrowid','year','month','prediction','actual'])
            for row in rowdict.values():
                if row['source'] == source:
                    # find actuals by morphing the current key to an actuals key
                    actualskey = row['id'].replace(f"-{source}","-actuals")
                    if actualskey not in rowdict:
                        continue
                    #app.logger.info(f"    for source '{source}': row={row} and actualskey={actualskey}")
                    for m in range(1,13):
                        mkey = f"m{m}"
                        prediction = row[mkey]
                        actual = rowdict[actualskey][mkey]
                        if actual != None and prediction != None:
                            # append record to predictionsdf
                                predictionsdf = pd.concat([predictionsdf, pd.DataFrame({
                                    #'predictionrowid': [row['id']],
                                    #'year': [year],
                                    #'month': [m],
                                    'prediction': [prediction],
                                    'actual': [actual]
                                    })], ignore_index=True
                                )
        
            # now calculate the score
            if len(predictionsdf) == 0:
                app.logger.info(f"    for source '{source}': no data to score")
                continue
            try:
                rmsescore = mean_squared_error(predictionsdf['actual'], predictionsdf['prediction'], squared=False)
                r2score = r2_score(predictionsdf['actual'], predictionsdf['prediction'])
                stddev = np.std(predictionsdf['actual'])
                app.logger.info(f"    for source '{source}': RMSE={rmsescore} RMSE/stddev={rmsescore/stddev} R2={r2score}")
            except Exception as e:
                app.logger.info(f"    for source '{source}': ERROR calculating score: {e}")
                continue

            newrow = rowtemplate.copy()
            sourceid = f"errorrates-{source}"
            newrow['id'] = sourceid
            newrow['parent'] = 'errorrates'
            newrow['name'] = sourcename_from_source(source)
            newrow['source'] = 'errorrates'
            newrow['detail'] = 'errorrates'
            newrow['m1'] = r2score*100
            newrow['m2'] = rmsescore/stddev*100
            newrow['m3'] = rmsescore*100
            rowdict[newrow['id']] = newrow

            predictionsdf.to_csv(f"../logs/predictions_{year}_{lrcat}_{source}_r2_{r2score}.csv", index=False)

    # create dataframe based on rowdict
    app.logger.info(f"  creating dataframe")
    df = pd.DataFrame(rowdict.values(), columns=columns)

    # remove the portfolio and source rows if we don't want them
    if showportfolios and showsources:
        pass
    elif showportfolios and not showsources:
        df = df[df['detail'] != 'source']
        df = df[df['detail'] != 'errorrates']
    elif not showportfolios and showsources:
        df = df[df['detail'] != 'portfolio']
    else:
        df = df[df['detail'] != 'portfolio']
        df = df[df['detail'] != 'source']
        df = df[df['detail'] != 'errorrates']

    # also FTE rows if this is not the full year
    if not showfullyear:
        df = df[df['detail'] != 'fte']
        df = df[df['detail'] != 'actuals']

    # switch dataframe nulls to blank
    df = df.fillna('')

    # a little gross ... we want to remove records that have no data in any month and no child records
    # convert dataframe to array of dictionaries
    app.logger.info(f"  cleaning out empty rows")
    dictarray = df.to_dict('records')
    filtdictarray = clean_dictarray(dictarray)
    filtdictarray = clean_dictarray(filtdictarray)
    filtdictarray = clean_dictarray(filtdictarray)
    app.logger.info(f"  {len(dictarray) - len(filtdictarray)} rows removed")
    df = pd.DataFrame(filtdictarray, columns=columns)

    # optionally remove all months except current one and the next 3 months
    if not showfullyear and year == thisyear:
        app.logger.info(f"  removing months except {thismonth} and next 3")
        for m in range(1,13):
            if m < thismonth or m > thismonth + 3:
                df = df.drop(f"m{m}", axis=1)

    app.logger.info(f"  post-filter processing done")

    return df
