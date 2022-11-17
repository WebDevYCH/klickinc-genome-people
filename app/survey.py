import datetime
import requests

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
import flask_admin
from flask_admin.contrib.sqla import ModelView

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField, RadioField, SelectMultipleField, TextAreaField, widgets

from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, delete, insert, update, or_, and_

from google.cloud import language_v1

from core import app, db, login_manager, admin
from model import Base, session, ReadOnlyModelView, \
    Survey, SurveyQuestion, SurveyAnswer, SurveyQuestionType, SurveyQuestionCategory, SurveyAnswerAnalysis

###################################################################
## SURVEY

# admin
admin.add_view(ModelView(Survey, db.session, category='Survey'))
class SurveyQuestionModelView(ModelView):
    column_searchable_list = ['name','question']
    column_filters = ['survey','survey_question_category']
    column_editable_list = ['name','question','survey','survey_question_category','survey_question_type']
    can_export = True
    export_types = ['csv', 'xlsx']
admin.add_view(SurveyQuestionModelView(SurveyQuestion, db.session, category='Survey'))
admin.add_view(ModelView(SurveyQuestionCategory, db.session, category='Survey'))
admin.add_view(ReadOnlyModelView(SurveyQuestionType, db.session, category='Survey'))
class SurveyAnswerModelView(ReadOnlyModelView):
    column_filters = ['survey_question.survey','survey_question','user']
    can_export = True
    export_types = ['csv', 'xlsx']
admin.add_view(SurveyAnswerModelView(SurveyAnswer, db.session, category='Survey'))
class SurveyAnswerAnalysisModelView(ReadOnlyModelView):
    column_filters = ['survey_answer.survey_question.survey','survey_answer.survey_question']
    can_export = True
    export_types = ['csv', 'xlsx']
admin.add_view(SurveyAnswerAnalysisModelView(SurveyAnswerAnalysis, db.session, category='Survey'))

# main frontend
@app.route('/survey', methods=['GET', 'POST'])
def survey():
    """Route to the survey."""
    form = SurveyForm()

    # TODO: use surveyid
    query = db.session.query(SurveyQuestionCategory)
    categories = [row.name for row in query.all()]

    surveys = db.session.query(Survey).filter(Survey.enabled == True).all()

    return render_template('survey/index.html', title='Survey', form=form, surveys=surveys, categories=categories)

# route called by Ajax method
@app.route('/survey/save', methods=['POST'])
def survey_save():
    # TODO: use surveyid
    userid=3446
    for k, v in request.form.items():
        if k.startswith('q'):
            qid = int(k[1:])
            db.session.execute(
                delete(SurveyAnswer).
                where(SurveyAnswer.survey_question_id==qid, SurveyAnswer.user_id==userid)
            )
            db.session.commit()
            db.session.execute(
                insert(SurveyAnswer).
                values(user_id=userid, survey_question_id=qid, answer=v)
            )
            db.session.commit()
    return jsonify({'status': 'ok'})

# utility functions
def getQuestions():
    '''Builds list of strs representing in DB defined questions as WTForm-elements.
    (This is some nice and hacky code generation while the program runs.)'''
    #qtypes = {}
    #for qtype in session.query(SurveyQuestionType).all():
    #    qtypes[qtype.id] = qtype.name

    questions = session.query(SurveyQuestion).order_by(SurveyQuestion.name).join(SurveyQuestion.survey_question_type).all()
    qslist = []
    for i, q in enumerate(questions):
        choices = generateChoices(q)
        qtype = q.survey_question_type.wtform_field
        # options in wtform are StringField, RadioField, SelectField, SelectMultipleField, MultiCheckboxField
        # options in db are single_line_text, multi_line_text, dropdown, multi_select, likert
        if qtype == "StringField":
            qslist.append(
                f'q{(q.id):08} = {qtype}("{q.question}", description="{q.survey_question_category.name}")')
        if qtype == "TextAreaField":
            qslist.append(
                f'q{(q.id):08} = {qtype}("{q.question}", description="{q.survey_question_category.name}")')
        elif qtype == "RadioField" or qtype == "SelectField":
            qslist.append(
                f'q{(q.id):08} = {qtype}("{q.question}", choices={repr(choices)}, description="{q.survey_question_category.name}")')
        elif qtype == "SelectMultipleField" or qtype == "MultiCheckboxField":
            qslist.append(
                f'q{(q.id):08} = {qtype}("{q.question}", choices={repr(choices)}, option_widget=widgets.CheckboxInput(), description="{q.survey_question_category.name}")')
    return qslist

def generateChoices(q):
    '''Generates list of tuples from answer choices to a given question.'''
    qname = q.survey_question_type.name
    if qname == 'Likert Scale':
        return [
            ('1','Strongly Disagree'),
            ('2','Disagree'),
            ('3','Neutral'),
            ('4','Agree'),
            ('5','Strongly Agree')
            ]
    elif qname == 'Likert Scale (10 options)':
        return [
            ('1','Strongly Disagree'),
            ('2','-'),
            ('3','-'),
            ('4','-'),
            ('5','-'),
            ('6','-'),
            ('7','-'),
            ('8','-'),
            ('9','-'),
            ('10','Strongly Agree')
            ]
    else :
        items = q.__dict__.items()
        l = [(k, v) for k, v in items if k.startswith(
            "ans") and v != '' and v != None]
        l.sort()
        return l

class SurveyForm(FlaskForm):
    """The final survey form. Generated on the fly from questions in the DB."""
    qslist = getQuestions()
    
    for qs in qslist:
        exec(qs)
    submit = SubmitField('Send')

# sentiment scoring
def retrieveEntitySentiment(line):
    apiKey = app.config['GOOGLE_SENTIMENT_APIKEY']
    apiEndpoint = 'https://language.googleapis.com/v1/documents:analyzeEntitySentiment?key=' + apiKey
    nlData = {
        'document': {
            'language': 'en-us',
            'type': 'PLAIN_TEXT',
            'content': line
        },
        'encodingType': 'UTF8'
    }
    # Makes the API call.
    response = requests.post(apiEndpoint, json=nlData)
    return response.json()

def retrieveOverallSentiment(line):
    apiKey = app.config['GOOGLE_SENTIMENT_APIKEY']
    apiEndpoint = 'https://language.googleapis.com/v1/documents:analyzeSentiment?key=' + apiKey
    # Creates a JSON request, with text string, language, type and encoding
    nlData = {
        'document': {
            'language': 'en-us',
            'type': 'PLAIN_TEXT',
            'content': line
        },
        'encodingType': 'UTF8'
    }
    # Makes the API call.
    response = requests.post(apiEndpoint, json=nlData)
    return response.json()

@app.route('/survey/score')
def score_answers():

    retstring = ""

    answers = session.query(SurveyAnswer).\
        join(SurveyQuestion).\
        join(SurveyQuestionType).\
        all()
    for a in answers:
        if a.survey_question.survey_question_type.wtform_field in ('StringField','TextAreaField'):
            db.session.execute(
                delete(SurveyAnswerAnalysis).
                where(SurveyAnswerAnalysis.survey_answer_id==a.id)
            )
            db.session.commit()

            if (a.answer and a.answer != ''):
                retstring += f"<br>text: {a.answer}<br>"
                sentiment = retrieveOverallSentiment(a.answer)
                retstring += f"  score={sentiment['documentSentiment']['score']} "
                retstring += f"  magnitude={sentiment['documentSentiment']['magnitude']}<br>"
                db.session.execute(
                    insert(SurveyAnswerAnalysis).
                    values(survey_answer_id=a.id, 
                        topic='OVERALL', 
                        topic_salience=1.0,
                        sentiment_score=sentiment['documentSentiment']['score'],
                        sentiment_magnitude=sentiment['documentSentiment']['magnitude'])
                )
                sentiment = retrieveEntitySentiment(a.answer)
                for e in sentiment['entities']:
                    retstring += f"entity: {e['name']} "
                    #retstring += f"entity: {e} "
                    retstring += f"  score={e['sentiment']['score']} "
                    retstring += f"  magnitude={e['sentiment']['magnitude']}"
                    retstring += "<br>\n"
                    db.session.execute(
                        insert(SurveyAnswerAnalysis).
                        values(survey_answer_id=a.id, 
                            topic=e['name'], 
                            topic_salience=e['salience'], 
                            sentiment_score=e['sentiment']['score'],
                            sentiment_magnitude=e['sentiment']['magnitude'])
                    )



            db.session.commit()

    return retstring


