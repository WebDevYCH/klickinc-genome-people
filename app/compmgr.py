
from flask_login import current_user

from core import *
from model import *

###################################################################
## MODEL

CompMgr = Base.classes.comp_mgr


###################################################################
## ADMIN

class CompMgrView(AdminModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('compmgr_admin')
    can_export = True
    export_types = ['csv', 'xlsx']
admin.add_view(CompMgrView(CompMgr, db.session, category='Comp Mgr'))


