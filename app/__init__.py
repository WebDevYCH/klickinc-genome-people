from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import config

# Create application and db references
app = config.configapp(Flask(__name__))
db = SQLAlchemy(app)

