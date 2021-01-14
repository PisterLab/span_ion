# -*- coding: utf-8 -*-
import sys, os
import yaml
from bag.design.module import Module
from bag.util.search import FloatBinaryIterator
from verification.mos.query import MOSDBDiscrete
from typing import Tuple, Mapping, Any, List
import numpy as np

def disable_print():
    sys.stdout = open(os.devnull, 'w')

def enable_print():
    sys.stdout = sys.__stdout__

def get_mos_db(spec_file, intent, interp_method='spline', sim_env='tt') -> MOSDBDiscrete:
    # Initialize transistor database from simulation data
    mos_db = MOSDBDiscrete([spec_file], interp_method=interp_method)
    # Set process corners
    mos_db.env_list = [sim_env]
    # Set layout parameters
    mos_db.set_dsn_params(intent=intent)
    return mos_db

def estimate_vth(db:MOSDBDiscrete, vgs:float, vbs:float, is_nch:bool, lch:float) -> float:
    """Estimates the threshold voltage of a device.
    TODO: Currently assumes a quadratic model for vgs/lch < 1V/um, otherwise
        assumes a linear model.
    Inputs:
        db: MOSDBDiscrete associated with the device.
        is_nch: Boolean. True for NMOS, false otherwise.
        vgs: Gate-source voltage of the device.
        vbs: Bulk/body-source voltage of the device.
        lch: Channel length.
    Returns:
        vth: Threshold voltage in volts. Note that this
            can be negative.
    """
    op = db.query(vgs=vgs, vds=vgs, vbs=vbs)
    vds_ref = vgs if is_nch else -vgs
    vov = op['vstar'] if vds_ref/lch < 1e6 else op['vstar']/2
    if is_nch:
        return vgs - vov
    else:
        return vgs + vov

def match_vgs(db, is_nch:bool, itarget:float, nf:int, vds:float, vbs:float, vdd:float):
    '''
    Binary search to find the vgs associated with a particular
    bias current, all other bias voltages constant. Assumes
    monotonic relationship between vgs and ibias.
    '''
    vgs_min = -vdd if not is_nch else 0
    vgs_max = vdd if is_nch else 0
    vgs_iter = FloatBinaryIterator(vgs_min, vgs_max, vdd/1000)
    while vgs_iter.has_next():
        vgs = vgs_iter.get_next()
        op = db.query(vgs=vgs, vds=vds, vbs=vbs)
        ibias = op['ibias']*nf

        if ibias > itarget:
            if is_nch:
                vgs_iter.down()
            else:
                vgs_iter.up()
        if ibias < itarget:
            if is_nch:
                vgs_iter.up()
            else:
                vgs_iter.down()
    if is_nch and vgs > vdd:
        return False, vgs
    elif not is_nch and vgs < -vdd:
        return False, vgs

    return True, vgs


def verify_ratio(ibase_A:float, ibase_B:float,
        nf_A:int, error_tol:float) -> Tuple[bool,int]:
    """
    Inputs:
        ibase_A/B: Float. the drain current of a single A- or B-device.
        nf_A: Integer. Number of fingers for device A.
        error_tol: float. Fractional tolerance for ibias error
            when computing the device sizing ratio.
    Outputs:
        meets_tol: True if the ratio is possible and meets
            the error tolerance.
        nf_B: Integer indicating the number of fingers for
            device B.
    """
    B_to_A = ibase_A/ibase_B

    # Check if ratio is possible with physical device sizes
    nf_B = int(round(nf_A * B_to_A))

    # Is anything smaller than min?
    if nf_B < 1:
        return False, 0

    # Check current mismatch given quantization
    id_A = nf_A * ibase_A
    id_B = nf_B * ibase_B

    error = (abs(id_A) - abs(id_B))/abs(id_A)

    if abs(error) > error_tol:
        return False, 0

    return True, nf_B

def parallel(*args):
    if 0 in args:
        return 0
    return 1/sum([1/a for a in args])

def num_den_add(num1, num2, den1, den2):
    den_new = np.convolve(den1, den2)
    num1_new = np.convolve(num1, den2)
    num2_new = np.convolve(num2, den1)

    num_new = np.add(num1_new, num2_new)

    return num_new, den_new

class DesignModule(object):
    """The base class of all design toward a spec.
    """

    def __init__(self):
        self.viable_ops = []
        self.other_params = dict() # Information necessary for schematic parameters

    @classmethod
    def get_params_info(cls):
        # type: () -> Optional[Dict[str, str]]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict()

    def meet_spec(self, **kwargs) -> List[Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.
        Assigns other_params
        Inputs:
            kwargs: Keys match the elements of the result of get_params_info
        Returns:
        """
        return []

    def choose_op(self, viable_op_list:List[Mapping[str,Any]]):
        if len(viable_op_list) == 0:
            raise ValueError("No solution")

        else:
            best_op = viable_op_list[0]
            for op in viable_op_list:
                best_op = self.op_compare(best_op, op)
        
        return best_op
    
    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        raise NotImplementedError()

    def get_sch_params(self, op):
        raise NotImplementedError()

    def design(self, **kwargs) -> Tuple[Mapping[str,Any], Mapping[str,Any]]:
        """Takes the spec parameters and designs for the spec.
        """
        print('Searching for viable operating points')
        self.viable_op_list = self.meet_spec(**kwargs)
        print(f'{len(self.viable_op_list)} viable operating points.\nChoosing best operating point')
        best_op = self.choose_op(self.viable_op_list)
        sch_params = self.get_sch_params(best_op)

        print(f"OP: \n{best_op}\n\nSCH:\n{sch_params}")

        return sch_params, best_op

        # yaml_info = dict(sch_params=sch_params.copy(),
        #                  op_info=best_op.copy())

        # return yaml_info