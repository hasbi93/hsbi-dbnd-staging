# © Copyright Databand.ai, an IBM Company 2022

from dbnd import band, parameter


class UnknownForDBND(object):
    pass


@band(ssss=parameter[UnknownForDBND])
def error_band_unknown_param():
    return None
