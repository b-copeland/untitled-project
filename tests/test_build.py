import pytest
import json
import datetime
from api.untitledapp import REQUESTS_SESSION
import api.untitledapp.build as app_build

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