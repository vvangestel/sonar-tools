#!/usr/local/bin/python3
'''

    Abstraction of the SonarQube "quality profile" concept

'''
import sys
import datetime
import re
import json
import pytz
import sonarqube.sqobject as sq
import sonarqube.env as env
import sonarqube.rules as rules
import sonarqube.utilities as util

class QualityProfile(sq.SqObject):

    def __init__(self, key, endpoint, data=None):
        super().__init__(key=key, env=endpoint)
        if data is not None:
            self.name = data['name']
            if 'lastUsed' in data:
                self.last_used = datetime.datetime.strptime(data['lastUsed'], '%Y-%m-%dT%H:%M:%S%z')
            else:
                self.last_used = None
            self.last_updated = datetime.datetime.strptime(data['rulesUpdatedAt'], '%Y-%m-%dT%H:%M:%S%z')
            self.language = data['language']
            self.language_name = data['languageName']
            self.is_default = data['isDefault']
            self.project_count = data.get('projectCount', None)
            self.is_built_in = data['isBuiltIn']
            self.nb_rules = int(data['activeRuleCount'])
            self.deprecated_rules = int(data['activeDeprecatedRuleCount'])
            self.is_inherited = data['isInherited']
            self.parent = data.get('parentKey', None)
            self.long_name = "{0} of language {1}".format(self.name, self.language_name)

    def get_permissions(self, perm_type):
        resp = env.get('permissions/{0}'.format(perm_type), ctxt=self.env,
                       params={'projectKey':self.key, 'ps':1})
        data = json.loads(resp.text)
        nb_perms = int(data['paging']['total'])
        nb_pages = (nb_perms+99) // 100
        perms = []
        for page in range(nb_pages):
            resp = env.get('permissions/{0}'.format(perm_type), ctxt=self.env,
                           params={'projectKey':self.key, 'ps':100, 'p':page+1})
            data = json.loads(resp.text)
            for p in data[perm_type]:
                perms.append(p)
        return perms

    def last_used_date(self):
        last_use = None
        return last_use

    def last_updated_date(self):
        last_use = None
        return last_use

    def number_associated_projects(self):
        return 0

    def age_of_last_use(self):
        today = datetime.datetime.today().replace(tzinfo=pytz.UTC)
        if self.last_used is None:
            return None
        return abs(today - self.last_used).days

    def age_of_last_update(self):
        today = datetime.datetime.today().replace(tzinfo=pytz.UTC)
        return abs(today - self.last_updated).days

    def audit(self):
        if self.is_built_in:
            return 0

        util.logger.info("Auditing quality profile %s (key %s)", self.long_name, self.key)
        issues = 0
        age = self.age_of_last_update()
        if age > 180:
            util.logger.warning('Quality profile %s has not been updated since %d days (more than %d days)',
                                self.long_name, age, 180)
            issues += 1
        if self.is_built_in:
            return issues
        rules_per_lang = rules.get_facet(facet='languages', endpoint=self.env)
        if self.nb_rules < int(rules_per_lang[self.language]*0.5):
            util.logger.warning('Quality profile %s has %d rules, this is too few, less than 50%% of all %d rules for language %s',
                                self.long_name, self.nb_rules, rules_per_lang[self.language], self.language)
            issues += 1
        age = self.age_of_last_use()
        if age is None or not self.is_default and self.project_count == 0:
            util.logger.warning('Quality profile %s is not used, it should be removed', self.long_name)
            issues += 1
        elif age > 180:
            util.logger.warning('Quality profile %s has not been used since %d days, it should be deleted',
                                self.long_name, age)
            issues += 1
        if self.deprecated_rules > 0:
            util.logger.warning('Quality profile %s has %d deprecated rules, they should be removed',
                                self.long_name, self.deprecated_rules)
            issues += 1


        return issues

def search(endpoint=None, params=None):
    resp = env.get('qualityprofiles/search', ctxt=endpoint, params=params)
    data = json.loads(resp.text)
    qp_list = []
    for qp in data['profiles']:
        qp_list.append(QualityProfile(qp['key'], endpoint=endpoint,data=qp))
    return qp_list

def audit(endpoint=None):
    issues = 0
    langs = {}
    for qp in search(endpoint):
        issues += qp.audit()
        langs[qp.language] = langs.get(qp.language, 0) + 1
    for lang in langs:
        if langs[lang] > 5:
            util.logger.warning("Language %s has %d quality profiles. This is more than the recommended 5 max",
                                lang, langs[lang])
    return issues