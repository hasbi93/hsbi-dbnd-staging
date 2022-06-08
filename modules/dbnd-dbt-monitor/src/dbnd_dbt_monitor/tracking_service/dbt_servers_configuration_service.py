from airflow_monitor.shared.base_tracking_service import WebServersConfigurationService


class DbtSyncersConfigurationService(WebServersConfigurationService):
    def _get_monitor_config_data(self):
        result = self._api_client.api_request(
            endpoint="dbt_syncers", method="GET", data=None
        )
        return result

    def update_monitor_state(self, monitor_state):
        data, _ = self.monitor_state_schema().dump(monitor_state.as_dict())

        self._api_client.api_request(
            endpoint=f"source_monitor/{self.monitor_type}/{self.tracking_source_uid}/state",
            method="PATCH",
            data=data,
        )