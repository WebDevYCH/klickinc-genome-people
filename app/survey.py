import requests

from flask import render_template, redirect, url_for, request
from flask_login import login_required, current_user
from flask_admin import expose

from flask_wtf import FlaskForm

from sqlalchemy import delete, insert

# from google.cloud import language_v1

from core import *
from model import *

###################################################################
## MODEL

Base.classes.survey.__str__ = obj_name
Survey = Base.classes.survey

Base.classes.survey_question_type.__str__ = obj_name
SurveyQuestionType = Base.classes.survey_question_type

Base.classes.survey_question_category.__str__ = obj_name
SurveyQuestionCategory = Base.classes.survey_question_category

Base.classes.survey_question.__str__ = obj_name_survey_question
SurveyQuestion = Base.classes.survey_question

Base.classes.survey_answer.__str__ = obj_name_survey_answer
SurveyAnswer = Base.classes.survey_answer

SurveyAnswerAnalysis = Base.classes.survey_answer_analysis

SurveyToken = Base.classes.survey_token

###################################################################
## ADMIN

admin.add_view(AdminModelView(Survey, db.session, category='Survey'))

class SurveyQuestionModelView(AdminModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('survey_admin')
    column_searchable_list = ['name','question']
    column_filters = ['survey','survey_question_category']
    column_editable_list = ['name','question','survey','survey_question_category','survey_question_type']
    can_export = True
    export_types = ['csv', 'xlsx']
admin.add_view(SurveyQuestionModelView(SurveyQuestion, db.session, category='Survey'))
admin.add_view(AdminModelView(SurveyQuestionCategory, db.session, category='Survey'))
admin.add_view(ReadOnlyModelView(SurveyQuestionType, db.session, category='Survey'))

class SurveyAnswerModelView(ReadOnlyModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('survey_admin')
    column_filters = ['survey_question.survey','survey_question','user']
    can_export = True
    export_types = ['csv', 'xlsx']
admin.add_view(SurveyAnswerModelView(SurveyAnswer, db.session, category='Survey'))

class SurveyAnswerAnalysisModelView(ReadOnlyModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('survey_admin')
    column_filters = ['survey_answer.survey_question.survey','survey_answer.survey_question']
    can_export = True
    export_types = ['csv', 'xlsx']
admin.add_view(SurveyAnswerAnalysisModelView(SurveyAnswerAnalysis, db.session, category='Survey'))

###################################################################
## FRONTEND

@app.route('/survey', methods=['GET', 'POST'])
@login_required
def survey():
    """Route to the survey."""

    surveys = db.session.query(Survey).filter(Survey.enabled == True).all()

    return render_template('survey/index.html', title='Survey', surveys=surveys)

@app.route('/survey/<id>')
@login_required
def survey_detail(id):
    
    qlist = getQuestions()
    for q in qlist:
        exec(q)
    form = SurveyForm()
    query = db.session.query(SurveyQuestionCategory).join(SurveyQuestion).filter(SurveyQuestion.survey_id == int(id))
    categories = [row.name for row in query.all()]

    surveys = db.session.query(Survey).filter(Survey.enabled == True, Survey.id == id).all()

    return render_template('survey/question.html', title='Survey', form=form, surveys=surveys, categories=categories)

# route called by Ajax method
@app.route('/survey/save', methods=['POST'])
@login_required
def survey_save():
    # TODO: use surveyid
    userid=current_user.userid
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
    return redirect(url_for('survey'))

# utility functions
def getQuestions():
    '''Builds list of strs representing in DB defined questions as WTForm-elements.
    (This is some nice and hacky code generation while the program runs.)'''
    #qtypes = {}
    #for qtype in session.query(SurveyQuestionType).all():
    #    qtypes[qtype.id] = qtype.name

    questions = db.session.query(SurveyQuestion).order_by(SurveyQuestion.name).join(SurveyQuestion.survey_question_type).all()
    qslist = []
    for i, q in enumerate(questions):
        choices = generateChoices(q)
        qtype = q.survey_question_type.wtform_field
        # options in wtform are StringField, RadioField, SelectField, SelectMultipleField, MultiCheckboxField
        # options in db are single_line_text, multi_line_text, dropdown, multi_select, likert
        if qtype == "StringField":
            qslist.append(
                f'SurveyForm.q{(q.id):08} = {qtype}("{q.question}", description="{q.survey_question_category.name}")')
        if qtype == "TextAreaField":
            qslist.append(
                f'SurveyForm.q{(q.id):08} = {qtype}("{q.question}", description="{q.survey_question_category.name}")')
        elif qtype == "RadioField" or qtype == "SelectField":
            qslist.append(
                f'SurveyForm.q{(q.id):08} = {qtype}("{q.question}", choices={repr(choices)}, description="{q.survey_question_category.name}")')
        elif qtype == "SelectMultipleField" or qtype == "MultiCheckboxField":
            qslist.append(
                f'SurveyForm.q{(q.id):08} = {qtype}("{q.question}", choices={repr(choices)}, option_widget=widgets.CheckboxInput(), description="{q.survey_question_category.name}")')
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
# qslist = getQuestions()
class SurveyForm(FlaskForm):
    """The final survey form. Generated on the fly from questions in the DB.""" 
    pass
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
    # Makesure the API call.
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


class SurveyScoreView(AdminBaseView):
    @expose('/')
    def index(self):

        loglines = []

        answers = db.session.query(SurveyAnswer).\
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
                    loglines.append(f"text: {a.answer}")
                    sentiment = retrieveOverallSentiment(a.answer)
                    loglines.append(f"  score={sentiment['documentSentiment']['score']} magnitude={sentiment['documentSentiment']['magnitude']}")
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
                        loglines.append(f"entity: {e['name']} score={e['sentiment']['score']} magnitude={e['sentiment']['magnitude']}")
                        db.session.execute(
                            insert(SurveyAnswerAnalysis).
                            values(survey_answer_id=a.id,
                                topic=e['name'],
                                topic_salience=e['salience'],
                                sentiment_score=e['sentiment']['score'],
                                sentiment_magnitude=e['sentiment']['magnitude'])
                        )
                    loglines.append("")
                    db.session.commit()
        return self.render('admin/job_log.html', loglines=loglines)

admin.add_view(SurveyScoreView(name='Run Scoring', category='Survey'))

