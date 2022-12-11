import datetime
import re

from flask import render_template, request
from flask_login import login_required
from flask_admin import expose

from core import *
from model import *

###################################################################
## UTILITIES

# get the portfolio forecasts (in dollars), returns a dictionary
def get_pfs(year, clients, csts, doforecasts=True, doactuals=True, dotargets=True):
    if csts != None:
        queryfilter = Portfolio.currcst.in_(csts.split(','))
    else:
        queryfilter = Portfolio.clientid.in_(clients.split(','))

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
def get_plrfs(year, clients, csts):
    if csts != None:
        queryfilter = Portfolio.currcst.in_(csts.split(','))
    else:
        queryfilter = Portfolio.clientid.in_(clients.split(','))

    pflrs = db.session.query(PortfolioLRForecast).\
        join(Portfolio).\
        join(LaborRole).\
        filter(PortfolioLRForecast.yearmonth >= datetime.date(year,1,1),
            PortfolioLRForecast.yearmonth < datetime.date(year+1,1,1),
            queryfilter
        ).all()

    bypfid = {}
    for pflr in pflrs:
        # make sure the source is mentioned under the portfolio
        sourcekey = f"{pflr.portfolioid}-{pflr.source}"
        pfout = bypfid.get(sourcekey) or {}
        pfout['id'] = sourcekey
        pfout['parent'] = f"{pflr.portfolioid}"
        pfout['name'] = f"'{pflr.source}' Forecast"
        bypfid[sourcekey] = pfout

        # make sure the source is mentioned under the portfolio
        catkey = f"{pflr.portfolioid}-{pflr.source}-"+re.sub('[^a-zA-Z0-9]','_',pflr.labor_role.categoryname)
        pfout = bypfid.get(catkey) or {}
        pfout['id'] = catkey
        pfout['parent'] = sourcekey
        pfout['name'] = pflr.labor_role.categoryname
        bypfid[catkey] = pfout

        # now the labor role under the source
        forecastkey = f"{pflr.portfolioid}-{pflr.source}-{pflr.laborroleid}"
        pfout = bypfid.get(forecastkey) or {}
        pfout['id'] = forecastkey
        pfout['parent'] = catkey
        pfout['name'] = pflr.labor_role.name
        if pflr.forecastedhours != None:
            pfout[f"m{pflr.yearmonth.month}"] = pflr.forecastedhours
            bypfid[forecastkey] = pfout

    return bypfid





###################################################################
## LABOR FORECASTS FRONTEND PAGES

# GET /forecasts/portfolio-forecasts
@app.route('/forecasts/portfolio-forecasts')
@login_required
def portfolio_forecasts():
    thisyear = datetime.date.today().year
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
    startyear = thisyear-2
    endyear = thisyear+1
    return render_template('forecasts/portfolio-lr-forecasts.html', 
        title='Portfolio Labor Role Forecasts', 
        startyear=startyear, endyear=endyear, thisyear=thisyear)

# GET /forecasts/portfolio-forecasts-data
@app.route('/forecasts/portfolio-forecasts-data')
@login_required
def portfolio_forecasts_data():
    year = int(request.args.get('year'))
    clients = request.args.get('clients')
    csts = request.args.get('csts')

    bypfid = get_pfs(year, clients, csts)

    return list(bypfid.values())

# GET /forecasts/portfolio-lr-forecasts-data
@app.route('/forecasts/portfolio-lr-forecasts-data')
@login_required
def portfolio_forecasts_lr_data():
    year = int(request.args.get('year'))
    clients = request.args.get('clients')
    csts = request.args.get('csts')

    bypfid = get_pfs(year, clients, csts, doactuals=False, dotargets=False) | get_plrfs(year, clients, csts)
    app.logger.info(f"portfolio_forecasts_lr_data: {bypfid}")

    return list(bypfid.values())

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

###################################################################
## ADMIN PAGES AND FORECASTING ALGORITHMS

class ForecastAdminView(AdminBaseView):
    @expose('/')
    def index(self):
        return self.render('admin/forecast.html')

    @expose('/linear')
    def linear(self):
        loglines = AdminLog()
        loglines.append("Starting Same-Portfolio Linear Extractor")
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


admin.add_view(ForecastAdminView(name='Forecast Processing', category='Forecasts'))














