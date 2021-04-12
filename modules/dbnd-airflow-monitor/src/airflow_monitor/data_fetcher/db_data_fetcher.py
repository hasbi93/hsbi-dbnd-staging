import contextlib
import logging

from typing import List, Optional

from airflow_monitor.common.airflow_data import (
    AirflowDagRun,
    AirflowDagRunsResponse,
    DagRunsFullData,
    DagRunsStateData,
    LastSeenValues,
)
from airflow_monitor.common.config_data import AirflowServerConfig
from airflow_monitor.data_fetcher.base_data_fetcher import AirflowDataFetcher


logger = logging.getLogger(__name__)


class DbFetcher(AirflowDataFetcher):
    def __init__(self, config):
        # type: (AirflowServerConfig) -> DbFetcher
        super(DbFetcher, self).__init__(config)

        from sqlalchemy import create_engine

        self.dag_folder = config.local_dag_folder
        self.sql_conn_string = config.sql_alchemy_conn
        self.engine = create_engine(self.sql_conn_string)
        self.env = "AirflowDB"

        self._engine = None
        self._session = None
        self._dagbag = None

    @contextlib.contextmanager
    def _get_session(self):
        from airflow import conf
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        if not self._engine:
            conf.set("core", "sql_alchemy_conn", value=self.sql_conn_string)
            self._engine = create_engine(self.sql_conn_string)

            self._session = sessionmaker(bind=self._engine)

        session = self._session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    def _get_dagbag(self):
        if not self._dagbag:
            from airflow import models, settings
            from airflow.settings import STORE_SERIALIZED_DAGS

            self._dagbag = models.DagBag(
                self.dag_folder if self.dag_folder else settings.DAGS_FOLDER,
                include_examples=True,
                store_serialized_dags=STORE_SERIALIZED_DAGS,
            )
        return self._dagbag

    def get_last_seen_values(self) -> LastSeenValues:
        from dbnd_airflow_export.api_functions import get_last_seen_values

        with self._get_session() as session:
            data = get_last_seen_values(session=session)
        return LastSeenValues.from_dict(data.as_dict())

    def get_airflow_dagruns_to_sync(
        self,
        last_seen_dag_run_id: Optional[int],
        last_seen_log_id: Optional[int],
        extra_dag_run_ids: Optional[List[int]],
        dag_ids: Optional[str],
    ) -> AirflowDagRunsResponse:
        from dbnd_airflow_export.api_functions import get_new_dag_runs

        dag_ids_list = dag_ids.split(",") if dag_ids else None

        with self._get_session() as session:
            data = get_new_dag_runs(
                last_seen_dag_run_id=last_seen_dag_run_id,
                last_seen_log_id=last_seen_log_id,
                extra_dag_run_ids=extra_dag_run_ids,
                dag_ids=dag_ids_list,
                session=session,
            )
        return AirflowDagRunsResponse.from_dict(data.as_dict())

    def get_full_dag_runs(
        self, dag_run_ids: List[int], include_sources: bool
    ) -> DagRunsFullData:
        from dbnd_airflow_export.api_functions import get_full_dag_runs

        with self._get_session() as session:
            data = get_full_dag_runs(
                dag_run_ids=dag_run_ids,
                include_sources=include_sources,
                airflow_dagbag=self._get_dagbag(),
                session=session,
            )

        return DagRunsFullData.from_dict(data.as_dict())

    def get_dag_runs_state_data(self, dag_run_ids: List[int]) -> DagRunsStateData:
        from dbnd_airflow_export.api_functions import get_dag_runs_states_data

        with self._get_session() as session:
            data = get_dag_runs_states_data(dag_run_ids=dag_run_ids, session=session)

        return DagRunsStateData.from_dict(data.as_dict())

    def is_alive(self):
        return True
