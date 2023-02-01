import calendar
import datetime, re
from statistics import mean
import pandas as pd

from flask import render_template, request
from flask_login import login_required

from core import *
from model import *
from forecasts_core import *


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
    showfullyear = request.args.get('showyear') == 'true'
    showhours = request.args.get('showhours') == 'true'
    mult = float(request.args.get('mult'))

    # cache the results (sorting is slow)
    cachekey = f"dept_lr_forecasts_data_{year}_{clients}_{csts}_{lrcat}_{showportfolios}_{showsources}_{showfullyear}_{showhours}_{mult}"
    df = Cache.get(cachekey)
    if df is None:
        app.logger.info(f"dept_lr_forecasts_data cache miss, reloading")
        df = get_dlrfs(year, lrcat, clients, csts, showportfolios, showsources, showfullyear, showhours, mult)
        app.logger.info(f"dept_lr_forecasts_data size: {len(df)}")
        df.sort_values(by=['name'], inplace=True)
        app.logger.info(f"dept_lr_forecasts_data sorted size: {len(df)}")
        Cache.set(cachekey, df, timeout_seconds=300)

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
        distinct(Portfolio.currbusinessunit).\
        join(PortfolioForecast).\
        filter(PortfolioForecast.yearmonth >= datetime.date(year,1,1)).\
        filter(PortfolioForecast.yearmonth < datetime.date(year+1,1,1)).\
        order_by(Portfolio.currbusinessunit).\
        all()

    retval = [{"id":c.currbusinessunit, "value":c.currbusinessunit } for c in csts]
    retval.sort(key=lambda x: x['value'])
    app.logger.info(f"pf_cst_list size: {len(retval)} {retval}")
    return retval

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

def monthly_hours_to_fte(hours, yearmonth, laborroleid, cst, source, mult=1.22):

    if source == 'gsheet':
        # add rough 6% for autobilling
        # TODO: account for per-laborrole and portfolio autobilling
        hours *= 1.06

        # add rough 20% for project overages, as reflected in RC/EAHR
        # TODO: make this more dynamic somehow
        # 1.14 as target based on 2020 experience
        # 1.22 or so in 2023, but we have to get it down fast
        hours *= mult

        # simplistic model, as PM forecasts are simplistic
        business_days = 249/12 # PM's are not accounting for shorter months in their forecasts
        business_hours_per_day = 7.26
        fte = hours / (business_days * business_hours_per_day)

        return fte
    else:
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


def clean_dictarray(dictarray):
    parentlookup = {}
    for d in dictarray:
        parentlookup[d['parent']] = True
    filtdictarray = []
    for d in dictarray:
        if f"{d['hc']}{d['m1']}{d['m2']}{d['m3']}{d['m4']}{d['m5']}{d['m6']}{d['m7']}{d['m8']}{d['m9']}{d['m10']}{d['m11']}{d['m12']}" != "" or d['id'] in parentlookup:
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

# get the department labor role forecasts (in hours), returns a cached dataframe
def get_dlrfs(year, lrcat, clients = None, csts = None, showportfolios=True, showsources=True, showfullyear=True, showhours=False, mult=1.22):

    queryfilter = queryClientCst(clients, csts)

    primarysource = 'gsheet'
    thisyear = datetime.date.today().year
    thismonth = datetime.date.today().month

    app.logger.info(f"get_dlrfs: {year} {lrcat} {clients} {csts} {showportfolios} {showsources} {showfullyear} {showhours}")

    # working with a dictionary of dictionaries
    columns = ['id','parent','name','detail','source','hc',
    'm1','m2','m3','m4','m5','m6','m7','m8','m9','m10','m11','m12','ba','billedpct']
    rowtemplate = dict.fromkeys(columns, None)

    # query the labor role forecasts
    pflrs = db.session.query(PortfolioLRForecast).join(Portfolio).join(LaborRole).filter(
            PortfolioLRForecast.yearmonth >= datetime.date(year,1,1),
            PortfolioLRForecast.yearmonth < datetime.date(year+1,1,1),
            LaborRole.categoryname == lrcat,
            PortfolioLRForecast.forecastedhours != None,
            queryfilter
        ).all()

    app.logger.info(f"  query done, rowcount: {len(pflrs)}")
    rowdict = {}

    # add the rows to the dataframe
    app.logger.info(f"  adding rows to dict")
    for pflr in pflrs:

        if pflr.forecastedhours == None or pflr.forecastedhours == 0:
            continue

        # we want four hierarchies:
        # A: labor role -> portfolio -> source
        # B: labor role -> source sum
        # C: lrcat -> portfolio -> source
        # D: lrcat -> source sum
        sourcename = f"'{pflr.source}' Source",
        if pflr.source == 'actuals':
            sourcename = 'Actuals'
        elif pflr.source == 'linear':
            sourcename = 'Linear Forecast'
        elif pflr.source == 'cilinear':
            sourcename = 'Linear Forecast by CI Tags'
        elif pflr.source == 'linreg':
            sourcename = 'Linear Regression Forecast'
        elif pflr.source == 'gsheet':
            sourcename = 'PM Line of Sight Forecast'
        elif pflr.source == 'mljar':
            sourcename = 'AutoML Forecast'

        # A: labor role as a root node, if it isn't already there
        lrmainkey = f"{pflr.laborroleid}"
        if lrmainkey not in rowdict:
            newrow = rowtemplate.copy()
            newrow['id'] = lrmainkey
            newrow['parent'] = None
            newrow['name'] = pflr.labor_role.name
            rowdict[lrmainkey] = newrow
        
        # A: sum of the forecasted hours for the labor role by portfolio
        lrportfoliokey = f"{pflr.portfolioid}-{pflr.laborroleid}"
        if lrportfoliokey not in rowdict:
            newrow = rowtemplate.copy()
            newrow['id'] = lrportfoliokey
            newrow['parent'] = lrmainkey
            newrow['name'] = f"{pflr.portfolio.clientname} - {pflr.portfolio.name}"
            newrow['detail'] = 'portfolio'
            rowdict[lrportfoliokey] = newrow

        # A: sum of the forecasted hours for the labor role by portfolio and source
        lrsourcekey = f"{pflr.portfolioid}-{pflr.laborroleid}-{pflr.source}"
        if lrsourcekey not in rowdict:
            newrow = rowtemplate.copy()
            newrow['id'] = lrsourcekey
            newrow['parent'] = lrportfoliokey
            newrow['name'] = sourcename
            newrow['source'] = pflr.source
            newrow['detail'] = 'source'
            rowdict[lrsourcekey] = newrow

        # B: sum of the forecasted hours for the labor role by source
        lrsourcesumkey = f"{pflr.laborroleid}-{pflr.source}"
        if lrsourcesumkey not in rowdict:
            newrow = rowtemplate.copy()
            newrow['id'] = lrsourcesumkey
            newrow['parent'] = lrmainkey
            newrow['name'] = sourcename
            newrow['source'] = pflr.source
            newrow['detail'] = 'sourcesum'
            rowdict[lrsourcesumkey] = newrow

        # C: sum of the forecasted hours for the labor cat
        lcatmainkey = f"lcat"
        if lcatmainkey not in rowdict:
            newrow = rowtemplate.copy()
            newrow['id'] = lcatmainkey
            newrow['parent'] = None
            newrow['name'] = f" {lrcat} Labor Category"
            newrow['detail'] = 'lcat'
            rowdict[lcatmainkey] = newrow

        # C: sum of the forecasted hours for the labor cat by portfolio
        lcatportfoliokey = f"{pflr.portfolioid}-lcat"
        if lcatportfoliokey not in rowdict:
            newrow = rowtemplate.copy()
            newrow['id'] = lcatportfoliokey
            newrow['parent'] = lcatmainkey
            newrow['name'] = f"{pflr.portfolio.clientname} - {pflr.portfolio.name}"
            newrow['detail'] = 'portfolio'
            rowdict[lcatportfoliokey] = newrow

        # C: sum of the forecasted hours for the labor cat by portfolio and source
        lcatsourcekey = f"{pflr.portfolioid}-lcat-{pflr.source}"
        if lcatsourcekey not in rowdict:
            newrow = rowtemplate.copy()
            newrow['id'] = lcatsourcekey
            newrow['parent'] = lcatportfoliokey
            newrow['name'] = sourcename
            newrow['source'] = pflr.source
            newrow['detail'] = 'source'
            rowdict[lcatsourcekey] = newrow

        # D: sum of the forecasted hours for the labor cat by source
        lcatsourcesumkey = f"lcat-{pflr.source}"
        if lcatsourcesumkey not in rowdict:
            newrow = rowtemplate.copy()
            newrow['id'] = lcatsourcesumkey
            newrow['parent'] = lcatmainkey
            newrow['name'] = sourcename
            newrow['source'] = pflr.source
            newrow['detail'] = 'sourcesum'
            rowdict[lcatsourcesumkey] = newrow

        # fill in the month columns in the source row
        mkey = f"m{pflr.yearmonth.month}"
        if pflr.forecastedhours != None and pflr.forecastedhours != 0:
            fte = monthly_hours_to_fte(pflr.forecastedhours, pflr.yearmonth, pflr.laborroleid, pflr.portfolio.currbusinessunit, pflr.source, mult)

            # possible override to hours
            if showhours:
                fte = pflr.forecastedhours

            rowdict[lrsourcekey][mkey] = fte
            addtocell(rowdict, lrsourcesumkey, mkey, fte)
            addtocell(rowdict, lcatsourcesumkey, mkey, fte)

            # also add to the portfolio and labor role sum rows if this is the primary source
            if pflr.source == primarysource:
                addtocell(rowdict, lrportfoliokey, mkey, fte)
                addtocell(rowdict, lrmainkey, mkey, fte)
                addtocell(rowdict, lcatportfoliokey, mkey, fte)
                addtocell(rowdict, lcatmainkey, mkey, fte)

    # calculate the RMSE and R2 for each source
    # TODO

    app.logger.info(f"  df processing done")

    # add billable allocm, headcount and billed pct data
    if csts != None and csts != "":
        queryfilter = LaborRoleHeadcount.cstname.in_(csts.split(','))
    else:
        queryfilter = True

    lrhcs = db.session.query(LaborRoleHeadcount).join(LaborRole).filter(
            LaborRoleHeadcount.yearmonth >= datetime.date(year,1,1),
            LaborRoleHeadcount.yearmonth < datetime.date(year+1,1,1),
            LaborRole.categoryname == lrcat,
            queryfilter
        ).all()

    for lrhc in lrhcs:
        # labor role as a root node, in case it isn't already there
        lrmainkey = f"{lrhc.laborroleid}"
        if lrmainkey not in rowdict:
            newrow = rowtemplate.copy()
            newrow['id'] = lrmainkey
            newrow['parent'] = None
            newrow['name'] = lrhc.labor_role.name
            rowdict[lrmainkey] = newrow
        
        # BA for the labor role
        lrbakey = f"{lrhc.laborroleid}-ba"
        if lrbakey not in rowdict:
            newrow = rowtemplate.copy()
            newrow['id'] = lrbakey
            newrow['parent'] = lrmainkey
            newrow['name'] = f" Billable Alloc EOM"
            newrow['source'] = 'headcount'
            newrow['detail'] = 'headcount'
            rowdict[lrbakey] = newrow

        # BA for the labor cat
        lcatmainkey = f"lcat"
        lcatbakey = f"lcat-ba"
        if lcatbakey not in rowdict:
            newrow = rowtemplate.copy()
            newrow['id'] = lcatbakey
            newrow['parent'] = lcatmainkey
            newrow['name'] = f" Billable Alloc EOM"
            newrow['source'] = 'headcount'
            newrow['detail'] = 'headcount'
            rowdict[lcatbakey] = newrow

        # fill in the month column in the headcount row
        mkey = f"m{lrhc.yearmonth.month}"
        addtocell(rowdict, lrbakey, mkey, lrhc.billablealloc_eom)
        addtocell(rowdict, lcatbakey, mkey, lrhc.billablealloc_eom)

        # if it's this month, fill in the hc column
        if lrhc.yearmonth == datetime.date(thisyear, thismonth, 1):
            addtocell(rowdict, lrmainkey, "hc", lrhc.headcount_eom)
            addtocell(rowdict, lcatmainkey, "hc", lrhc.headcount_eom)
            addtocell(rowdict, lrmainkey, "ba", lrhc.billablealloc_eom)
            addtocell(rowdict, lcatmainkey, "ba", lrhc.billablealloc_eom)

        # if it's this month or the previous 2 months, save target and billable hours and calculate billed pct
        if lrhc.yearmonth >= datetime.date.today() - relativedelta(months=3):
            addtocell(rowdict, lrmainkey, f"targethours", lrhc.target_hours)
            addtocell(rowdict, lrmainkey, f"billedhours", lrhc.billed_hours)
            targethours = getfromcell(rowdict, lrmainkey, "targethours")
            billedhours = getfromcell(rowdict, lrmainkey, "billedhours")
            if targethours != None and targethours != 0:
                billedpct = billedhours / targethours * 100
                settocell(rowdict, lrmainkey, "billedpct", billedpct)
            else:
                settocell(rowdict, lrmainkey, "billedpct", None)

    app.logger.info(f"  headcount processing done")

    # create dataframe based on rowdict
    app.logger.info(f"  creating dataframe")
    df = pd.DataFrame(rowdict.values(), columns=columns)

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

    # a little gross ... we want to remove records that have no data in any month and no child records
    # convert dataframe to array of dictionaries
    app.logger.info(f"  cleaning out empty rows")
    dictarray = df.to_dict('records')
    filtdictarray = clean_dictarray(dictarray)
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
