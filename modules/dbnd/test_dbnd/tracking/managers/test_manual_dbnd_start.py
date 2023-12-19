# © Copyright Databand.ai, an IBM Company 2022
"""
If you want to debug these tests, you can easily run this file as a Run
"""
import logging
import os
import re
import sys

import pytest

from mock import patch

from dbnd import dbnd_tracking_start, dbnd_tracking_stop, log_metric, task
from dbnd._core.tracking.script_tracking_manager import (
    _calculate_root_task_name_from_env_or_script_path,
)
from dbnd.testing.helpers import run_dbnd_subprocess


FAIL_F2 = "fail_f2"
FAIL_MAIN = "fail_main"
USE_DBND_START = "use_dbnd_start"
USE_DBND_STOP = "use_dbnd_stop"
RUN_TASK_DECORATED_METHOD = "run_task_decorated_method"

RE_TASK_COMPLETED = r"Task {}[_\w]*.+ has been completed!"
RE_TASK_FAILED = r"Task {}[_\w]*.+ has failed!"
RE_F_RUNNING = r"Running {} function"

CURRENT_PY_FILE = __file__.replace(".pyc", ".py")


class MyClass:
    @task
    def do_something(self):
        log_metric("evgeny", 10)


def run_dbnd_subprocess__current_file(args, env=None, **kwargs):
    args = args or []
    env = env or os.environ.copy()
    env["DBND__CORE__TRACKER"] = "['console']"
    env["DBND__CORE__TRACKER_API"] = "web"
    env["DBND__VERBOSE"] = "True"
    return run_dbnd_subprocess(
        [sys.executable, CURRENT_PY_FILE] + args, env=env, **kwargs
    )


def _assert_output(reg_exp, output, count=1):
    logging.info("RE: %s", reg_exp)
    assert count == len(re.findall(reg_exp, output))


class TestManualDbndStart(object):
    auto_task_name = os.path.basename(__file__)
    expected_task_names = (("f1", 1), ("f2", 3))

    def test_manual_dbnd_start(self, set_verbose_mode):
        result = run_dbnd_subprocess__current_file(args=[USE_DBND_START])

        for task_name, count in self.expected_task_names + ((self.auto_task_name, 1),):
            assert count == len(
                re.findall(RE_TASK_COMPLETED.format(task_name), result)
            ), task_name

        for task_name, count in self.expected_task_names:
            assert count == len(
                re.findall(RE_F_RUNNING.format(task_name), result)
            ), task_name

    def test_no_dbnd_start(self):
        result = run_dbnd_subprocess__current_file([])
        assert "Running Databand!" not in result

        for task_name, count in self.expected_task_names + ((self.auto_task_name, 1),):
            assert 0 == len(re.findall(r"Task {}__\w+".format(task_name), result))

        for task_name, count in self.expected_task_names:
            _assert_output(RE_F_RUNNING.format(task_name), result, count)

    def test_manual_dbnd_start_manual_stop(self):
        run_dbnd_subprocess__current_file([USE_DBND_START, USE_DBND_STOP])

    def test_manual_dbnd_start_fail_main(self):
        result = run_dbnd_subprocess__current_file(
            [USE_DBND_START, FAIL_MAIN], retcode=1
        )
        assert "main bummer!" in result
        _assert_output(RE_TASK_FAILED.format("test_manual_dbnd_start.py"), result)

    def test_manual_dbnd_start_fail_f2(self):
        result = run_dbnd_subprocess__current_file([USE_DBND_START, FAIL_F2], retcode=1)
        assert "f2 bummer!" in result

        for task_name, count in self.expected_task_names:
            _assert_output(RE_TASK_FAILED.format(task_name), result)

    def test_manual_dbnd_start_with_decorated_function(self):
        # This test is checking that decorating a function in class works
        result = run_dbnd_subprocess__current_file(
            [USE_DBND_START, USE_DBND_STOP, RUN_TASK_DECORATED_METHOD]
        )
        assert "evgeny=10" in result
        # Verify that we did not send the 'self' param to the web server and received KeyError
        assert "KeyError:" not in result

    def test_custom_job_name(self, set_verbose_mode):
        env = os.environ.copy()
        env["DBND__TRACKING__JOB"] = "test_job_name"
        result = run_dbnd_subprocess__current_file(args=[USE_DBND_START], env=env)
        assert "job_name=test_job_name" in result

    def test_custom_project_name(self, set_verbose_mode):
        env = os.environ.copy()
        env["DBND__TRACKING__PROJECT"] = "test_project"
        result = run_dbnd_subprocess__current_file(args=[USE_DBND_START], env=env)

        assert "project_name=test_project" in result

    @pytest.mark.parametrize(
        "argv,expected",
        [
            (["abc"], "abc"),
            (None, "unknown"),
            (["abc_123456789.py"], "abc"),
            (["abc_123.py"], "abc_123.py"),
            (["abc_20230606T1344566222.py"], "abc"),
        ],
    )
    def test_clean_script_name_from_date(self, argv, expected):
        with patch.object(sys, "argv", argv):
            actual = _calculate_root_task_name_from_env_or_script_path(None)
            assert actual == expected


@task
def f2(p):
    print("Running f2 function")

    if FAIL_F2 in sys.argv:
        raise Exception("f2 bummer!")

    return p * p


@task
def f1():
    print("Running f1 function")
    sum = 0

    for i in range(1, 4):
        sum += f2(i)

    assert sum == 14


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if USE_DBND_START in sys.argv:
        logging.info("Explicitly starting the tracking")
        dbnd_tracking_start()
        dbnd_tracking_start()

    f1()
    logging.info(
        "Done, you should see this message, otherwise, tests will fail, as console writer will not work"
    )
    print("Done")

    if FAIL_MAIN in sys.argv:
        raise Exception("main bummer!")

    if RUN_TASK_DECORATED_METHOD:
        MyClass().do_something()

    if USE_DBND_STOP in sys.argv:
        dbnd_tracking_stop()
        dbnd_tracking_stop()
