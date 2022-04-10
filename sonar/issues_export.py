#!/usr/local/bin/python3
#
# sonar-tools
# Copyright (C) 2019-2022 Olivier Korach
# mailto:olivier.korach AT gmail DOT com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
'''
    This script exports issues as CSV

    Usage: issuesearch.py -t <SQ_TOKEN> -u <SQ_URL> [<filters>]

    Filters can be:
    [-k <projectKey>]
    [-s <statuses>] (FIXED, CLOSED, REOPENED, REVIEWED)
    [-r <resolutions>] (UNRESOLVED, FALSE-POSITIVE, WONTFIX)
    [-a <createdAfter>] issues created on or after a given date (YYYY-MM-DD)
    [-b <createdBefore>] issues created before or on a given date (YYYY-MM-DD)
    [--severities <severities>] Comma separated desired severities: BLOCKER, CRITICAL, MAJOR, MINOR, INFO
    [--types <types>] Comma separated issue types (VULNERABILITY,BUG,CODE_SMELL,HOTSPOT)
    [--tags]
'''
import sys
from sonar import version, env, projects, hotspots, issues, options
import sonar.utilities as util
from sonar.findings import to_csv_header

def parse_args():
    parser = util.set_common_args('SonarQube issues extractor')
    parser = util.set_component_args(parser)
    parser.add_argument('-o', '--outputFile', required=False, help='File to generate the report, default is stdout'
                        'Format is automatically deducted from file extension, if extension given')
    parser.add_argument('-f', '--format', required=False, default='csv',
                        help='Format of output (json, csv), default is csv')
    parser.add_argument('-b', '--branches', required=False, default=None,
                        help='Comma separated list of branches to export. Use * to export findings from all branches. '
                             'If not specified, only findings of the main branch will be exported')
    parser.add_argument('-p', '--pullRequests', required=False, default=None,
                        help='Comma separated list of pull request. Use * to export findings from all PRs. '
                             'If not specified, only findings of the main branch will be exported')
    parser.add_argument('--statuses', required=False, help='comma separated issue status, '
                        'OPEN, WONTFIX, FALSE-POSITIVE, FIXED, CLOSED, REOPENED, REVIEWED')
    parser.add_argument('--createdAfter', required=False,
                        help='issues created on or after a given date (YYYY-MM-DD)')
    parser.add_argument('--createdBefore', required=False,
                        help='issues created on or before a given date (YYYY-MM-DD)')
    parser.add_argument('--resolutions', required=False,
                        help='Comma separated resolution states of the issues among'
                             'UNRESOLVED, FALSE-POSITIVE, WONTFIX')
    parser.add_argument('--severities', required=False,
                        help='Comma separated severities among BLOCKER, CRITICAL, MAJOR, MINOR, INFO')
    parser.add_argument('--types', required=False,
                        help='Comma separated issue types among CODE_SMELL, BUG, VULNERABILITY, HOTSPOT')
    parser.add_argument('--tags', help='Comma separated issue tags', required=False)
    parser.add_argument('--useFindings', required=False, default=False, action='store_true',
                        help='Use export_findings() whenever possible')
    parser.add_argument('--' + options.WITH_URL, required=False, default=False, action='store_true',
                        help='Generate issues URL in the report, false by default')
    parser.add_argument('--' + options.CSV_SEPARATOR, required=False, default=util.CSV_SEPARATOR,
                        help=f'CSV separator (for CSV output), default {util.CSV_SEPARATOR}')
    return util.parse_and_check_token(parser)

def __dump_findings(issues_list, file, file_format, **kwargs):
    if file is None:
        f = sys.stdout
        util.logger.info("Dumping report to stdout")
    else:
        f = open(file, "w", encoding='utf-8')
        util.logger.info("Dumping report to file '%s'", file)
    if file_format == 'json':
        print("[", file=f)
    else:
        print(to_csv_header(), file=f)
    is_first = True
    url = ''
    sep = kwargs[options.CSV_SEPARATOR]
    for _, issue in issues_list.items():
        if file_format == 'json':
            pfx = "" if is_first else ",\n"
            issue_json = issue.to_json()
            if not kwargs[options.WITH_URL]:
                issue_json.pop('url', None)
            print(pfx + util.json_dump(issue_json), file=f, end='')
            is_first = False
        else:
            if kwargs[options.WITH_URL]:
                url = f'{sep}"{issue.url()}"'
            print(f"{issue.to_csv(sep)}{url}", file=f)

    if file_format == 'json':
        print("\n]", file=f)
    if file is not None:
        f.close()


def main():
    args = parse_args()
    sqenv = env.Environment(some_url=args.url, some_token=args.token)
    sqenv.set_env(args.url, args.token)
    kwargs = vars(args)
    util.check_environment(kwargs)
    util.logger.info('sonar-tools version %s', version.PACKAGE_VERSION)

    # Remove unset params from the dict
    params = vars(args)
    for p in params.copy():
        if params[p] is None:
            del params[p]

    # Add SQ environment
    params.update({'env': sqenv})
    all_issues = {}
    project_key = kwargs.get('componentKeys', None)
    branch_str = kwargs.get('branches', None)
    pr_str = kwargs.get('pullRequests', None)
    if project_key is not None:
        branches = []
        prs = []
        if branch_str == '*':
            project = projects.Project(project_key, endpoint=sqenv)
            branches = project.get_branches()
        elif branch_str is not None:
            branches = util.csv_to_list(branch_str)
        if pr_str == '*':
            project = projects.Project(project_key, endpoint=sqenv)
            prs = project.get_pull_requests()
        elif pr_str is not None:
            prs = util.csv_to_list(pr_str)
        if branches or prs:
            for b in branches:
                all_issues.update(issues.search_by_project(project_key, branch=b.name,
                                  endpoint=sqenv, search_findings=kwargs['useFindings']))
                if not kwargs['useFindings']:
                    all_issues.update(hotspots.search_by_project(project_key, sqenv, branch=b.name))
            for p in prs:
                all_issues.update(issues.search_by_project(project_key, pull_request=p.key,
                                  endpoint=sqenv, search_findings=kwargs['useFindings']))
                if not kwargs['useFindings']:
                    all_issues.update(hotspots.search_by_project(project_key, sqenv, pull_request=p.key))
        else:
            all_issues = issues.search_by_project(project_key, sqenv, search_findings=kwargs['useFindings'])
            if not kwargs['useFindings']:
                all_issues.update(hotspots.search_by_project(project_key, sqenv))
    else:
        all_issues = issues.search_by_project(project_key, sqenv, search_findings=kwargs['useFindings'])
        if not kwargs['useFindings']:
            all_issues.update(hotspots.search_by_project(project_key, sqenv))
    fmt = kwargs['format']
    if kwargs.get('outputFile', None) is not None:
        ext = kwargs['outputFile'].split('.')[-1].lower()
        if ext in ('csv', 'json'):
            fmt = ext
    __dump_findings(all_issues, kwargs.get('outputFile', None), fmt, **kwargs)
    util.logger.info("Returned issues: %d", len(all_issues))
    sys.exit(0)


if __name__ == '__main__':
    main()