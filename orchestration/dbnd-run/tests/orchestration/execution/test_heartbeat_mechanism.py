# © Copyright Databand.ai, an IBM Company 2022

import logging

from mock import MagicMock, PropertyMock, patch

from dbnd import new_dbnd_context
from dbnd._core.configuration.environ_config import ENV_DBND__ORCHESTRATION__NO_PLUGINS
from dbnd._core.run.databand_run import DatabandRun
from dbnd_run.run_executor.heartbeat_sender import start_heartbeat_sender
from dbnd_run.run_executor.run_executor import RunExecutor
from dbnd_run.run_settings import RunConfig


logger = logging.getLogger(__name__)


class TestHeartbeat(object):
    def test_start_heartbeat_sender(self):
        # we are not going to mock settings as that's too much work
        with new_dbnd_context(
            conf={
                RunConfig.heartbeat_interval_s: 5,
                RunConfig.hearbeat_disable_plugins: 5,
            }
        ) as dc:
            run = MagicMock(DatabandRun)
            type(run).run_uid = PropertyMock(return_value="testtest")
            type(run).context = PropertyMock(return_value=dc)

            run_executor = MagicMock(RunExecutor)
            type(run_executor).run = PropertyMock(return_value=run)
            type(run_executor).run_config = RunConfig()
            type(run_executor).run_local_root = PropertyMock(
                return_value=dc.run_settings.env.dbnd_local_root
            )
            with patch("subprocess.Popen") as mock_popen:
                hearbeat = start_heartbeat_sender(run_executor)
                with hearbeat:
                    logger.info("running with heartbeat")
                mock_popen.assert_called_once()
                call = mock_popen.call_args_list[-1]

                assert ENV_DBND__ORCHESTRATION__NO_PLUGINS in call.kwargs["env"]
                assert "testtest" in call.args[0]
