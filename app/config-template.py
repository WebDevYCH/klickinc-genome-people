


def configapp(app):
	# Create dummy secrey key so we can use sessions
	app.config['SECRET_KEY'] = '123456790'
	app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'

	# Database
	app.config['DATABASE'] = 'genome-people-dev'
	app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://USER:PASS@IPADDRESS:5432/genome-people-dev'
	app.config['SQLALCHEMY_ECHO'] = False

	# OAuth
	app.config['GOOGLE_CLIENT_ID'] = "YOURCLIENTID.apps.googleusercontent.com"
	app.config['GOOGLE_CLIENT_SECRET'] = "YOURSECRET"
	app.config['GOOGLE_DISCOVERY_URL'] = "https://accounts.google.com/.well-known/openid-configuration"

	# Sentiment
	app.config['GOOGLE_SENTIMENT_APIKEY'] = "YOURKEY"


	return app


