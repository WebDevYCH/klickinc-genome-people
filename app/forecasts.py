import datetime, json, os, re
from dateutil.relativedelta import relativedelta

from flask import render_template, request
from flask_login import login_required
from flask_admin import expose

from core import *
from model import *

from google.cloud import bigquery

###################################################################
## UTILITIES

# get the portfolio forecasts (in dollars), returns a dictionary
def get_pfs(year, clients, csts, doforecasts=True, doactuals=True, dotargets=True):
    if csts != None and csts != "":
        queryfilter = Portfolio.currcst.in_(csts.split(','))
    elif clients != None and clients != "":
        queryfilter = Portfolio.clientid.in_(clients.split(','))
    else:
        queryfilter = True

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
def get_plrfs(year, clients, csts, dosources=True):
    if csts != None and csts != "":
        queryfilter = Portfolio.currcst.in_(csts.split(','))
    elif clients != None and clients != "":
        queryfilter = Portfolio.clientid.in_(clients.split(','))
    else:
        queryfilter = True

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

        # add the labor role under the category, with the "main" forecast
        forecastkey = f"LR-(LRCAT{pflr.labor_role.categoryname})-{pflr.portfolioid}-{pflr.laborroleid}-MAIN"
        if pflr.forecastedhours != None:
            pfout = bypfid.get(forecastkey) or {}
            pfout['id'] = forecastkey
            pfout['parent'] = catkey
            pfout['name'] = pflr.labor_role.name
            pfout['lrname'] = pflr.labor_role.name
            pfout['source'] = 'MAIN'
            monthkey = f"m{pflr.yearmonth.month}"
            if pflr.source == 'MAIN' or monthkey not in pfout:
                # TODO: have some hierarchy of the sources
                pfout[f"m{pflr.yearmonth.month}"] = pflr.forecastedhours
                pfout[f"m{pflr.yearmonth.month}-source"] = pflr.source
            bypfid[forecastkey] = pfout

        # if this isn't the main source, add a line underneath that gives the source's forecast
        if dosources and pflr.source != 'MAIN':
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
def get_dlrfs(year, clients, csts, lrcat, dosources=True):
    # first get all portfolio labor role forecasts
    plrfs = get_plrfs(year, clients, csts, dosources=True)
    app.logger.info(f"get_dlrfs() plrfs data size: {len(plrfs)}")
    
    # then filter them by the labor role category and sum by labor role
    dlrfs = {}
    for key in plrfs:
        if key.startswith(f"LR-(LRCAT{lrcat})-"):
            # get the labor role id and source from the key
            lrid = key.split('-')[3]
            source = key.split('-')[4]

            # make sure there's a root level MAIN record for this labor role
            dlrmainkey = f"LR-{lrid}-SUMMARY"
            dlrout = dlrfs.get(dlrmainkey) or {}
            dlrout['id'] = dlrmainkey
            dlrout['name'] = plrfs[key]['lrname']
            # add the hours from each month, if this is the main source
            if source == 'MAIN':
                for month in range(1,13):
                    monthkey = f"m{month}"
                    if monthkey in plrfs[key]:
                        dlrout[monthkey] = dlrout.get(monthkey) or 0 + plrfs[key][monthkey]
            dlrfs[dlrmainkey] = dlrout

            # make sure there's a record for this labor role and source
            dlrkey = f"LR-{lrid}-{source}"
            dlrout = dlrfs.get(dlrkey) or {}
            dlrout['id'] = dlrkey
            dlrout['name'] = f"'{plrfs[key]['source']}' Forecast"
            dlrout['parent'] = dlrmainkey
            # add the hours from each month
            for month in range(1,13):
                monthkey = f"m{month}"
                if monthkey in plrfs[key]:
                    dlrout[monthkey] = dlrout.get(monthkey) or 0 + plrfs[key][monthkey]
            dlrfs[dlrkey] = dlrout

    # one more pass through dlrfs, to fill in SUMMARY records with one of the sources
    for key in dlrfs:
        if key.endswith('-SUMMARY'):
            for month in range(1,13):
                monthkey = f"m{month}"
                if monthkey not in dlrfs[key]:
                    for sourcekey in dlrfs:
                        if sourcekey.startswith(key+'-') and monthkey in dlrfs[sourcekey]:
                            dlrfs[key][monthkey] = dlrfs[sourcekey][monthkey]
                            dlrfs[key][monthkey+'-source'] = dlrfs[sourcekey]['name']
                            break

    # and one MORE pass through drlfs, to remove any sources that aren't SUMMARY if dosources is false
    if not dosources:
        for key in dlrfs:
            if not key.endswith('-SUMMARY'):
                del dlrfs[key]

    return dlrfs





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

    bypfid = get_pfs(year, clients, csts, doactuals=False, dotargets=False) | get_plrfs(year, clients, csts, dosources=True)
    app.logger.info(f"portfolio_lr_forecasts_data size: {len(bypfid)}")
    if len(bypfid) > 1000:
        bypfid = get_pfs(year, clients, csts, doactuals=False, dotargets=False) | get_plrfs(year, clients, csts, dosources=False)
        app.logger.info(f"portfolio_lr_forecasts_data minimized size: {len(bypfid)}")

    retval = list(bypfid.values())
    retval.sort(key=lambda x: x['name'])

    return retval

# GET /forecasts/dept-lr-forecasts-data
# note departments are also labor categories
@app.route('/forecasts/dept-lr-forecasts-data')
@login_required
def dept_lr_forecasts_data():
    year = int(request.args.get('year'))
    clients = request.args.get('clients')
    csts = request.args.get('csts')
    lrcat = request.args.get('lrcat')

    bylrid = get_dlrfs(year, clients, csts, lrcat, dosources=True)
    app.logger.info(f"dept_lr_forecasts_data size: {len(bylrid)}")
    if len(bylrid) > 1000:
        bylrid = get_dlrfs(year, clients, csts, lrcat, dosources=False)
        app.logger.info(f"dept_lr_forecasts_data minimized size: {len(bylrid)}")

    retval = list(bylrid.values())
    retval.sort(key=lambda x: x['name'])

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
    portfolioid = int(data['id'].split('-')[0])
    laborroleid = data['id'].split('-')[1]
    source = data['id'].split('-')[2]
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
        title='Labor Role Forecasts by Category', 
        startyear=startyear, endyear=endyear, thisyear=thisyear)



###################################################################
## ADMIN PAGES AND FORECASTING ALGORITHMS

class ForecastAdminView(AdminBaseView):
    @expose('/')
    def index(self):
        return self.render('admin/forecast.html')

    @expose('/linear')
    def linear(self):
        loglines = AdminLog()
        loglines.append("Starting Same-Portfolio Linear Extrapolator")
        loglines.append("")

        lookback = 10
        lookahead = 3
        sourcename = 'linear'
        startdate = datetime.date.today().replace(day=1)

        # for each portfolio with forecasts in the next lookahead months
        loglines.append("grabbing portfolio list")
        for p in db.session.query(PortfolioForecast).where(
                    PortfolioForecast.yearmonth >= startdate,
                    PortfolioForecast.forecast != None,
                    PortfolioForecast.forecast != "0.00"
                ).distinct(PortfolioForecast.portfolioid).all():
            loglines.append(f"portfolio {p.portfolioid}")
            # pick up the forecasts from the Genome report (hardcoded numbers come from the report config)
            json = retrieveGenomeReport(2145, [2434,2435,2436], [p.portfolioid,lookback,lookahead])
            loglines.append(f"{json}")

            if 'Entries' in json:
                # for each Genome forecast
                for pfin in json['Entries']:
                    # {'AccountPortfolioID': 174, 'YearMonth': '/Date(1669870800000-0500)/', 'Forecast': 54000.0, 'LaborCategory': 'Analytics', 'LaborRoleID': 'ANLTCADR', 'LaborRoleName': 'Analytics, Associate Director', 'PredictedHour': 0.14, 'PredictedAmount': 17.2267}
                    pfin['YearMonth'] = parseGenomeDate(pfin['YearMonth'])
                    key = f"{pfin['AccountPortfolioID']} // {pfin['YearMonth']} // {pfin['LaborRoleID']} // {sourcename}"

                    if pfin['PredictedHour'] != None:
                        pflr = db.session.query(PortfolioLRForecast).filter(
                            PortfolioLRForecast.portfolioid == pfin['AccountPortfolioID'],
                            PortfolioLRForecast.yearmonth == pfin['YearMonth'],
                            PortfolioLRForecast.laborroleid == pfin['LaborRoleID'],
                            PortfolioLRForecast.source == sourcename).first()

                        if pflr != None and pflr.forecastedhours == pfin['PredictedHour']:
                            loglines.append(f"  SKIPPED {key}")
                        else:
                            if pflr != None:
                                loglines.append(f"  UPDATING {key} because not: {pflr.forecastedhours} == {pfin['PredictedHour']} and {pflr.forecasteddollars} == {pfin['PredictedAmount']}")
                            else:
                                loglines.append(f"  NEW {key}")
                                pflr = PortfolioLRForecast()
                                db.session.add(pflr)

                            # set the fields
                            pflr.portfolioid = pfin['AccountPortfolioID']
                            pflr.yearmonth = pfin['YearMonth']
                            pflr.laborroleid = pfin['LaborRoleID']
                            pflr.source = sourcename
                            pflr.userid = None
                            pflr.updateddate = datetime.date.today()
                            pflr.forecasteddollars = pfin['PredictedAmount']
                            pflr.forecastedhours = pfin['PredictedHour']
            else:
                loglines.append("ERROR: CRASH RETRIEVING PORTFOLIO'S FORECASTS")

            db.session.commit()

        return self.render('admin/job_log.html', loglines=loglines)

    @expose('/cilinear')
    def cilinear(self):
        loglines = AdminLog()
        loglines.append("Starting CI-Selected-Portfolio Linear Extrapolator")
        loglines.append("")

        lookahead = 3
        sourcename = 'cilinear'
        startdate = datetime.date.today().replace(day=1)
        enddate = startdate + relativedelta(months=lookahead)

        # gather the labor rates
        loglines.append("gathering labor rates")
        rates = get_clrrates()

        loglines.append("querying Genome BQ model")
        # query the CI-selected portfolios view in BigQuery
        # query returns AccountPortfolioID, LaborRoleID, Pct, CST, Client
        client = bigquery.Client()
        query_job = client.query("SELECT * FROM `genome-datalake-prod.GenomeReports.vDemandPlanningByPortfolio`")
        results = query_job.result()
        # convert the results to a dictionary by portfolio ID with an array of labor role IDs and percentages 
        ciportfolios = {}
        for row in results:
            ciportfolios[row['AccountPortfolioID']] = ciportfolios.get(row['AccountPortfolioID']) or []
            ciportfolios[row['AccountPortfolioID']].append(row)

        # grab each future forecast
        loglines.append("grabbing portfolio forecast list")
        # for each future forecast
        for pf in db.session.query(PortfolioForecast).where(
                    PortfolioForecast.yearmonth >= startdate,
                    PortfolioForecast.yearmonth < enddate,
                ).join(Portfolio).all():
            loglines.append(f"portfolio {pf.portfolioid} forecast at {pf.yearmonth}, {pf.forecast}")

            # delete existing portfolio labor role forecasts
            db.session.query(PortfolioLRForecast).filter(
                PortfolioLRForecast.portfolioid == pf.portfolioid,
                PortfolioLRForecast.yearmonth == pf.yearmonth,
                PortfolioLRForecast.source == sourcename).delete()

            # if the portfolio is in the CI-selected portfolios and has a forecast
            if pf.portfolioid in ciportfolios and pf.forecast != None and pf.forecast != '$0.00':
                # convert forecast to a number
                pfforecast = float(pf.forecast.replace('$','').replace(',',''))
                # for each labor role in the model forecast
                for cipflr in ciportfolios[pf.portfolioid]:
                    # create a record with calculated hours in the portfolio labor role forecast
                    pflr = PortfolioLRForecast()
                    pflr.portfolioid = pf.portfolioid
                    pflr.yearmonth = pf.yearmonth
                    pflr.laborroleid = cipflr['LaborRoleID']
                    pflr.forecasteddollars = pfforecast * cipflr['Pct'] #/ 100
                    pflr.forecastedhours = pflr.forecasteddollars / rates[pf.portfolio.clientname][pflr.laborroleid]
                    pflr.source = sourcename
                    pflr.updateddate = datetime.date.today()
                    db.session.add(pflr)
                    loglines.append(f"  {pflr.laborroleid} {pflr.forecastedhours} hours")

            db.session.commit()

        return self.render('admin/job_log.html', loglines=loglines)

admin.add_view(ForecastAdminView(name='Forecast Processing', category='Forecasts'))














