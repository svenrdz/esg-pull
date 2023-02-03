import pytest

from esgpull.exceptions import AlreadySetFacet
from esgpull.models import Query


def test_empty_asdict():
    assert Query().asdict() == {}


def test_clone_is_deepcopy():
    query = Query(selection=dict(project="CMIP6"))
    clone = query.clone()
    assert query.asdict() == clone.asdict()
    clone.selection.variable_id = "tas"
    assert query.asdict() != clone.asdict()


def test_combine():
    # various ways to create subqueries
    a = Query(selection=dict(project="CMIP6"))
    b = Query(selection=dict(mip_era="CMIP6"))
    c = Query(options=dict(distrib=None))
    d = Query(options=dict(distrib=True))
    ab_dict = (a << b).selection.asdict()
    ba_dict = (b << a).selection.asdict()
    abcd_dict = (a << b << c << d).asdict()
    dcba_dict = (d << c << b << a).asdict()
    assert ab_dict == ba_dict == dict(project="CMIP6", mip_era="CMIP6")
    assert abcd_dict == dict(selection=ab_dict, options=dict(distrib=True))
    assert dcba_dict == dict(selection=ab_dict, options=dict(distrib=None))


def test_combine_raise():
    a = Query(selection=dict(project="CMIP5"))
    b = Query(selection=dict(project="CMIP6"))
    with pytest.raises(AlreadySetFacet):
        a << b


def test_combine_removes_require():
    a = Query(selection=dict(project="CMIP6"))
    a.compute_sha()
    b = Query(require=a.sha, selection=dict(variable_id="tas"))
    ab = a << b
    ba = b << a
    assert ab.require is None
    assert ba.require == a.sha
