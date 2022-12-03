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
    portfolios = request.args.get('portfolios')
    pfs = db.session.query(PortfolioForecast).\
        join(Portfolio).\
        filter(PortfolioForecast.yearmonth >= datetime.date(year,1,1),\
            PortfolioForecast.yearmonth < datetime.date(year+1,1,1),\
            PortfolioForecast.portfolioid.in_(list(map(int, portfolios.split(','))))\
        ).\
        all()

    bypfid= {}
    for pf in pfs:
        pfout = bypfid.get(pf.portfolioid) or {}
        pfout['client'] = pf.portfolio.clientname
        pfout['portfolio'] = pf.portfolio.name
        pfout[f"m{pf.yearmonth.month}"] = pf.forecast
        bypfid[pf.portfolio.id] = pfout

    return list(bypfid.values())

@app.route('/forecasts/portfolio-data')
@login_required
def portfolio_data():
    thisyear = datetime.date.today().year
    startyear = thisyear-2
    endyear = thisyear+1
    portfolios = db.session.query(Portfolio).\
        join(PortfolioForecast).\
        filter(PortfolioForecast.yearmonth >= datetime.date(startyear,1,1)).\
        order_by(Portfolio.clientname,Portfolio.name).\
        all()
    return [{"id" : p.id, "value" : f"{p.clientname} - {p.name}"} for p in portfolios]


