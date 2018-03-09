#!/usr/local/bin/python

# !/Library/Frameworks/Python.framework/Versions/3.6/bin/python3.6

import json
import requests
import sonarqube.env
import sonarqube.issues

# Mandatory script input parameters
global token
global project_key


global credentials
# global root_url
root_url = 'http://localhost:9000/'

global dry_run_mode
dry_run_mode = False

def search(project_key):
    params = dict(ps='10', componentKeys=project_key, additionalFields='_all')
    resp = requests.get(url=sonarqube.env.get_url() + '/api/issues/search', auth=sonarqube.env.get_credentials(), params=params)
    data = json.loads(resp.text)
    print("Number of issues:", data['paging']['total'])

    all_issues = data['issues']
    print(all_issues)



def print_change_log(issue_key):
    events_by_date = sort_changelog(get_changelog(issue_key))
    comments_by_date = sort_comments(get_comments(issue_key))
    for date in comments_by_date:
        events_by_date[date] = comments_by_date[date]

    for date in sorted(events_by_date):
        print(date, ':')
        print_object(events_by_date[date])


def apply_changelog(new_issue, closed_issue, do_it_really=True):
    global root_url
    global credentials
    events_by_date = sort_changelog(get_changelog(closed_issue))
    comments_by_date = sort_comments(get_comments(closed_issue))
    for date in comments_by_date:
        events_by_date[date] = comments_by_date[date]
    if do_it_really:
        print('   Not joking I am doing it')
    for date in sorted(events_by_date):
        # print_object(events_by_date[date])
        is_applicable_event = True

        if events_by_date[date][0] == 'log' and is_log_a_severity_change(events_by_date[date][1]):
            params = dict(issue=new_issue, severity=get_log_new_severity(events_by_date[date][1]))
            operation = 'Changing severity to: ' + params['severity']
            api = 'issues/set_severity'
        elif events_by_date[date][0] == 'log' and is_log_a_type_change(events_by_date[date][1]):
            params = dict(issue=new_issue, type=get_log_new_type(events_by_date[date][1]))
            operation = 'Changing type to: ' + params['type']
            api = 'issues/set_type'
        elif events_by_date[date][0] == 'log' and is_log_a_reopen(events_by_date[date][1]):
            params = dict(issue=new_issue, type='reopen')
            operation = 'Reopening issue'
            api = 'issues/do_transition'
        elif events_by_date[date][0] == 'log' and is_log_a_resolve_as_fp(events_by_date[date][1]):
            params = dict(issue=new_issue, transition='falsepositive')
            operation = 'Setting as False Positive'
            api = 'issues/do_transition'
        elif events_by_date[date][0] == 'log' and is_log_a_resolve_as_wf(events_by_date[date][1]):
            params = dict(issue=new_issue, transition='wontfix')
            operation = 'Setting as wontfix'
            api = 'issues/do_transition'
        elif events_by_date[date][0] == 'log' and is_log_an_assignee(events_by_date[date][1]):
            params = dict(issue=new_issue, assignee=get_log_assignee(events_by_date[date][1]))
            operation = 'Assigning issue to: ' + params['assignee']
            api = 'issues/assign'
        elif events_by_date[date][0] == 'log' and is_log_a_tag_change(events_by_date[date][1]):
            params = dict(key=new_issue, tags=get_log_new_tag(events_by_date[date][1]).replace(' ', ','))
            operation = 'Setting new tags to: ' + params['tags']
            api = 'issues/set_tags'
        elif events_by_date[date][0] == 'comment' and is_log_a_comment(events_by_date[date][1]):
            params = dict(issue=new_issue, text=events_by_date[date][1]['markdown'])
            operation = 'Adding comment: ' + params['text']
            api = 'issues/add_comment'
        else:
            is_applicable_event = False
            api = ''


        if is_applicable_event:
            if do_it_really:
                print('   ' + operation)
                resp = requests.post(url=sonarqube.env.get_url() + '/api/' + api, auth=sonarqube.env.get_credentials(), params=params)
                if resp.status_code != 200:
                    print('HTTP Error ' + resp.status_code + ' from SonarQube API query')
            else:
                print('   DRY RUN for ' + operation)

def was_fp_or_wf(key):
    changelog = get_changelog(key)
    for log in changelog:
        if is_log_a_closed_fp(log) or is_log_a_closed_wf(log) or is_log_a_severity_change(log) or is_log_a_type_change(
                log):
            return True
    return False


def get_log_date(log):
    return log['creationDate']


def is_log_a_closed_resolved_as(log, old_value):
    cond1 = False
    cond2 = False

    for diff in log['diffs']:
        if diff['key'] == 'resolution' and 'newValue' in diff and diff['newValue'] == 'FIXED' and 'oldValue' in diff and \
                        diff['oldValue'] == old_value:
            cond1 = True
        if diff['key'] == 'status' and 'newValue' in diff and diff['newValue'] == 'CLOSED' and 'oldValue' in diff and \
                        diff['oldValue'] == 'RESOLVED':
            cond2 = True
    return cond1 and cond2


def is_log_a_closed_wf(log):
    return is_log_a_closed_resolved_as(log, 'WONTFIX')


def is_log_a_comment(log):
    return True


def is_log_an_assign(log):
    return False


def is_log_a_tag(log):
    return False

def is_log_a_closed_fp(log):
    return is_log_a_closed_resolved_as(log, 'FALSE-POSITIVE')

def is_log_a_resolve_as(log, resolve_reason):
    cond1 = False
    cond2 = False
    for diff in log['diffs']:
        if diff['key'] == 'resolution' and 'newValue' in diff and diff['newValue'] == resolve_reason:
            cond1 = True
        if diff['key'] == 'status' and 'newValue' in diff and diff['newValue'] == 'RESOLVED':
            cond2 = True
    return cond1 and cond2

def is_log_an_assignee(log):
    for diff in log['diffs']:
        if diff['key'] == 'assignee':
            return True

def is_log_a_reopen(log):
    cond1 = False
    cond2 = False
    for diff in log['diffs']:
        if diff['key'] == 'resolution':
            cond1 = True
        if diff['key'] == 'status' and 'newValue' in diff and diff['newValue'] == 'REOPENED':
            cond2 = True
    return cond1 and cond2

def is_log_a_resolve_as_fp(log):
    return is_log_a_resolve_as(log, 'FALSE-POSITIVE')

def is_log_a_resolve_as_wf(log):
    return is_log_a_resolve_as(log, 'WONTFIX')


def log_change_type(log):
    return log['diffs'][0]['key']


def is_log_a_severity_change(log):
    return log_change_type(log) == 'severity'


def is_log_a_type_change(log):
    return log_change_type(log) == 'type'


def is_log_an_assignee_change(log):
    return log_change_type(log) == 'assignee'


def is_log_a_tag_change(log):
    return log_change_type(log) == 'tags'


def get_log_new_value(log, key_type):
    for diff in log['diffs']:
        if diff['key'] == key_type:
            return diff['newValue']
    return 'undefined'


def get_log_assignee(log):
    return get_log_new_value(log, 'assignee')


def get_log_new_severity(log):
    return get_log_new_value(log, 'severity')


def get_log_new_type(log):
    return get_log_new_value(log, 'type')


def get_log_new_tag(log):
    return get_log_new_value(log, 'tags')


def identical_attributes(o1, o2, key_list):
    for key in key_list:
        if o1[key] != o2[key]:
            return False
    return True


def search_siblings(closed_issue, issue_list, only_new_issues=True):
    siblings = []
    for iss in issue_list:
        if identical_attributes(closed_issue, iss, ['rule', 'component', 'message', 'debt']):
            if only_new_issues:
                if len(get_changelog(iss['key'])) == 0:
                    # Add issue only if it has no change log, meaning it's brand new
                    siblings.append(iss)
            else:
                siblings.append(iss)
    return siblings


def print_whole_issue(issue):
    print(json.dumps(issue, indent=4, sort_keys=True))


def print_issue(issue):
    for attr in ['rule', 'component', 'message', 'debt', 'author', 'key', 'status']:
        print (issue[attr], ',')
    print()


def parse_args():
    global project_key
    global root_url
    global dry_run_mode
    global token
    global credentials

    parser = argparse.ArgumentParser(
            description='Search for unexpectedly closed issues and recover their history in a corresponding new issue.')
    parser.add_argument('-p', '--projectKey', help='Project key of the project to search', required=True)
    parser.add_argument('-t', '--token',
                        help='Token to authenticate to SonarQube - Unauthenticated usage is not possible',
                        required=True)
    parser.add_argument('-r', '--recover',
                        help='What information to recover (default is FP and WF, but issue assignment, tags, severity and type change can be recovered too',
                        required=False)
    parser.add_argument('-d', '--dryrun',
                        help='If True, show changes but don\'t apply, if False, apply changes - Default is true',
                        required=False)
    parser.add_argument('-u', '--url', help='Root URL of the SonarQube server, default is http://localhost:9000',
                        required=False)

    args = parser.parse_args()

    project_key = args.projectKey
    soanrqube.env.set_token(args.token)
    sonarqube.env.set_url(args.url if args.url != None else "http://localhost:9000")

    if args.dryrun == "False":
        dry_run_mode = True


# ------------------------------------------------------------------------------

try:
    import argparse
except ImportError:
    if sys.version_info < (2, 7, 0):
        print("Error:")
        print("You are running an old version of python. Two options to fix the problem")
        print("  Option 1: Upgrade to python version >= 2.7")
        print("  Option 2: Install argparse library for the current python version")
        print("            See: https://pypi.python.org/pypi/argparse")

parse_args()


all_issues = issues.search(project_key)

non_closed_issues = []
mistakenly_closed_issues = []

for issue in all_issues:
    print('----ISSUE-------------------------------------------------------------')
    print(issue.toString())
    # print('----CHANGELOG-------------')
    # print_object(get_changelog(issue['key']))
    print('----------------------------------------------------------------------')
    if issue.get_status() == 'CLOSED':
        if was_fp_or_wf(issue['key']):
            mistakenly_closed_issues.append(issue)
    else:
        non_closed_issues.append(issue)

print('----------------------------------------------------------------------')
print('        ', len(mistakenly_closed_issues), 'mistakenly closed issues')
print('----------------------------------------------------------------------')

for issue in mistakenly_closed_issues:
    # print_issue(issue)
    # print_change_log(issue['key'])
    print('Searching sibling for issue key ', issue['key'])
    siblings = search_siblings(issue, non_closed_issues, False)
    if len(siblings) >= 0:
        print('   Found', len(siblings), 'SIBLING(S)')
        for sibling in siblings:
            print('  ')
            print_issue(sibling)
        if len(siblings) == 1:
            print('   Automatically applying changelog')
            apply_changelog(siblings[0]['key'], issue['key'], dry_run_mode)
        else:
            print('Ambiguity for issue, cannot automatically apply changelog')
    print('----------------------------------------------------------------------')