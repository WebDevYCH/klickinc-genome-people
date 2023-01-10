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
