import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_admin.contrib.sqla import ModelView

db = SQLAlchemy()

# Models
class User(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.Unicode(64))
	email = db.Column(db.Unicode(64))
	active = db.Column(db.Boolean, default=True)
	created_at = db.Column(db.DateTime, default=datetime.datetime.now)

	def __unicode__(self):
		return self.name


class Page(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.Unicode(64))
	content = db.Column(db.UnicodeText)

	def __unicode__(self):
		return self.name


# Customized admin interface
class CustomView(ModelView):
	pass


class UserAdmin(CustomView):
	column_searchable_list = ('name',)
	column_filters = ('name', 'email')
	can_export = True
	export_types = ['csv', 'xlsx']


