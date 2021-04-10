# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

import os
import pkg_resources
import numpy as np
import warnings
from pprint import pprint

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add, enable_print, disable_print
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins, get_w_crossings

from .amp_gm_mirr import bag2_analog__amp_gm_mirr_dsn
from .constant_gm import bag2_analog__constant_gm_dsn

# noinspection PyPep8Naming
class span_ion__delay_sk_ord2_dsn(DesignModule):
    """Module for library span_ion cell delay_sk_ord2 for a 
    second order low-pass bessel filter. Amplifier is in unity
    gain feedback.

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
            th_dict = 'Transistor flavor dictionary.',
            l_dict = 'Transistor channel length dictionary',
            sim_env = 'Simulation environment',
            tdelay = 'Target low frequency group delay',
            vdd = 'Supply voltage in volts.',
            vincm = 'Input bias point',
            cload = 'Output load capacitance in farads.',
            amp_dsn_params = 'Design parameters for the amplifier that doesn`t get determined elsewhere',
            bias_dsn_params = 'Design parameters for biasing that doesn`t get determined elsewhere',
            C1 = 'Chosen value for C1',
            C2 = 'Chosen value for C2',
            res_lim_list = 'List of tuples containing min and max resistor values',
            optional_params = ''
        ))
        return ans

    def meet_spec(self, **params) -> List[Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.
        Returns collection of all possible solutions.
        Raises a ValueError if there is no solution.
        """
        specfile_dict = params['specfile_dict']
        amp_specfile_dict = specfile_dict['amp']
        bias_specfile_dict = specfile_dict['bias']

        th_dict = params['th_dict']
        amp_th_dict = th_dict['amp']
        bias_th_dict = th_dict['bias']

        l_dict = params['l_dict']
        amp_l_dict = l_dict['amp']
        bias_l_dict = l_dict['bias']

        sim_env = params['sim_env']

        tdelay = params['tdelay']
        vdd = params['vdd']
        vincm = params['vincm']
        cload = params['cload']

        amp_dsn_params = params['amp_dsn_params']
        bias_dsn_params = params['bias_dsn_params']

        C1 = params['C1']
        C2 = params['C2']
        res_lim_list = params['res_lim_list']
        optional_params = params['optional_params']
        res_rstep = optional_params.get('res_rstep', 500)

        ### Design feedback passives assuming an ideal amplifier
        passives_info_list = self.dsn_passives(tdelay, C1, C2, res_lim_list)
        print(f'{len(passives_info_list)} solutions with passives')

        ### Designing amplifier and associated constant gm
        amp_dsn_mod = bag2_analog__amp_gm_mirr_dsn()
        bias_dsn_mod = bag2_analog__constant_gm_dsn()

        beta_cap = C1/(C1+C2)
        amp_optional_params = amp_dsn_params['optional_params'].copy()
        amp_optional_params.update(dict(voutcm=vincm))

        print('Designing the amplifier...')
        amp_dsn_params.update(dict(vincm=vincm,
                                   cload=cload + C1*(1-beta_cap),
                                   specfile_dict=amp_specfile_dict,
                                   th_dict=amp_th_dict,
                                   l_dict=amp_l_dict,
                                   vdd=vdd,
                                   sim_env=sim_env,
                                   optional_params=amp_optional_params))
        bias_dsn_params.update(dict(specfile_dict=bias_specfile_dict,
                                    th_dict=bias_th_dict,
                                    l_dict=bias_l_dict,
                                    vdd=vdd,
                                    sim_env=sim_env,
                                    res_side=amp_dsn_params['in_type']))
        try:
            disable_print()
            amp_info_list = amp_dsn_mod.meet_spec(**amp_dsn_params)
        except ValueError:
            amp_info_list = []
        finally:
            enable_print()
        print(f'{len(amp_info_list)} amp solutions')

        viable_op_list = []

        for passives_info in passives_info_list:
            for amp_dsn_info in amp_info_list:
                ### Designing biasing
                bias_dsn_params.update(dict(vref={amp_dsn_params['in_type'] : amp_dsn_info['vgtail']}))
                
                try:
                    disable_print()
                    bias_sch_params, bias_dsn_info = bias_dsn_mod.design(**bias_dsn_params)
                except ValueError:
                    continue
                finally:
                    enable_print()

                # TODO lticircuit?
                viable_op = dict(amp_dsn_info=amp_dsn_info,
                                 bias_dsn_info=bias_dsn_info,
                                 passives_info=passives_info)
                print('(SUCCESS)')
                pprint(viable_op)
                viable_op_list.append(viable_op)
        
        return viable_op_list

    def dsn_passives(self, tdelay, C1, C2, res_lim_list) -> List[Mapping[str,float]]:
        # Transfer function
        w0 = 1/tdelay

        b0 = 3 * w0**2
        a1 = 3 * w0
        a0 = 3 * w0**2

        # Get the required product and sum of the resistors
        res_prod = 1 / (3 * w0**2 * C1 * C2)
        res_sum = 3 * C1 * res_prod * w0
        k1 = res_prod
        k2 = res_sum

        R1_min, R1_max = res_lim_list[0]
        R2_min, R2_max = res_lim_list[1]

        # xy = k1; x+y=k2
        # y = k2 - x
        # x(k2-x) = k1 -> x^2-k2x+k1 = 0

        sqrt_arg = k2**2 - 4*k1

        # No solution for strictly real resistor values 
        if sqrt_arg < 0:
            print(f'Complex resistance value {sqrt_arg}')
            return []

        R1_sols = [(k2 + np.sqrt(sqrt_arg)) / 2,
                   (k2 - np.sqrt(sqrt_arg)) / 2]
        R2_sols = [res_sum-R1 for R1 in R1_sols]
        R_sols_unfiltered = [(R1_sols[i], R2_sols[i]) for i in range(len(R1_sols))]
        print(f'Unfiltered resistor solutions: {R_sols_unfiltered}')
        # Filter through computed solutions for constraints
        R_sols_filtered = []
        for i, R_vals in enumerate(R_sols_unfiltered):
            R1, R2 = R_vals
            if R1>=R1_min and R1<=R1_max and R2>=R2_min and R2<=R2_max:
                R_sols_filtered.append(R_vals)

        return R_sols_filtered

        # # Estimate bandwidth
        # num = np.asarray([b0])
        # den = np.asarray([1, a1, a0])

        # wbw = get_w_3db(num, den)
        # if wbw == None:
        #     wbw = 0
        # fbw = wbw / (2*np.pi)


    def _get_ss_lti(self, op_dict:Mapping[str,Any], 
                    nf_dict:Mapping[str,int], 
                    cload:float) -> Tuple[float,float]:
        return

    def make_ltickt(self, op_dict:Mapping[str,Any], nf_dict:Mapping[str,int], 
                    cload:float, meas_side:str) -> LTICircuit:
        return

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        ibias1 = op1['amp_dsn_info']['ibias'] + op1['bias_dsn_info']['ibias']
        ibias2 = op1['amp_dsn_info']['ibias'] + op1['bias_dsn_info']['ibias']
        return op1 if ibias1 < ibias2 else op2

    def get_sch_params(self, op):
        return dict()