import datetime

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
import flask_admin

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField, RadioField, SelectMultipleField, TextAreaField, widgets

from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, delete, insert, update, or_, and_

from google.cloud import language_v1

from core import *
from model import *

###################################################################
## LABOR FORECASTS

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

@app.route('/forecasts/portfolio-forecasts-data')
@login_required
def portfolio_forecasts_data():
    year = int(request.args.get('year'))
    clients = request.args.get('clients')
    csts = request.args.get('csts')

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
        # portfolios with forecasts
        key = f"{pf.portfolioid}"
        pfout = bypfid.get(key) or {}
        pfout['id'] = f"{pf.portfolioid}"
        pfout['parent'] = pf.portfolio.clientid
        pfout['name'] = pf.portfolio.name
        pfout[f"m{pf.yearmonth.month}"] = pf.forecast
        bypfid[key] = pfout

        # clients (as parent nodes)
        key = pf.portfolio.clientname
        pfout = bypfid.get(key) or {}
        pfout['id'] = pf.portfolio.clientid
        pfout['name'] = pf.portfolio.clientname
        bypfid[key] = pfout

        # targets (as child nodes)
        key = f"t{pf.portfolioid}"
        pfout = bypfid.get(key) or {}
        pfout['id'] = f"t{pf.portfolioid}"
        pfout['parent'] = f"{pf.portfolioid}"
        pfout['name'] = "Targets"
        pfout[f"m{pf.yearmonth.month}"] = pf.target
        bypfid[key] = pfout

        # targets (as child nodes)
        key = f"a{pf.portfolioid}"
        pfout = bypfid.get(key) or {}
        pfout['id'] = f"a{pf.portfolioid}"
        pfout['parent'] = f"{pf.portfolioid}"
        pfout['name'] = "Actuals"
        pfout[f"m{pf.yearmonth.month}"] = pf.actuals
        bypfid[key] = pfout

    return list(bypfid.values())


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


