import datetime
import json

import pytest
from click import unstyle
from conftest import load

from vulnix.derivation import Derive
from vulnix.output import Filtered, fmt_vuln, output, output_json, output_text
from vulnix.vulnerability import Vulnerability
from vulnix.whitelist import WhitelistRule

V = Vulnerability


@pytest.fixture(name="deriv")
def fixture_deriv():
    d = Derive(name="test-0.2")
    d.store_path = "/nix/store/zsawgflc1fq77ijjzb1369zi6kxnc36j-test-0.2"
    return (
        d,
        {
            V("CVE-2018-0001"),
            V("CVE-2018-0002"),
            V("CVE-2018-0003", cvssv3=9.8),
        },
    )


@pytest.fixture(name="deriv1")
def fixture_deriv1():
    return (Derive(name="foo-1"), {V("CVE-2018-0004"), V("CVE-2018-0005")})


@pytest.fixture(name="deriv2")
def fixture_deriv2():
    return (Derive(name="bar-2"), {V("CVE-2018-0006", cvssv3=5.0)})


@pytest.fixture(name="filt")
def fixture_filt(deriv):
    return Filtered(*deriv)


@pytest.fixture(name="items")
def fixture_items(deriv, deriv1, deriv2):
    return [Filtered(*deriv), Filtered(*deriv1), Filtered(*deriv2)]


def test_init(deriv):
    f = Filtered(*deriv)
    assert f.report == {V("CVE-2018-0001"), V("CVE-2018-0002"), V("CVE-2018-0003")}
    assert not f.masked


def test_add_unspecific_rule(deriv):
    f = Filtered(*deriv)
    f.add(WhitelistRule(pname="test", version="1.2"))
    assert not f.report


def test_add_rule_with_cves(filt):
    filt.add(WhitelistRule(pname="test", version="1.2", cve={"CVE-2018-0001"}))
    assert filt.report == {V("CVE-2018-0002"), V("CVE-2018-0003")}
    assert filt.masked == {V("CVE-2018-0001")}


def test_add_temporary_whitelist(filt):
    assert not filt.until
    filt.add(WhitelistRule(pname="test", version="1.2", until="2018-03-05"))
    assert filt.until == datetime.date(2018, 3, 5)


@pytest.fixture(name="wl_items")
def fixture_wl_items(items):
    # makes deriv1 list only one CVE
    items[1].add(WhitelistRule(cve={"CVE-2018-0004"}, issue_url="https://tracker/4"))
    # makes deriv2 disappear completely
    items[2].add(WhitelistRule(pname="bar", comment="irrelevant"))
    return items


def test_output_text(wl_items, capsys):
    output_text(wl_items, show_whitelisted=True)
    assert (
        capsys.readouterr().out
        == """\
2 derivations with active advisories

------------------------------------------------------------------------
foo-1

CVE                                                CVSSv3
https://nvd.nist.gov/vuln/detail/CVE-2018-0005
https://nvd.nist.gov/vuln/detail/CVE-2018-0004  [whitelisted]

Issue(s):
https://tracker/4

------------------------------------------------------------------------
test-0.2

/nix/store/zsawgflc1fq77ijjzb1369zi6kxnc36j-test-0.2
CVE                                                CVSSv3
https://nvd.nist.gov/vuln/detail/CVE-2018-0003     9.8
https://nvd.nist.gov/vuln/detail/CVE-2018-0001
https://nvd.nist.gov/vuln/detail/CVE-2018-0002

------------------------------------------------------------------------
bar-2

CVE                                                CVSSv3
https://nvd.nist.gov/vuln/detail/CVE-2018-0006     5.0  [whitelisted]

Comment:
* irrelevant
"""
    )


def test_output_json(wl_items, capsys):
    output_json(wl_items)
    assert json.loads(capsys.readouterr().out) == [
        {
            "affected_by": ["CVE-2018-0005"],
            "derivation": None,
            "name": "foo-1",
            "pname": "foo",
            "version": "1",
            "whitelisted": ["CVE-2018-0004"],
            "cvssv3_basescore": {},
            "description": {},
        },
        {
            "affected_by": ["CVE-2018-0001", "CVE-2018-0002", "CVE-2018-0003"],
            "derivation": "/nix/store/zsawgflc1fq77ijjzb1369zi6kxnc36j-test-0.2",
            "name": "test-0.2",
            "pname": "test",
            "version": "0.2",
            "whitelisted": [],
            "cvssv3_basescore": {
                "CVE-2018-0003": 9.8,
            },
            "description": {},
        },
    ]


def test_exitcode(items, capsys):
    assert output([], json_dump=True) == 0
    # something to report
    assert output(items) == 2
    # everything masked
    for i in items:
        i.add(WhitelistRule(pname=i.derivation.pname))
    assert output(items) == 0
    assert output(items, show_whitelisted=True) == 1
    capsys.readouterr()  # swallow stdout/stderr: it doesn't matter here


def test_description():
    v = Vulnerability.parse(load("CVE-2010-0748"))
    assert unstyle(fmt_vuln(v, show_description=True)) == (
        "https://nvd.nist.gov/vuln/detail/CVE-2010-0748              "
        "Transmission before 1.92 allows an attacker to cause a denial of "
        "service (crash) or possibly have other unspecified impact via a "
        "large number of tr arguments in a magnet link."
    )


def test_description_json(capsys):
    d = Derive(name="test-0.2")
    v = Vulnerability.parse(load("CVE-2010-0748"))
    output_json([Filtered(d, {v})])
    assert json.loads(capsys.readouterr().out) == [
        {
            "affected_by": ["CVE-2010-0748"],
            "cvssv3_basescore": {},
            "derivation": None,
            "description": {
                "CVE-2010-0748": "Transmission before 1.92 allows an "
                "attacker to cause a denial of service "
                "(crash) or possibly have other unspecified "
                "impact via a large number of tr arguments "
                "in a magnet link."
            },
            "name": "test-0.2",
            "pname": "test",
            "version": "0.2",
            "whitelisted": [],
        }
    ]
