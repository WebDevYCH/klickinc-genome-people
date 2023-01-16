# from sqlalchemy_serializer import SerializerMixin


import os
import pickle
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.automap import automap_base

from core import app, db

###################################################################
## MODEL

def obj_name(obj):
    return obj.name
def obj_title(obj):
    return obj.title
def obj_name_withid(obj):
    return f"{obj.name} [{obj.id}]"
def obj_name_user(obj):
    return f"{obj.firstname} {obj.lastname}"
def obj_name_portfolio(obj):
    return f"{obj.clientname} - {obj.name}"
def obj_name_joined(obj):
    return ['id', 'job_or_availadble', 'job_posting_category_id', 'poster_user_id', 'posted_date', 'expiry_date', 'removed_date', 'title', 'description', 'contact_user_id', 'name']

# Connect directly to database to make the schema, outside of the Flask context so we can
# initialize before the first web request
print("Initializing database model ")
dbengine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Session = sessionmaker(bind=dbengine)
dbsession = Session()

metadatacachefile = "../cache/dbmetadata.cache"
cached_metadata = None
if os.path.exists(metadatacachefile):
    print("Loading cached metadata")
    try:
        with open(metadatacachefile, 'rb') as cache_file:
            cached_metadata = pickle.load(file=cache_file)
    except IOError:
        # cache file not found - no problem, reflect as usual
        pass

if cached_metadata:
    Base = automap_base(bind=dbengine, metadata=cached_metadata)
    Base.prepare()
else:
    dbmetadata = MetaData()
    dbmetadata.reflect(dbengine)
    Base = automap_base(metadata=dbmetadata)
    Base.prepare()
    # save the metadata for future runs
    try:
        print("Saving metadata cache")
        # make sure to open in binary mode - we're writing bytes, not str
        with open(metadatacachefile, 'wb') as cache_file:
            pickle.dump(Base.metadata, cache_file)
    except:
        # couldn't write the file for some reason
        pass
print("<-- Done initializing database model ")

Base.classes.user.__str__ = obj_name_user
ModelUser = Base.classes.user
UserRole = Base.classes.user_role
Base.classes.role.__str__ = obj_name
Role = Base.classes.role
class User(ModelUser):
    def has_roles(self, rolename):
        for roles in db.session.query(Role).join(UserRole).\
            where(UserRole.user_id==self.userid,Role.name==rolename).all():
            return True
        return False
    def is_authenticated(self):
        return True
    def is_active(self):
        return self.enabled
    def is_anonymous(self):
        return False
    def get_id(self):
        return str(self.userid)

# some core Model concepts

UserProfile = Base.classes.user_profile

Base.classes.labor_role.__str__ = obj_name
LaborRole = Base.classes.labor_role

Base.classes.portfolio.__str__ = obj_name_portfolio
Portfolio = Base.classes.portfolio

LaborRoleHeadcount = Base.classes.labor_role_headcount
