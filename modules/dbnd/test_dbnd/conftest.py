# © Copyright Databand.ai, an IBM Company 2022

from __future__ import print_function

from datetime import datetime

import pytest

from pytest import fixture

# import dbnd should be first!
import dbnd
import dbnd._core.utils.basics.environ_utils

from dbnd._core.configuration.environ_config import (
    ENV_DBND__DISABLE_PLUGGY_ENTRYPOINT_LOADING,
    ENV_DBND__ORCHESTRATION__NO_PLUGINS,
    reset_dbnd_project_config,
)
from dbnd._core.context.use_dbnd_run import disable_airflow_package
from dbnd._core.utils.basics.environ_utils import set_on
from dbnd.testing.test_config_setter import add_test_configuration
from targets import target


# we want to test only this module
# However, this import runs in separate space from test run -> this global will not be visible to your test
# get_dbnd_project_config().is_no_dbnd_orchestration = True

# if enabled will pring much better info on tests
# os.environ["DBND__VERBOSE"] = "True"
# set_on(ENV_DBND__NO_ORCHESTRATION)
set_on(ENV_DBND__ORCHESTRATION__NO_PLUGINS)
set_on(ENV_DBND__DISABLE_PLUGGY_ENTRYPOINT_LOADING)

# DISABLE AIRFLOW, we don't test it in this module!
disable_airflow_package()

# all env changes should be active for current project config
reset_dbnd_project_config()

pytest_plugins = [
    "dbnd.testing.pytest_dbnd_plugin",
    "dbnd.testing.pytest_dbnd_markers_plugin",
    "dbnd.testing.pytest_dbnd_home_plugin",
]
__all__ = ["dbnd"]

try:
    import matplotlib

    # see:
    # https://stackoverflow.com/questions/37604289/tkinter-tclerror-no-display-name-and-no-display-environment-variable
    # https://markhneedham.com/blog/2018/05/04/python-runtime-error-osx-matplotlib-not-installed-as-framework-mac/
    matplotlib.use("Agg")
except ModuleNotFoundError:
    pass

# by default exclude tests marked with following marks from execution:
markers_to_exlude_by_default = ["dbnd_integration"]


def pytest_configure(config):
    add_test_configuration(__file__)
    markexpr = getattr(config.option, "markexpr", "")
    marks = [markexpr] if markexpr else []
    for mark in markers_to_exlude_by_default:
        if mark not in markexpr:
            marks.append("not %s" % mark)
    new_markexpr = " and ".join(marks)
    setattr(config.option, "markexpr", new_markexpr)


@pytest.fixture
def pandas_data_frame():
    import pandas as pd

    df = pd.DataFrame(
        {
            "Names": pd.Series(["Bob", "Jessica", "Mary", "John", "Mel"], dtype="str"),
            "Births": pd.Series([968, 155, 77, 578, 973], dtype="int"),
            # "Weights": pd.Series([12.3, 23.4, 45.6, 56.7, 67.8], dtype="float"),
            "Married": pd.Series([True, False, True, False, True], dtype="bool"),
        }
    )
    return df


@pytest.fixture
def df_categorical():
    import pandas as pd

    return pd.DataFrame(
        {"A": [1, 2, 3], "B": pd.Series(list("xyz")).astype("category")}
    )


@pytest.fixture
def pandas_data_frame_index(pandas_data_frame):
    return pandas_data_frame.set_index("Names")


@pytest.fixture
def pandas_data_frame_on_disk(tmpdir, pandas_data_frame):
    t = target(tmpdir / "df.csv")
    t.write_df(pandas_data_frame)
    return pandas_data_frame, t


@fixture
def partitioned_data_target_date():
    return datetime.date(year=2018, month=9, day=3)
