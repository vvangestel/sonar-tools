#!/usr/bin/env python3
#
# sonar-tools tests
# Copyright (C) 2024 Olivier Korach
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

""" applications tests """

import datetime
import pytest

import utilities as util
import sonar.logging as log
from sonar import applications, exceptions

EXISTING_KEY = "APP_TEST"
EXISTING_KEY_2 = "APP_TEST_2"
NON_EXISTING_KEY = "NON_EXISTING"
TEST_KEY = "MY_APPPP"


def test_get_object() -> None:
    """Test get_object and verify that if requested twice the same object is returned"""
    portf = applications.Application.get_object(endpoint=util.SQ, key=EXISTING_KEY)
    assert portf.key == EXISTING_KEY
    portf2 = applications.Application.get_object(endpoint=util.SQ, key=EXISTING_KEY)
    assert portf2.key == EXISTING_KEY
    assert portf == portf2


def test_count() -> None:
    """Verify count works"""
    assert applications.count(util.SQ) > 0


def test_search() -> None:
    """Verify that search with criterias work"""
    res_list = applications.search(endpoint=util.SQ, params={"s": "analysisDate"})
    oldest = datetime.datetime(1970, 1, 1).replace(tzinfo=datetime.timezone.utc)
    for app in res_list.values():
        app_date = app.last_analysis()
        if app_date and app_date != "":
            assert oldest <= app_date
            oldest = app_date


def test_get_object_non_existing() -> None:
    """Test exception raised when providing non existing portfolio key"""
    with pytest.raises(exceptions.ObjectNotFound) as e:
        _ = applications.Application.get_object(endpoint=util.SQ, key=NON_EXISTING_KEY)
    assert str(e.value) == f"Application key '{NON_EXISTING_KEY}' not found"


def test_exists() -> None:
    """Test exist"""
    assert applications.exists(endpoint=util.SQ, key=EXISTING_KEY)
    assert not applications.exists(endpoint=util.SQ, key=NON_EXISTING_KEY)


def test_get_list() -> None:
    """Test portfolio get_list"""
    p_dict = applications.get_list(endpoint=util.SQ, key_list=f"{EXISTING_KEY},{EXISTING_KEY_2}")
    assert EXISTING_KEY in p_dict
    assert EXISTING_KEY_2 in p_dict
    assert len(p_dict) == 2


def test_create_delete() -> None:
    """Test portfolio create delete"""
    app = applications.Application.create(endpoint=util.SQ, name="My App", key=TEST_KEY)
    assert app is not None
    assert app.key == TEST_KEY
    assert app.name == "My App"
    app.delete()
    assert not applications.exists(endpoint=util.SQ, key=TEST_KEY)

    # Test delete with 1 project in the app
    app = applications.Application.create(endpoint=util.SQ, name="My App", key=TEST_KEY)
    assert app is not None
    assert app.key == TEST_KEY
    assert app.name == "My App"
    app.add_projects(["okorach_sonar-tools"])
    app.delete()
    assert not applications.exists(endpoint=util.SQ, key=TEST_KEY)


def test_permissions_1() -> None:
    """Test permissions"""
    app = applications.Application.create(endpoint=util.SQ, name="An app", key=TEST_KEY)
    app.set_permissions({"groups": {"sonar-users": ["user", "admin"], "sonar-administrators": ["user", "admin"]}})
    # assert app.permissions().to_json()["groups"] == {"sonar-users": ["user", "admin"], "sonar-administrators": ["user", "admin"]}
    app.delete()
    assert not applications.exists(endpoint=util.SQ, key=TEST_KEY)


def test_permissions_2() -> None:
    """Test permissions"""
    app = applications.Application.create(endpoint=util.SQ, name="A portfolio", key=TEST_KEY)
    app.set_permissions({"groups": {"sonar-users": ["user"], "sonar-administrators": ["user", "admin"]}})
    # assert app.permissions().to_json()["groups"] == {"sonar-users": ["user"], "sonar-administrators": ["user", "admin"]}
    app.delete()
    assert not applications.exists(endpoint=util.SQ, key=TEST_KEY)


def test_get_projects() -> None:
    """test_get_projects"""
    app = applications.Application.get_object(endpoint=util.SQ, key=EXISTING_KEY)
    count = len(app.projects())
    assert count > 0
    assert len(app.projects()) == count


def test_get_branches() -> None:
    """test_get_projects"""
    app = applications.Application.get_object(endpoint=util.SQ, key=EXISTING_KEY)
    count = len(app.branches())
    assert count > 0
    assert len(app.branches()) == count


def test_no_audit() -> None:
    """Check stop fast when audit params are disabled"""
    app = applications.Application.get_object(endpoint=util.SQ, key=EXISTING_KEY)
    assert len(app.audit({"audit.applications": False})) == 0
    assert len(app._audit_empty({"audit.applications.empty": False})) == 0
    assert len(app._audit_singleton({"audit.applications.singleton": False})) == 0


def test_set_tags() -> None:
    """Test setting tags"""
    app = applications.Application.create(endpoint=util.SQ, name="A portfolio", key=TEST_KEY)
    app.set_tags(["foo", "bar"])
    assert app._tags == ["foo", "bar"]
    app.delete()


def test_search_by_name() -> None:
    """test_search_by_name"""
    log.set_logger(filename="test.log")
    log.set_debug_level("DEBUG")
    app = applications.Application.get_object(endpoint=util.SQ, key=EXISTING_KEY)
    other_apps = applications.search_by_name(endpoint=util.SQ, name=app.name)

    assert len(other_apps) == 1
    first_app = list(other_apps.values())[0]
    # FIXME this test fails
    assert app == first_app
