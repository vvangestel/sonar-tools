# sonar-tools
Command line tools to help in SonarQube administration tasks. The following utilities are available:
- **sonar-audit**: Audits a SonarQube platform
- **sonar-measures-export**: Exports measures/metrics of one, several or all projects of the platform i CSV
- **sonar-issues-export**: Exports issues (potentially filtered) from the platform in CSV
- **sonar-projects-export**: Exports all projects from a platform (EE and higher)
- **sonar-projects-import**: Imports a list of projects into a platform (EE and higher)


# Requirements and Installation
- `sonar-tools` requires python 3.6 or higher
- Install is based on [pip](/https://pypi.org/project/pip/). To install run: `python3 -m pip install sonar-tools`

All tools accept the following common parameters:
- `-h` : Displays a help and exits
- `-u` : URL of the SonarQube server, default is `http://localhost:9000`
- `-t` : token of the user to invoke the SonarQube APIs, like `d04d671eaec0272b6c83c056ac363f9b78919b06` (using login/password is not possible)
- `-g` : Debug level (`WARN`, `ÌNFO` or `DEBUG`). `ERROR` and above is always active. Default is `INFO`
- `-m` : Mode when performing API calls, `dry-run` is the default
  - `batch`: All API calls are performed without any confirmation
  - `confirm`: All API calls that change the SonarQube internal state (POST and DELETE) are asking for a confirmation before execution
  - `dry-run`: All API calls taht would change SonarQube internal state are just output in logging but not actually performed.


# sonar-audit

Audits the SonarQube platform and output warning logs whenever a suspicious or incorrect setting/situation is found.
What is audited is listed at the bottom of this page

Usage: `sonar-audit -u <url> -t <token> [--what [settings|projects|qg|qp]]`
When `--what` is not specified, everything audited
- `--what settings`: Audits global settings and general system data (system info in particular)
- `--what qp`: Audits quality profiles
- `--what qg`: Audits quality gates
- `--what projects`: Audits all projects. This can be a fairly long operation


# sonar-measures-export

Exports one or all projects with all (or some selected) measures in a CSV file.
The CSV is sent to standard output.
Plenty of issue filters can be specified from the command line, type `sonar-measures-export -h` for details

Basic Usage: `sonar-measures-export -u <url> -t <token> --metricKeys _main -b -r >measures.csv`

## Examples
```
sonar-measures-export -u <url> -t <token> -m ncloc,bugs,vulnerabilities >measures.csv
sonar-measures-export -u <url> -t <token> -m _main >main_measures.csv
sonar-measures-export -u <url> -t <token> -k <projectKey1>,<projectKey2> -m _all >all_measures.csv
```

# sonar-issues-export

Exports a list of issues as CSV (sent to standard output)
Plenty of issue filters can be specified from the command line, type `sonar-issues-export -h` for details
:warning: On large platforms with a lot of issues, it can be stressful for the platform (many API calls) and very long to export all issues. It's recommended to define filters that will only export a subset of all issues (see examples below).

## Examples
```
sonar-issues-export -u <url> -t <token> >all_issues.csv
sonar-issues-export -u <url> -t <token> -k <projectKey> >project_issues.csv
sonar-issues-export -u <url> -t <token> -r FALSE-POSITIVE,WONTFIX >fp_wf.csv
sonar-issues-export -u <url> -t <token> -a 2020-01-01 >issues_created_in_2020.csv
sonar-issues-export -u <url> -t <token> -types VULNERABILITY,BUG >bugs_and_vulnerabilities.csv
```


# sonar-projects-export

Exports all projects of a given SonarQube platform.
:warning: This requires a SonarQube Enterprise or Data Center Edition.
It sends to the output a CSV with the list of project keys, the export result (`SUCCESS` or `FAIL`), and:
- If the export was successful, the generated zip file
- If the export was failed, the failure reason

:information_source: All zip files are generated in the platform standard location(under `data/governance/project_dumps/export`)

The CSV file generated is to be used by the `sonar-projects-import` tool

## Examples
```
sonar-projects-export -u <url> -t <token> >exported_projects.csv
```

# sonar-projects-import

Imports a list of projects previously exported with `sonar-projects-export`.
:warning: This requires a SonarQube Enterprise or Data Center Edition.
It takes as input a CSV file produced by `sonar-projects-export`

:information_source: All exported zip files must be first copied to the right location on the target platform for the import to be successful (In `data/governance/project_dumps/import`)

## Examples
```
sonar-projects-import -u <url> -t <token> -f <export_csv_file>
```

# Tools coming soon

## sonar-issues-recover

Tries to recover issues that were mistakenly closed following a scan with incorrect parameters. This tool is only useful for platforms in version 7.9.x and lower since this feature is built-in with SonarQube 8.x

Issue recovery means:
- Reapplying all transitions to the issue to reach its final state before close (Usually *False positive* or *Won't Fix*)
- Reapplying all manual comments
- Reapplying all severity or issue type change

### :information_source: Limitations
- The script has to be run before the closed issue purge period (SonarQube parameter `sonar.dbcleaner.daysBeforeDeletingClosedIssues` whose default value is **30 days**)
- The recovery is not 100% deterministic. In some rare corner cases (typically less than 5%) it is not possible to determine that an issue was closed unexpectedly, in which case the issue is not recovered. The script will log those cases
- When recovering an issue all state change of the issue are applied with the user whose token is provided to the script (it cannot be applied with the original user). Some comments are added to mention who was the original user that made the change

### Examples
```
issues_recover.py -u <url> -t <token> -k <projectKey>
```

## sonar-issues-sync

This tool tries to sync issues manual changes (FP, WF, Comments, Change of Severity or of issue type) between:
- 2 different branches of a same project
- A same project on 2 different SonarQube platforms

Issue sync means:
- Applying all transitions of the source issue to the target issue
- Applying all manual comments
- Applying all severity or issue type change

### Examples
```
# Syncs issues for project <projectKey> from platform <src_url> to platform <target_url>
sonar-issues-sync -u <src_url> -t <src_token> -k <projectKey> -U <target_url> -T <target_token>
```

### :information_source: Limitations
- The sync is not 100% deterministic. In some rare corner cases (typically less than 5%) it is not possible to determine that an issue is the same between 2 branches or 2 platforms,in which case the issue is not sync'ed. The script will log those cases
- When sync'ing an issue, all changes of the target issue are applied with the user whose token is provided to the script (it cannot be applied with the user of the original issue). Some comments are added to mention who was the original user that made the change
- To be modified (sync'ed from a source issue), the target issue must has zero manual changes ie it must be has created originally by SonarQube


## sonar-project-history
Extracts the history of some given metrics for a given project

## sonar-project-housekeeper
Deletes all projects whose last analysis date (on any branch) is older than a given number of days.

### :information_source: Limitations
To avoid bad mistakes (mistakenly deleting too many projects), the tools will refuse to delete projects analyzed in the last 90 days.

### :warning: Database backup
**A database backup should always be taken before executing this script. There is no recovery.**

### Example
```
sonar-project-housekeeper -u <url> -t <token> -o <days>
```

# List of checks performed by `sonar-audit`

What is audited:
- General checks:
  - Verifies this is an official distribution
  - Verifies that the admin default password has been changed
  - DCE: Verifies that same plugins are install on all app nodes
  - DCE: Verifies that all app nodes run the same version of SonarQube
  - DCE: Verifies that all nodes are in GREEN status
- General global settings:
  - sonar.forceAuthentication is true
  - sonar.cpd.cross_project is false
  - sonar.core.serverBaseURL is set
  - sonar.global.exclusions is empty
  - Project default visbility is Private
- Global permissions:
  - Max 3 users with global admin, admin quality gates, admin quality profiles or create project permission
  - Max 10 users with global permissions
  - Group 'Anyone' should have no global permissions
  - Group 'sonar-users' should not have Admin, Admin QG, Admin QP or Create Projects permissions
  - Max 2 groups with global admin, admin quality gates, admin quality profiles permissions
  - Max 3 groups with create project permission
  - Max 10 groups with global permissions
- DB Cleaner:
  - Delay to delete inactive SLB (7.9) or branches (8.x) between 10 and 60 days
  - Delay to delete closed issues between 10 and 60 days
  - sonar.dbcleaner.hoursBeforeKeepingOnlyOneSnapshotByDay between 12 and 240 hours (0.5 to 10 days)
  - sonar.dbcleaner.weeksBeforeKeepingOnlyOneSnapshotByWeek between 2 and 12 weeks (0.5 to 3 months)
  - sonar.dbcleaner.weeksBeforeKeepingOnlyOneSnapshotByMonth between 26 and 104 weeks (0.5 year to 2 years)
  - sonar.dbcleaner.weeksBeforeDeletingAllSnapshots between 104 and 260 weeks (2 to 5 years)
- Maintainability rating grid:
  - A maintainability rating threshold between 3% and 5%
  - B maintainability rating threshold between 7% and 10%
  - C maintainability rating threshold between 15% and 20%
  - D maintainability rating threshold between 40% and 50%
- Environment
  - Web heap (`-Xmx`) between 1 GB and 2 GB
  - CE heap (`-Xmx`) between 512 MB per worker and 2 GB per worker
  - Maximum CE 4 workers
  - CE background tasks failure rate of more than 1%
  - Excessive nbr of background tasks: More than 100 pending CE background tasks or more than 20 or 10 x Nbr workers
  - ES heap (`-Xmx`) is less than half the ES index (small indexes) or less than ES index + 1 GB (large indexes)
- Quality Gates:
  - Unused QG
  - QG with 0 conditions or more than 7 conditions
  - QG not using the recommended metrics: reliability, security, maintainibility, coverage, duplication,
    security review rating on new code, new bugs, new vulnerabilities, new hotspots, new blocker, new critical, new major
    and reliability rating and security rating on overall code
  - Thresholds for the above metrics not consistent (non A for ratings on new code, non 0 for numeric count of issues,
    coverage not between 20% and 90%, duplication not between 1% and 3%, secuirty and relibility on overall code lower than D)
  - More than 5 quality gates
- Quality Profiles:
  - QP not modified in 6 months
  - QP with less than 50% of all the available rules activated
  - QP not used by any projects
  - QP not used since more than 6 months
  - QP using deprecated rules
  - More than 5 QP for a given language
- Projects:
  - Projects provisioned but never analyzed
  - Projects not analyzed since 6 months (on any branch)
  - Projects with Public visbility
  - Large projects with too much XML: Projects with more than 200K LoC and XML representing more than 50% of it
  - Permissions:
    - More than 5 different users with direct permissions (use groups)
    - More than 3 users with Project admin permission
    - More than 5 different groups with permissions on project
    - More than 1 group with execute analysis permission
    - More than 2 groups with issue admin permission
    - More than 2 groups with hotspot admin permission
    - More than 2 groups with project admin permission
