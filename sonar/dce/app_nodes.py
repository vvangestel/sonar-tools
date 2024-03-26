#
# sonar-tools
# Copyright (C) 2019-2024 Olivier Korach
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
"""

    Abstraction of the App Node concept

"""

import datetime
from dateutil.relativedelta import relativedelta
import sonar.utilities as util
from sonar.audit import rules
import sonar.sif_node as sifn
import sonar.audit.problem as pb
import sonar.dce.nodes as dce_nodes

_RELEASE_DATE_6_7 = datetime.datetime(2017, 11, 8) + relativedelta(months=+6)
_RELEASE_DATE_7_9 = datetime.datetime(2019, 7, 1) + relativedelta(months=+6)
_RELEASE_DATE_8_9 = datetime.datetime(2021, 5, 4) + relativedelta(months=+6)

_SYSTEM = "System"


class AppNode(dce_nodes.DceNode):
    def __str__(self):
        return f"App Node '{self.name()}'"

    def plugins(self):
        self.json.get("Plugins", None)

    def health(self):
        return self.json.get("Health", "RED")

    def node_type(self):
        return "APPLICATION"

    def start_time(self):
        return self.sif.start_time()

    def version(self, digits=3, as_string=False):
        try:
            return util.string_to_version(self.json[_SYSTEM]["Version"], digits, as_string)
        except KeyError:
            return None

    def edition(self):
        self.sif.edition()

    def name(self):
        return self.json["Name"]

    def audit(self, audit_settings: dict[str, str] = None):
        util.logger.info("Auditing %s", str(self))
        return (
            self.__audit_official()
            + self.__audit_health()
            + self.__audit_version()
            + sifn.audit_web(self, f"{str(self)} Web process", self.json)
            + sifn.audit_ce(self, f"{str(self)} CE process", self.json)
        )

    def __audit_health(self):
        if self.health() != dce_nodes.HEALTH_GREEN:
            rule = rules.get_rule(rules.RuleId.DCE_APP_NODE_NOT_GREEN)
            return [pb.Problem(rule.type, rule.severity, rule.msg.format(str(self), self.health()))]
        else:
            util.logger.debug("%s: Node health is %s", str(self), dce_nodes.HEALTH_GREEN)
            return []

    def __audit_official(self):
        if _SYSTEM not in self.json:
            util.logger.warning(
                "%s: Official distribution information missing, audit skipped...",
                str(self),
            )
            return []
        elif not self.json[_SYSTEM]["Official Distribution"]:
            rule = rules.get_rule(rules.RuleId.DCE_APP_NODE_UNOFFICIAL_DISTRO)
            return [pb.Problem(rule.type, rule.severity, rule.msg.format(str(self)))]
        else:
            util.logger.debug("%s: Node is official distribution", str(self))
            return []

    def __audit_version(self):
        sq_version = self.version()
        if sq_version is None:
            util.logger.warning("%s: Version information is missing, audit on node vresion is skipped...")
            return []
        st_time = self.sif.start_time()
        if (
            (st_time > _RELEASE_DATE_6_7 and sq_version < (6, 7, 0))
            or (st_time > _RELEASE_DATE_7_9 and sq_version < (7, 9, 0))
            or (st_time > _RELEASE_DATE_8_9 and sq_version < (8, 9, 0))
        ):
            rule = rules.get_rule(rules.RuleId.BELOW_LTS)
            return [pb.Problem(rule.type, rule.severity, rule.msg)]
        else:
            util.logger.debug(
                "%s: Version %s is correct wrt LTS",
                str(self),
                self.version(as_string=True),
            )
            return []


def audit(sub_sif: dict[str, str], sif_object: object, audit_settings: dict[str, str] = None) -> list[pb.Problem]:
    """Audits application nodes of a DCE instance

    :param dict sub_sif: The JSON subsection of the SIF pertaining to the App Nodes
    :param Sif sif: The Sif object
    :param dict audit_settings: Config settings for audit
    :return: List of Problems
    :rtype: list
    """
    if audit_settings is None:
        audit_settings = {}
    nodes = []
    problems = []
    for n in sub_sif:
        nodes.append(AppNode(n, sif_object))
    if len(nodes) == 1:
        rule = rules.get_rule(rules.RuleId.DCE_APP_CLUSTER_NOT_HA)
        return [pb.Problem(rule.type, rule.severity, rule.msg)]
    for i in range(len(nodes)):
        problems += nodes[i].audit(audit_settings)
        for j in range(i, len(nodes)):
            v1 = nodes[i].version()
            v2 = nodes[j].version()
            if v1 is not None and v2 is not None and v1 != v2:
                rule = rules.get_rule(rules.RuleId.DCE_DIFFERENT_APP_NODES_VERSIONS)
                problems.append(
                    pb.Problem(
                        rule.type,
                        rule.severity,
                        rule.msg.format(str(nodes[i]), str(nodes[j])),
                    )
                )
            if nodes[i].plugins() != nodes[j].plugins():
                rule = rules.get_rule(rules.RuleId.DCE_DIFFERENT_APP_NODES_PLUGINS)
                problems.append(
                    pb.Problem(
                        rule.type,
                        rule.severity,
                        rule.msg.format(str(nodes[i]), str(nodes[j])),
                    )
                )
    return problems
