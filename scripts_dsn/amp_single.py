# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

import os
import pkg_resources
import numpy as np
import warnings

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins

# noinspection PyPep8Naming
class bag2_analog__amp_single_dsn(DesignModule):
    """Module for library bag2_analog cell amp_single.

    Fill in high level description here.
    """

    @classmethod
    def get_params_info(cls) -> Mapping[str,str]:
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        ans = super().get_params_info()
        # TODO: add resistors to specfile_dict and th_dict 
        ans.update(dict(
            specfile_dict = 'Transistor database spec file names for each device',
            l_dict = 'Transistor channel length dictionary',
            th_dict = 'Transistor flavor dictionary.',
            sim_env = 'Simulation environment',
            vswing_lim = 'Tuple of lower and upper swing from the bias',
            gain_lim = '(Min, max) small signal gain target in V/V',
            fbw = 'Minimum bandwidth in Hz',
            vdd = 'Supply voltage in volts.',
            vincm = 'Input bias mode voltage.',
            ibias = 'Maximum bias current, in amperes.',
            cload = 'Output load capacitance in farads.',
            optional_params = 'Optional parameters. voutcm=output bias voltage.',
            in_conn = '',
            out_conn = '',
            inv_out = ''
        ))
        return ans

    def meet_spec(self, **params) -> List[Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.
        Returns collection of all possible solutions.
        Raises a ValueError if there is no solution.
        """
        optional_params = params['optional_params']

        ### Get DBs for each device
        specfile_dict = params['specfile_dict']
        l_dict = params['l_dict']
        th_dict = params['th_dict']
        sim_env = params['sim_env']
        
        # Databases
        db_dict = {k:get_mos_db(spec_file=specfile_dict[k],
                                intent=th_dict[k],
                                sim_env=sim_env) for k in specfile_dict.keys()}

        ### Design devices
        vswing_low, vswing_high = params['vswing_lim']
        gain_min, gain_max = params['gain_lim']
        fbw_min = params['fbw']
        vdd = params['vdd']
        vincm = params['vincm']
        ibias_max = params['ibias']
        cload = params['cload']

        # Somewhat arbitrary vstar_min in this case
        vstar_min = 0.2

        # Keep track of viable operating points
        viable_op_list = []

        assert False, 'Not done'

        self.other_params = dict(in_type=in_type,
                                 w_dict={k:db.width_list[0] for k,db in db_dict.items()},
                                 l_dict=l_dict,
                                 th_dict=th_dict)

        return viable_op_list

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1

    def get_sch_params(self, op):
        return dict(in_type=self.other_params['in_type'],
                    l_dict=self.other_params['l_dict'],
                    w_dict=self.other_params['w_dict'],
                    th_dict=self.other_params['th_dict'],
                    seg_dict={'in' : op['nf_in'],
                              'tail' : op['nf_tail'],
                              'load' : op['nf_load']})