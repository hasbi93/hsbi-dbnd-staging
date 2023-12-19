# © Copyright Databand.ai, an IBM Company 2022

from typing import Optional, Tuple

from airflow_monitor.shared.adapter.adapter import Adapter, Assets, ThirdPartyInfo


class MockAirflowAdapter(Adapter):
    def __init__(self):
        super(MockAirflowAdapter, self).__init__()
        self.metadata = None
        self.error_list = []

    def init_cursor(self) -> object:
        raise NotImplementedError()

    def get_new_assets_for_cursor(self, cursor: object) -> Tuple[Assets, object]:
        raise NotImplementedError()

    def get_assets_data(self, assets: Assets) -> Assets:
        raise NotImplementedError()

    def get_third_party_info(self) -> Optional[ThirdPartyInfo]:
        return ThirdPartyInfo(metadata=self.metadata, error_list=self.error_list)
