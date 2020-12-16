# -*- coding: utf-8 -*-
import yaml
from bag.design.module import Module
from verification.mos.query import MOSDBDiscrete
from typing import Tuple, Mapping, Any, List

def get_mos_db(spec_file, intent, interp_method='spline', sim_env='tt') -> MOSDBDiscrete:
    # Initialize transistor database from simulation data
    mos_db = MOSDBDiscrete([spec_file], interp_method=interp_method)
    # Set process corners
    mos_db.env_list = [sim_env]
    # Set layout parameters
    mos_db.set_dsn_params(intent=intent)
    return mos_db

def estimate_vth(db:MOSDBDiscrete, vgs:float, vbs:float, is_nch:bool) -> float:
    """Estimates the threshold voltage of a device.
    TODO: Currently assumes a quadratic model.
    Inputs:
        db: MOSDBDiscrete associated with the device.
        is_nch: Boolean. True for NMOS, false otherwise.
        vgs: Gate-source voltage of the device.
        vbs: Bulk/body-source voltage of the device.
    Returns:
        vth: Threshold voltage in volts. Note that this
            can be negative.
    """
    op = db.query(vgs=vgs, vds=vgs, vbs=vbs)
    return vgs - op['vstar']

def parallel(*args):
    if 0 in args:
        return 0
    return 1/sum([1/a for a in args])

class DesignModule(object):
    """The base class of all design toward a spec.
    """

    def __init__(self):
        self.sch_params = None
        self.best_op = None

    @classmethod
    def get_params_info(cls):
        # type: () -> Optional[Dict[str, str]]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return None

    def meet_spec(self, **kwargs) -> Tuple[Mapping[str,Any],Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.
        Inputs:
            kwargs: Keys match the elements of the result of get_params_info
        Returns:
            sch_params: Schematic parameters for use with a schematic generator.
            best_op: Expected parameters (calculated, not simulated)
        Raises a ValueError if there is no solution.
        """
        return None, None

    def design(self, **kwargs):
        """Takes the spec parameters and designs for the spec.
        """
        self.sch_params, self.best_op = self.meet_spec(**kwargs)

        yaml_info = dict(params = self.sch_params.copy(),
                         op_info = self.best_op.copy())

        return yaml_info