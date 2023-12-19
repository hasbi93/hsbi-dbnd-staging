# © Copyright Databand.ai, an IBM Company 2022

import pytest

from more_itertools import one

from dbnd import dataset_op_logger, log_dataset_op, task
from dbnd._core.constants import DbndDatasetOperationType, DbndTargetOperationStatus
from dbnd.testing.helpers_mocks import set_tracking_context
from targets import target
from test_dbnd.tracking.tracking_helpers import get_log_datasets, get_log_metrics


@pytest.mark.usefixtures(set_tracking_context.__name__)
class TestTrackingDatasets(object):
    def test_log_dataset_with_row_and_column_count(self, mock_channel_tracker):
        @task()
        def task_with_log_datasets():
            log_dataset_op(
                "location://path/to/value.csv",
                DbndDatasetOperationType.read,
                row_count=987,
                column_count=4,
            )

        task_with_log_datasets()

        log_dataset_arg = one(get_log_datasets(mock_channel_tracker))
        assert log_dataset_arg.operation_path == "location://path/to/value.csv"
        assert log_dataset_arg.operation_type == DbndDatasetOperationType.read.value
        assert log_dataset_arg.operation_status == DbndTargetOperationStatus.OK.value
        assert log_dataset_arg.value_preview == ""
        assert log_dataset_arg.data_dimensions == [987, 4]
        assert log_dataset_arg.data_schema is None

    def test_log_dataset(self, mock_channel_tracker):
        @task()
        def taskWithLogDatasets():  # Deliberately use camelCase here
            log_dataset_op(
                "location://path/to/value.csv",
                DbndDatasetOperationType.read,
                with_schema=False,
            )

        taskWithLogDatasets()

        log_dataset_arg = one(get_log_datasets(mock_channel_tracker))
        assert log_dataset_arg.operation_path == "location://path/to/value.csv"
        assert log_dataset_arg.operation_type == DbndDatasetOperationType.read.value
        assert log_dataset_arg.operation_status == DbndTargetOperationStatus.OK.value
        assert log_dataset_arg.value_preview == ""
        assert log_dataset_arg.data_dimensions is None
        assert log_dataset_arg.data_schema is None
        assert log_dataset_arg.task_run_name == "taskWithLogDatasets"

        # no metrics reported
        log_metrics_args = list(get_log_metrics(mock_channel_tracker))
        assert len(log_metrics_args) == 0

    def test_log_dataset_with_wrapper(self, mock_channel_tracker, pandas_data_frame):
        @task()
        def task_with_log_dataset_wrapper():
            with dataset_op_logger(
                op_path=target("/path/to/value.csv"), op_type="read", with_preview=True
            ) as logger:
                logger.set(data=pandas_data_frame)

        task_with_log_dataset_wrapper()

        log_dataset_arg = one(get_log_datasets(mock_channel_tracker))
        assert log_dataset_arg.operation_path == "/path/to/value.csv"
        assert log_dataset_arg.operation_type == DbndDatasetOperationType.read.value
        assert log_dataset_arg.operation_status == DbndTargetOperationStatus.OK.value
        assert log_dataset_arg.value_preview is not None
        assert log_dataset_arg.data_dimensions == [5, 3]
        assert set(log_dataset_arg.data_schema.keys()) == {
            "columns",
            "dtypes",
            "shape",
            "size.bytes",
            "type",
        }

    def test_log_dataset_override_row_count(
        self, mock_channel_tracker, pandas_data_frame
    ):
        @task()
        def task_with_log_dataset_wrapper():
            with dataset_op_logger(
                op_path=target("/path/to/value.csv"), op_type="read", with_preview=True
            ) as logger:
                logger.set(data=pandas_data_frame, row_count=999)

        task_with_log_dataset_wrapper()

        log_dataset_arg = one(get_log_datasets(mock_channel_tracker))
        assert log_dataset_arg.operation_path == "/path/to/value.csv"
        assert log_dataset_arg.operation_type == DbndDatasetOperationType.read.value
        assert log_dataset_arg.operation_status == DbndTargetOperationStatus.OK.value
        assert log_dataset_arg.value_preview is not None
        assert log_dataset_arg.data_dimensions == [999, 3]
        assert set(log_dataset_arg.data_schema.keys()) == {
            "columns",
            "dtypes",
            "shape",
            "size.bytes",
            "type",
        }

    def test_log_dataset_override_col_count(
        self, mock_channel_tracker, pandas_data_frame
    ):
        @task()
        def task_with_log_dataset_wrapper():
            with dataset_op_logger(
                op_path=target("/path/to/value.csv"), op_type="read", with_preview=True
            ) as logger:
                logger.set(data=pandas_data_frame, column_count=8)

        task_with_log_dataset_wrapper()

        log_dataset_arg = one(get_log_datasets(mock_channel_tracker))
        assert log_dataset_arg.operation_path == "/path/to/value.csv"
        assert log_dataset_arg.operation_type == DbndDatasetOperationType.read.value
        assert log_dataset_arg.operation_status == DbndTargetOperationStatus.OK.value
        assert log_dataset_arg.value_preview is not None
        assert log_dataset_arg.data_dimensions == [5, 8]
        assert set(log_dataset_arg.data_schema.keys()) == {
            "columns",
            "dtypes",
            "shape",
            "size.bytes",
            "type",
        }

    def test_failed_target_with_wrapper(self, mock_channel_tracker, pandas_data_frame):
        @task()
        def task_with_log_dataset_wrapper():
            with dataset_op_logger(
                op_path=target("/path/to/value.csv"),
                data=pandas_data_frame,
                op_type="write",
                with_preview=True,
            ) as logger:
                ans = 42
                ans / 0

        try:
            task_with_log_dataset_wrapper()
        except Exception:
            pass

        log_dataset_arg = one(get_log_datasets(mock_channel_tracker))
        assert log_dataset_arg.operation_path == "/path/to/value.csv"
        assert log_dataset_arg.operation_type == DbndDatasetOperationType.write.value
        assert log_dataset_arg.operation_status == DbndTargetOperationStatus.NOK.value
        assert log_dataset_arg.value_preview is not None
        assert log_dataset_arg.data_dimensions == [5, 3]
        assert set(log_dataset_arg.data_schema.keys()) == {
            "columns",
            "dtypes",
            "shape",
            "size.bytes",
            "type",
        }

    def test_failed_target(self, mock_channel_tracker):
        @task()
        def task_with_log_datasets():
            log_dataset_op(
                "location://path/to/value.csv",
                "read",  # Check passing str values too
                success=False,
                with_schema=False,
            )

        task_with_log_datasets()

        log_dataset_arg = one(get_log_datasets(mock_channel_tracker))
        assert log_dataset_arg.operation_path == "location://path/to/value.csv"
        assert log_dataset_arg.operation_type == DbndDatasetOperationType.read.value
        assert log_dataset_arg.operation_status == DbndTargetOperationStatus.NOK.value
        assert log_dataset_arg.value_preview == ""
        assert log_dataset_arg.data_dimensions is None
        assert log_dataset_arg.data_schema is None

        log_metrics_args = get_log_metrics(mock_channel_tracker)
        assert len(list(log_metrics_args)) == 0

    def test_with_actual_op_path(self, mock_channel_tracker):
        @task()
        def task_with_log_datasets():
            a_target = target("/path/to/value.csv")
            log_dataset_op(a_target, DbndDatasetOperationType.read, with_schema=False)

        task_with_log_datasets()

        log_dataset_arg = one(get_log_datasets(mock_channel_tracker))
        assert log_dataset_arg.operation_path == "/path/to/value.csv"
        assert log_dataset_arg.operation_type == DbndDatasetOperationType.read.value
        assert log_dataset_arg.operation_status == DbndTargetOperationStatus.OK.value
        assert log_dataset_arg.value_preview == ""
        assert log_dataset_arg.data_dimensions is None
        assert log_dataset_arg.data_schema is None

        log_metrics_args = get_log_metrics(mock_channel_tracker)
        assert len(list(log_metrics_args)) == 0

    def test_path_with_data_meta(self, mock_channel_tracker, pandas_data_frame):
        @task()
        def task_with_log_datasets():
            log_dataset_op(
                "/path/to/value.csv",
                DbndDatasetOperationType.read,
                data=pandas_data_frame,
                with_preview=True,
                with_schema=True,
            )

        task_with_log_datasets()

        log_dataset_arg = one(get_log_datasets(mock_channel_tracker))

        assert log_dataset_arg.operation_path == "/path/to/value.csv"
        assert log_dataset_arg.operation_type == DbndDatasetOperationType.read.value
        assert log_dataset_arg.operation_status == DbndTargetOperationStatus.OK.value
        assert log_dataset_arg.value_preview is not None
        assert log_dataset_arg.data_dimensions == [5, 3]
        assert set(log_dataset_arg.data_schema.keys()) == {
            "columns",
            "dtypes",
            "shape",
            "size.bytes",
            "type",
        }

        log_metrics_args = get_log_metrics(mock_channel_tracker)
        metrics_names = {metric_row["metric"].key for metric_row in log_metrics_args}
        assert metrics_names.issuperset(
            {
                "path.to.value.csv.schema",
                "path.to.value.csv.shape0",
                "path.to.value.csv.shape1",
                "path.to.value.csv.rows",
                "path.to.value.csv.columns",
                "path.to.value.csv",
            }
        )
