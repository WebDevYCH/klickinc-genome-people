from flask import json
import requests
import json
from flask_admin import expose

from core import *
from model import *
from skillutils import *


###################################################################
## MODEL

Base.classes.skill.__str__ = obj_name
Skill = Base.classes.skill

Base.classes.user_skill_source.__str__ = obj_name
UserSkillSource = Base.classes.user_skill_source

UserSkill = Base.classes.user_skill

Base.classes.title.__str__ = obj_name
Title = Base.classes.title

TitleSkill = Base.classes.title_skill

LaborRoleSkill = Base.classes.labor_role_skill

###################################################################
## ADMIN

admin.add_view(AdminModelView(LaborRoleSkill, db.session, category='Skill'))
admin.add_view(AdminModelView(TitleSkill, db.session, category='Skill'))
admin.add_view(AdminModelView(Skill, db.session, category='Skill'))

class SkillReplicationView(AdminBaseView):
    @expose('/')
    def index(self):
        return self.render('admin/skillrepl.html')

    @expose('/newskills')
    def newskills(self):
        loglines = AdminLog()
        loglines.append("Starting autofill New Skills Replication via LightCast API")
        skills = get_allskills_from_lightcast()
        loglines.append("Comparing with current skills table")
        for skill in skills['data']:
            current_skill =db.session.query(Skill).filter(Skill.name==skill['name']).first()
            if not current_skill:
                new_skill = Skill(name=skill['name'], is_klick=False, description=skill['description'])
                db.session.add(new_skill)
                loglines.append(f"Creating new skill {skill['name']}")
            else:
                loglines.append(f"Skipping existing skill {skill['name']}")
            db.session.commit()
        loglines.append("Finished autofilling new skills repliaction via LightCast API")
        return self.render('admin/job_log.html', loglines=loglines)
admin.add_view(SkillReplicationView(name='Autofill skills', category='Skill'))

