# © Copyright Databand.ai, an IBM Company 2022
from typing import Generator, List, Tuple
from unittest.mock import patch

import mock
import pytest

from attr import evolve

from airflow_monitor.shared.adapter.adapter import (
    Adapter,
    Assets,
    AssetState,
    AssetToState,
)
from airflow_monitor.shared.base_server_monitor_config import BaseServerConfig
from airflow_monitor.shared.base_tracking_service import BaseTrackingService
from airflow_monitor.shared.generic_syncer import GenericSyncer
from airflow_monitor.shared.integration_management_service import (
    IntegrationManagementService,
)
from dbnd._core.utils.uid_utils import get_uuid


INTEGRATION_UID = get_uuid()


class MockAdapter(Adapter):
    def __init__(self):
        super(MockAdapter, self).__init__()
        self.cursor: int = 0
        self.next_page: int = 0
        self.error: Exception = None

    def set_error(self, error: Exception) -> None:
        self.error = error

    def init_assets_for_cursor(
        self, cursor: int, batch_size: int
    ) -> Generator[Tuple[Assets, int], None, None]:
        while True:
            yield (
                Assets(
                    data=None,
                    assets_to_state=[
                        AssetToState(
                            asset_id=self.cursor + self.next_page, state=AssetState.INIT
                        )
                    ],
                ),
                self.cursor,
            )
            self.cursor += 1
            if self.next_page == 1:
                break
            self.next_page = 1

    def init_cursor(self) -> int:
        return self.cursor

    def get_assets_data(self, assets: Assets) -> Assets:
        if self.error:
            raise self.error
        if assets.assets_to_state:
            return Assets(
                data={
                    "data": [
                        asset_to_state.asset_id
                        for asset_to_state in assets.assets_to_state
                    ]
                },
                assets_to_state=[
                    evolve(asset_to_state, state=AssetState.FAILED_REQUEST)
                    if asset_to_state.state == AssetState.FAILED_REQUEST
                    else evolve(asset_to_state, state=AssetState.FINISHED)
                    for asset_to_state in assets.assets_to_state
                ],
            )
        else:
            return Assets(data={}, assets_to_state=[])


class MockTrackingService(BaseTrackingService):
    def __init__(self, monitor_type: str, tracking_source_uid: str):
        BaseTrackingService.__init__(self, monitor_type, tracking_source_uid)
        self.sent_data = []
        self.assets_state = []
        self.last_seen_run_id = None
        self.last_cursor = None
        self.last_state = None
        self.counter = 0
        self.error = None
        self.active_runs = None

    def save_tracking_data(self, assets_data):
        self.sent_data.append(assets_data)
        if self.error and self.counter == 1:
            raise self.error
        self.counter += 1

    def save_assets_state(
        self, integration_id, syncer_instance_id, assets_to_state: List[AssetToState]
    ):
        self.assets_state.append(assets_to_state)
        return

    def update_last_cursor(self, integration_id, syncer_instance_id, state, data):
        self.last_cursor = data
        self.last_state = state

    def get_last_cursor_and_state(self) -> (int, str):
        return self.last_cursor, self.last_state

    def get_last_cursor(self, integration_id, syncer_instance_id) -> int:
        return self.last_cursor

    def get_active_assets(self, integration_id, syncer_instance_id) -> List[dict]:
        assets_to_state = []
        if self.active_runs:
            for asset_to_state_dict in self.active_runs:
                try:
                    assets_to_state.append(AssetToState.from_dict(asset_to_state_dict))
                except:
                    continue
            return assets_to_state

    def set_error(self, error):
        self.error = error

    def set_active_runs(self, active_runs):
        self.active_runs = active_runs


class MockIntegrationManagementService(IntegrationManagementService):
    def report_monitor_time_data(self, integration_uid, synced_new_data=False):
        pass

    def report_metadata(self, integration_uid, metadata):
        pass

    def report_error(self, integration_uid, full_function_name, err_message):
        pass


@pytest.fixture
def mock_tracking_service() -> MockTrackingService:
    yield MockTrackingService("integration", "12345")


@pytest.fixture
def mock_server_config() -> BaseServerConfig:
    yield BaseServerConfig(
        uid=INTEGRATION_UID,
        source_name="test_syncer",
        source_type="integration",
        tracking_source_uid="12345",
        sync_interval=10,
    )


@pytest.fixture
def mock_adapter() -> MockAdapter:
    yield MockAdapter()


@pytest.fixture
def mock_integration_management_service() -> MockIntegrationManagementService:
    yield MockIntegrationManagementService("integration", BaseServerConfig)


@pytest.fixture
def generic_runtime_syncer(
    mock_tracking_service,
    mock_server_config,
    mock_integration_management_service,
    mock_adapter,
):
    syncer = GenericSyncer(
        config=mock_server_config,
        tracking_service=mock_tracking_service,
        integration_management_service=mock_integration_management_service,
        adapter=mock_adapter,
        syncer_instance_id="123",
    )
    with patch.object(syncer, "refresh_config", new=lambda *args: None), patch.object(
        syncer, "tracking_service", wraps=syncer.tracking_service
    ), patch.object(
        syncer,
        "integration_management_service",
        wraps=syncer.integration_management_service,
    ):
        yield syncer


class TestGenericSyncer:
    def test_sync_get_data_with_pagination(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        generic_runtime_syncer.sync_once()
        assert mock_tracking_service.get_last_cursor_and_state() == (0, "init")
        generic_runtime_syncer.sync_once()
        assert mock_tracking_service.get_last_cursor_and_state() == (1, "update")
        generic_runtime_syncer.sync_once()
        assert mock_tracking_service.get_last_cursor_and_state() == (2, "update")
        assert mock_tracking_service.sent_data == [
            {"data": [0]},
            {"data": [2]},
            {"data": [3]},
        ]

    def test_sync_get_data_exception_on_save_data(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        mock_tracking_service.set_error(Exception("test"))
        generic_runtime_syncer.sync_once()
        assert mock_tracking_service.get_last_cursor_and_state() == (0, "init")
        generic_runtime_syncer.sync_once()
        # last cursor is not updated after failure
        assert mock_tracking_service.get_last_cursor_and_state() == (0, "init")
        generic_runtime_syncer.sync_once()
        # call get data with same cursor before failure
        assert mock_tracking_service.get_last_cursor_and_state() == (0, "init")
        assert mock_tracking_service.sent_data == [
            {"data": [0]},
            {"data": [2]},
            {"data": [2]},
        ]

    def test_sync_get_and_update_data_with_pagination(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        mock_tracking_service.set_active_runs(
            [
                {"asset_uri": 3, "state": "active"},
                {"asset_uri": 4, "state": "active"},
                {"asset_uri": 5, "state": "active"},
                {"asset_uri": 6, "state": "active"},
                {"asset_uri": 7, "state": "active"},
                {"asset_uri": 8, "state": "active"},
            ]
        )
        generic_runtime_syncer.sync_once()
        assert mock_tracking_service.get_last_cursor_and_state() == (0, "init")
        generic_runtime_syncer.sync_once()
        assert mock_tracking_service.assets_state == [
            [
                AssetToState(asset_id=3, state=AssetState.FINISHED),
                AssetToState(asset_id=4, state=AssetState.FINISHED),
                AssetToState(asset_id=5, state=AssetState.FINISHED),
                AssetToState(asset_id=6, state=AssetState.FINISHED),
                AssetToState(asset_id=7, state=AssetState.FINISHED),
                AssetToState(asset_id=8, state=AssetState.FINISHED),
            ],
            [AssetToState(asset_id=0, state=AssetState.FINISHED)],
            [AssetToState(asset_id=2, state=AssetState.FINISHED)],
        ]
        assert mock_tracking_service.sent_data == [
            {"data": [3, 4, 5, 6, 7, 8]},
            {"data": [0]},
            {"data": [2]},
        ]

    def test_sync_get_and_update_data_with_pagination_and_unknown_state(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        mock_tracking_service.set_active_runs(
            [
                {"asset_uri": 3, "state": "wow", "data": {"retry_count": 2}},
                {"asset_uri": 4, "state": "active"},
                {"asset_uri": 5, "state": "active"},
                {"asset_uri": 6, "state": "active"},
                {"asset_uri": 7, "state": "active"},
                {"asset_uri": 8, "state": "active"},
            ]
        )
        generic_runtime_syncer.sync_once()
        assert mock_tracking_service.get_last_cursor_and_state() == (0, "init")
        generic_runtime_syncer.sync_once()
        assert mock_tracking_service.assets_state == [
            [
                AssetToState(asset_id=4, state=AssetState.FINISHED),
                AssetToState(asset_id=5, state=AssetState.FINISHED),
                AssetToState(asset_id=6, state=AssetState.FINISHED),
                AssetToState(asset_id=7, state=AssetState.FINISHED),
                AssetToState(asset_id=8, state=AssetState.FINISHED),
            ],
            [AssetToState(asset_id=0, state=AssetState.FINISHED)],
            [AssetToState(asset_id=2, state=AssetState.FINISHED)],
        ]
        assert mock_tracking_service.sent_data == [
            {"data": [4, 5, 6, 7, 8]},
            {"data": [0]},
            {"data": [2]},
        ]

    def test_sync_get_and_update_data_with_pagination_and_failed_request(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        mock_tracking_service.set_active_runs(
            [
                {"asset_uri": 3, "state": "failed_request", "data": {"retry_count": 1}},
                {"asset_uri": 4, "state": "active"},
                {"asset_uri": 5, "state": "active"},
                {"asset_uri": 6, "state": "active"},
                {"asset_uri": 7, "state": "active"},
                {"asset_uri": 8, "state": "active"},
            ]
        )
        generic_runtime_syncer.sync_once()
        assert mock_tracking_service.get_last_cursor_and_state() == (0, "init")
        generic_runtime_syncer.sync_once()
        assert mock_tracking_service.assets_state == [
            [
                AssetToState(
                    asset_id=3, state=AssetState.FAILED_REQUEST, retry_count=2
                ),
                AssetToState(asset_id=4, state=AssetState.FINISHED),
                AssetToState(asset_id=5, state=AssetState.FINISHED),
                AssetToState(asset_id=6, state=AssetState.FINISHED),
                AssetToState(asset_id=7, state=AssetState.FINISHED),
                AssetToState(asset_id=8, state=AssetState.FINISHED),
            ],
            [AssetToState(asset_id=0, state=AssetState.FINISHED)],
            [AssetToState(asset_id=2, state=AssetState.FINISHED)],
        ]

    def test_sync_once_total_duration_metric(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        with mock.patch(
            "airflow_monitor.shared.generic_syncer_metrics.generic_syncer_sync_once_total_duration_seconds.labels"
        ) as generic_syncer_sync_once_total_duration_seconds:
            generic_runtime_syncer.sync_once()
            generic_runtime_syncer.sync_once()
            generic_syncer_sync_once_total_duration_seconds.assert_called_with(
                integration_id=INTEGRATION_UID, syncer_instance_id="123"
            )
            # generic_syncer_sync_once_total_duration_seconds.labels
            labels = generic_syncer_sync_once_total_duration_seconds.return_value
            # sync once duration value is more then 0 seconds
            assert labels.method_calls[0].args[0] > 0

    def test_sync_once_batch_duration_metric(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        with mock.patch(
            "airflow_monitor.shared.generic_syncer_metrics.generic_syncer_sync_once_batch_duration_seconds.labels"
        ) as generic_syncer_sync_once_batch_duration_seconds:
            generic_runtime_syncer.sync_once()
            generic_runtime_syncer.sync_once()
            generic_syncer_sync_once_batch_duration_seconds.assert_called_with(
                integration_id=INTEGRATION_UID, syncer_instance_id="123"
            )
            # generic_syncer_sync_once_batch_duration_seconds.labels
            labels = generic_syncer_sync_once_batch_duration_seconds.return_value
            # batch duration value is more then 0 seconds
            assert labels.method_calls[0].args[0] > 0

    def test_save_tracking_data_response_duration_metric(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        with mock.patch(
            "airflow_monitor.shared.generic_syncer_metrics.generic_syncer_save_tracking_data_response_time_seconds.labels"
        ) as generic_syncer_save_tracking_data_response_time_seconds:
            generic_runtime_syncer.sync_once()
            generic_runtime_syncer.sync_once()
            generic_syncer_save_tracking_data_response_time_seconds.assert_called_with(
                integration_id=INTEGRATION_UID, syncer_instance_id="123"
            )
            # generic_syncer_save_tracking_data_response_time_seconds.labels
            labels = (
                generic_syncer_save_tracking_data_response_time_seconds.return_value
            )
            # save tracking response duration value is more then 0 seconds
            assert labels.method_calls[0].args[0] > 0

    def test_total_assets_data_size_metric(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        with mock.patch(
            "airflow_monitor.shared.generic_syncer_metrics.generic_syncer_total_assets_size.labels"
        ) as generic_syncer_total_assets_size:
            generic_runtime_syncer.sync_once()
            generic_runtime_syncer.sync_once()
            generic_syncer_total_assets_size.assert_called_with(
                integration_id=INTEGRATION_UID, syncer_instance_id="123"
            )
            # generic_syncer_total_assets_size.labels
            labels = generic_syncer_total_assets_size.return_value
            # total assets size value
            assert labels.method_calls[0].args[0] == 2

    def test_report_assets_data_batch_size_bytes_metric(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        with mock.patch(
            "airflow_monitor.shared.generic_syncer_metrics.generic_syncer_assets_data_batch_size_bytes.labels"
        ) as generic_syncer_assets_data_batch_size_bytes:
            generic_runtime_syncer.sync_once()
            generic_runtime_syncer.sync_once()
            generic_syncer_assets_data_batch_size_bytes.assert_called_with(
                integration_id=INTEGRATION_UID, syncer_instance_id="123"
            )
            # report_assets_data_batch_size_bytes.labels
            labels = generic_syncer_assets_data_batch_size_bytes.return_value
            # data batch size bytes value
            assert labels.method_calls[0].args[0] > 0

    def test_report_get_assets_data_error_metric(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        generic_runtime_syncer.adapter.set_error(Exception("mock error"))
        with mock.patch(
            "airflow_monitor.shared.generic_syncer_metrics.generic_syncer_assets_data_error_counter.labels"
        ) as generic_syncer_assets_data_error_counter:
            generic_runtime_syncer.sync_once()
            generic_runtime_syncer.sync_once()
            generic_syncer_assets_data_error_counter.assert_called_with(
                integration_id=INTEGRATION_UID,
                syncer_instance_id="123",
                error_message="mock error",
            )

    def test_report_generic_syncer_error_metric(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        mock_tracking_service.set_error(Exception("test"))
        with mock.patch(
            "airflow_monitor.shared.generic_syncer_metrics.generic_syncer_error_counter.labels"
        ) as generic_syncer_assets_data_error_counter:
            generic_runtime_syncer.sync_once()
            generic_runtime_syncer.sync_once()
            generic_syncer_assets_data_error_counter.assert_called_with(
                integration_id=INTEGRATION_UID,
                syncer_instance_id="123",
                error_message="test",
            )

    def test_report_total_failed_assets_requests_metric(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        mock_tracking_service.set_active_runs(
            [
                {"asset_uri": 3, "state": "failed_request", "data": {"retry_count": 1}},
                {"asset_uri": 4, "state": "failed_request", "data": {"retry_count": 1}},
            ]
        )
        with mock.patch(
            "airflow_monitor.shared.generic_syncer_metrics.generic_syncer_total_failed_assets_requests.labels"
        ) as generic_syncer_total_failed_assets_requests:
            generic_runtime_syncer.sync_once()
            generic_runtime_syncer.sync_once()
            generic_syncer_total_failed_assets_requests.assert_called_with(
                integration_id=INTEGRATION_UID, syncer_instance_id="123"
            )
            labels = generic_syncer_total_failed_assets_requests.return_value
            # total failed assets requests value
            assert labels.method_calls[0].args[0] == 2

    def test_report_total_max_retry_assets_requests_metric(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        mock_tracking_service.set_active_runs(
            [
                {"asset_uri": 3, "state": "failed_request", "data": {"retry_count": 6}},
                {"asset_uri": 4, "state": "failed_request", "data": {"retry_count": 6}},
            ]
        )
        with mock.patch(
            "airflow_monitor.shared.generic_syncer_metrics.generic_syncer_total_max_retry_assets_requests.labels"
        ) as generic_syncer_total_max_retry_assets_requests:
            generic_runtime_syncer.sync_once()
            generic_runtime_syncer.sync_once()
            generic_syncer_total_max_retry_assets_requests.assert_called_with(
                integration_id=INTEGRATION_UID, syncer_instance_id="123"
            )
            labels = generic_syncer_total_max_retry_assets_requests.return_value
            # total max retry assets requests value
            assert labels.method_calls[0].args[0] == 2

    def test_get_assets_data_response_duration_metric(
        self,
        generic_runtime_syncer: GenericSyncer,
        mock_tracking_service: MockTrackingService,
    ):
        with mock.patch(
            "airflow_monitor.shared.generic_syncer_metrics.generic_syncer_get_assets_data_response_time_seconds.labels"
        ) as generic_syncer_get_assets_data_response_time_seconds:
            generic_runtime_syncer.sync_once()
            generic_runtime_syncer.sync_once()
            generic_syncer_get_assets_data_response_time_seconds.assert_called_with(
                integration_id=INTEGRATION_UID, syncer_instance_id="123"
            )
            # generic_syncer_save_tracking_data_response_time_seconds.labels
            labels = generic_syncer_get_assets_data_response_time_seconds.return_value
            # get_assets_data_duration value is more then 0 seconds
            assert labels.method_calls[0].args[0] > 0
