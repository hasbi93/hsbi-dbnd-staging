# © Copyright Databand.ai, an IBM Company 2022

from __future__ import absolute_import

import os

import pytest

from pytest import fixture


@fixture
def simple_df():
    import pandas as pd

    return pd.DataFrame(data=[[1, 1], [2, 2]], columns=["c1", "c2"])


@fixture
def pandas_data_frame():
    import pandas as pd

    names = ["Bob", "Jessica", "Mary", "John", "Mel"]
    births = [968, 155, 77, 578, 973]
    df = pd.DataFrame(data=list(zip(names, births)), columns=["Names", "Births"])
    return df


@fixture
def s1_root_dir(tmpdir):
    dir_path = str(tmpdir.join("dir.csv/"))
    os.makedirs(dir_path)
    return dir_path + "/"


@fixture
def s1_file_1_csv(s1_root_dir, simple_df):
    path = os.path.join(s1_root_dir, "1.csv")
    simple_df.head(1).to_csv(path, index=False)
    return path


@fixture
def s1_file_2_csv(s1_root_dir, simple_df):
    path = os.path.join(s1_root_dir, "2.csv")
    simple_df.tail(1).to_csv(path, index=False)
    return path


@fixture
def s1_dir_with_csv(s1_root_dir, s1_file_1_csv, s1_file_2_csv):
    return s1_root_dir, s1_file_1_csv, s1_file_2_csv


@pytest.fixture()
def mock_target_fs():
    from targets.fs.mock import MockFileSystem

    MockFileSystem.instance.clear()
    yield MockFileSystem.instance
    MockFileSystem.instance.clear()
