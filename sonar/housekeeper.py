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

    Removes obsolete data from SonarQube platform
    Currently:
    - projects, branches, PR not analyzed since a given number of days
    - Tokens not renewed since a given number of days

'''
import sys
from sonar import projects, users, groups, env, version
from sonar.branches import Branch
from sonar.pull_requests import PullRequest
from sonar.user_tokens import UserToken
import sonar.utilities as util
from sonar.audit import config, problem

def get_project_problems(max_days_proj, max_days_branch, max_days_pr, endpoint):
    problems = []
    if max_days_proj < 90:
        util.logger.error("As a safety measure, can't delete projects more recent than 90 days")
        return problems

    settings = {
        'audit.projects.maxLastAnalysisAge': max_days_proj,
        'audit.projects.branches.maxLastAnalysisAge': max_days_branch,
        'audit.projects.pullRequests.maxLastAnalysisAge': max_days_pr,
        'audit.projects.neverAnalyzed': False,
        'audit.projects.duplicates': False,
        'audit.projects.visibility': False,
        'audit.projects.permissions': False
    }
    settings = config.load(config_name='sonar-audit', settings=settings)
    problems = projects.audit(endpoint=endpoint, audit_settings=settings)
    nb_proj = 0
    total_loc = 0
    for p in problems:
        if p.concerned_object is not None and isinstance(p.concerned_object, projects.Project):
            nb_proj += 1
            total_loc += int(p.concerned_object.get_measure('ncloc', fallback='0'))

    if nb_proj == 0:
        util.logger.info("%d projects older than %d days found during audit", nb_proj, max_days_proj)
    else:
        util.logger.warning("%d projects older than %d days for a total of %d LoC found during audit",
                            nb_proj, max_days_proj, total_loc)
    return problems

def get_user_problems(max_days, endpoint):
    settings = {
        'audit.tokens.maxAge': max_days,
        'audit.tokens.maxUnusedAge': 30,
        'audit.groups.empty': True
    }
    settings = config.load(config_name='sonar-audit', settings=settings)
    user_problems = users.audit(endpoint=endpoint, audit_settings=settings)
    nb_problems = len(user_problems)
    if nb_problems == 0:
        util.logger.info("%d user tokens older than %d days found during audit", nb_problems, max_days)
    else:
        util.logger.warning("%d user tokens older than %d days found during audit", nb_problems, max_days)
    group_problems = groups.audit(endpoint=endpoint, audit_settings=settings)
    user_problems += group_problems
    nb_problems = len(group_problems)
    if nb_problems == 0:
        util.logger.info("%d empty groups found during audit", nb_problems)
    else:
        util.logger.warning("%d empty groups found during audit", nb_problems)
    return user_problems


def _parse_arguments():
    _DEFAULT_PROJECT_OBSOLESCENCE = 365
    _DEFAULT_BRANCH_OBSOLESCENCE = 90
    _DEFAULT_PR_OBSOLESCENCE = 30
    _DEFAULT_TOKEN_OBSOLESCENCE = 365
    util.set_logger('sonar-housekeeper')
    parser = util.set_common_args('Deletes projects not analyzed since a given numbr of days')
    parser.add_argument('--mode', required=False, choices=['dry-run', 'delete'],
                        default='dry-run',
                        help='''
                        If 'dry-run', script only lists objects (projects, branches, PRs or tokens) to delete,
                        If 'delete' it deletes projects or tokens
                        ''')
    parser.add_argument('-P', '--projects', required=False, type=int, default=_DEFAULT_PROJECT_OBSOLESCENCE,
        help=f'Deletes projects not analyzed since a given number of days, by default {_DEFAULT_PROJECT_OBSOLESCENCE} days')
    parser.add_argument('-B', '--branches', required=False, type=int, default=_DEFAULT_BRANCH_OBSOLESCENCE,
        help=f'Deletes branches not to be kept and not analyzed since a given number of days, by default {_DEFAULT_BRANCH_OBSOLESCENCE} days')
    parser.add_argument('-R', '--pullrequests', required=False, type=int, default=_DEFAULT_BRANCH_OBSOLESCENCE,
        help=f'Deletes pull requests not analyzed since a given number of days, by default {_DEFAULT_PR_OBSOLESCENCE} days')
    parser.add_argument('-T', '--tokens', required=False, type=int, default=_DEFAULT_TOKEN_OBSOLESCENCE,
        help=f'Deletes user tokens older than a certain number of days, by default {_DEFAULT_TOKEN_OBSOLESCENCE} days')
    return util.parse_and_check_token(parser)


def _delete_objects(problems, mode):
    revoked_token_count = 0
    deleted_projects = {}
    deleted_branch_count = 0
    deleted_pr_count = 0
    deleted_loc = 0
    for p in problems:
        obj = p.concerned_object
        if obj is None:
            continue    # BUG
        if isinstance(obj, projects.Project):
            loc = int(obj.get_measure('ncloc', fallback='0'))
            util.logger.info("Deleting %s, %d LoC", str(obj), loc)
            if mode != 'delete' or obj.delete():
                deleted_projects[obj.key] = obj
                deleted_loc += loc
        if isinstance(obj, Branch):
            if obj.project.key in deleted_projects:
                util.logger.info("%s deleted, so no need to delete %s", str(obj.project), str(obj))
            elif mode != 'delete' or obj.delete():
                deleted_branch_count += 1
        if isinstance(obj, PullRequest):
            if obj.project.key in deleted_projects:
                util.logger.info("%s deleted, so no need to delete %s", str(obj.project), str(obj))
            elif mode != 'delete' or obj.delete():
                deleted_pr_count += 1
        if isinstance(obj, UserToken) and (mode != 'delete' or obj.revoke()):
            revoked_token_count += 1
    return (len(deleted_projects), deleted_loc, deleted_branch_count, deleted_pr_count, revoked_token_count)


def main():
    args = _parse_arguments()

    sq = env.Environment(some_url=args.url, some_token=args.token)
    kwargs = vars(args)
    mode = args.mode
    util.check_environment(kwargs)
    util.logger.debug("Args = %s", str(kwargs))
    util.logger.info('sonar-tools version %s', version.PACKAGE_VERSION)
    problems = []
    if args.projects > 0 or args.branches > 0 or args.pullrequests > 0:
        problems = get_project_problems(args.projects, args.branches, args.pullrequests, sq)

    if args.tokens:
        problems += get_user_problems(args.tokens, sq)

    problem.dump_report(problems, file=None, file_format='csv')

    op = 'to delete'
    if mode == 'delete':
        op = 'deleted'
    (deleted_proj, deleted_loc, deleted_branches, deleted_prs, revoked_tokens) = _delete_objects(problems, mode)

    util.logger.info("%d projects older than %d days (%d LoCs) %s", deleted_proj, args.projects, deleted_loc, op)
    util.logger.info("%d branches older than %d days %s", deleted_branches, args.branches, op)
    util.logger.info("%d pull requests older than %d days deleted %s", deleted_prs, args.pullrequests, op)
    util.logger.info("%d tokens older than %d days revoked", revoked_tokens, args.tokens)
    sys.exit(0)


if __name__ == "__main__":
    main()