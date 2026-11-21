import pytest
import json
import datetime
from untitledapp import REQUESTS_SESSION
import untitledapp.build as app_build

def test__divide_across_splits():
    splits = ["split_1", "split_2", "split_3"]

    assert app_build._divide_across_splits(splits, 3) == {
        "split_1": 1,
        "split_2": 1,
        "split_3": 1,
    }
    
    assert app_build._divide_across_splits(splits, 5) == {
        "split_1": 2,
        "split_2": 2,
        "split_3": 1,
    }

def test__make_time_splits():

    min_time = 1
    max_time = 3

    with pytest.raises(AssertionError):
        app_build._make_time_splits(min_time, max_time, 3)

    two_splits = app_build._make_time_splits(min_time, max_time, 2)
    assert two_splits == [3.0, 1.0]

    four_splits = app_build._make_time_splits(min_time, max_time, 4)
    expected_splits = [2.333, 1.667, 3.0, 1.0]
    for test_split, expected_split in zip(four_splits, expected_splits):
        assert round(test_split, 3) == expected_split
    
    twelve_splits = app_build._make_time_splits(1, 23, 12)
    assert twelve_splits == [13.0, 11.0, 15.0, 9.0, 17.0, 7.0, 19.0, 5.0, 21.0, 3.0, 23.0, 1.0]


def test_engineers_can_not_be_disbanded():
    kd_info = {"units": {"attack": 10, "engineers": 5}}
    assert app_build._validate_disband(kd_info, {"engineers": 1}) == (False, "You can't disband engineers")
    assert app_build._validate_disband(kd_info, {"attack": 3, "engineers": 1}) == (False, "You can't disband engineers")
    assert app_build._validate_disband(kd_info, {"attack": 3}) == (True, "")

def test_queue_total_counts_every_item_not_every_entry():
    import untitledapp.getters as getters
    assert getters._queue_total([]) == 0
    assert getters._queue_total([{"time": "t1", "homes": 3, "mines": 2}, {"time": "t2", "amount": 4.0}]) == 9


def test_queue_pages_show_the_total_number_of_items(app, client, jwt1):
    """The parenthesis on the Build page is the items in the queue: two builds of 3 and 2 homes are 5, not 2."""
    from tests.test_concurrency import _set_up_kingdom
    _set_up_kingdom(money=10**7)
    headers = {"Authorization": f"Bearer {jwt1}"}
    for count in (3, 2):
        response = client.post("/api/structures", json={"homes": count}, headers=headers)
        assert response.status_code == 200, response.get_json()
    structures = client.get("/api/structures", headers=headers).get_json()
    assert structures["total_queue"] == 5
    assert structures["len_queue"] >= 2
    for path in ("/api/settle", "/api/mobis", "/api/engineers", "/api/missiles"):
        assert client.get(path, headers=headers).get_json()["total_queue"] == 0, path
