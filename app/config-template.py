


def configapp(app):
	# Create dummy secrey key so we can use sessions
	app.config['SECRET_KEY'] = '123456790'
	app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'

	# Database
	app.config['DATABASE'] = 'genome-people-dev'
	app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://USER:PASS@IPADDRESS:5432/genome-people-dev'
	app.config['SQLALCHEMY_ECHO'] = False

	return app


