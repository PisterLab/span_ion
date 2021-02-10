# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

import os
import pkg_resources
import numpy as np
import warnings

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins, get_w_crossings

# noinspection PyPep8Naming
class span_ion__delay_tt1_ord2_dsn(DesignModule):
    """Module for library span_ion cell delay_tt1_ord2 for a 
    second order low-pass bessel filter from Vout2.

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
            in_type_list = '"p" or "n" for NMOS or PMOS input pair',
            specfile_dict_list = 'Transistor database spec file names for each device',
            th_dict_list = 'Transistor flavor dictionary.',
            l_dict_list = 'Transistor channel length dictionary',
            sim_env = 'Simulation environment',
            tdelay = 'Target low frequency group delay',
            vdd = 'Supply voltage in volts.',
            vref = 'Reference voltage for all of the amplifiers.',
            ibias = 'Maximum bias current, in amperes.',
            cload = 'Output load capacitance in farads.',
            gain = 'Target DC gain of the full filter (assume ideal amplifiers)',
            tf_scale_num = 'If the gain is nonunity, scale the numerator or denominator of the transfer function',
            amp_dsn_params_list = 'Design parameters for the amplifiers that don`t get determined elsewhere',
            bias_dsn_params_list = 'Design parameters for biasing that don`t get determined elsewhere',
            optional_params_dict = 'Optional parameters. keys "amp" and "bias"',
            k1 = '',
            k2 = '',
            C1 = '',
            C2 = '',
            R8 = '',
            optional_params = 'res_istep'
        ))
        return ans

    def meet_spec(self, **params) -> List[Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.
        Returns collection of all possible solutions.
        Raises a ValueError if there is no solution.
        """
        optional_params = dict(params['optional_params'])
        optional_params_dict = params['optional_params_dict']

        # Keeping track of viable operating points
        viable_op_list = []

        # Design the passives assuming an ideal amplifier
        passives_info = self.dsn_passives(tdelay=params['tdelay'],
                                          k1=params['k1'], 
                                          k2=params['k2'],
                                          C1=params['C1'],
                                          C2=params['C2'],
                                          R8=params['R8'], 
                                          gain_target=params['gain_target'],
                                          scale_num=params['tf_csale_num'])

        # Design amplifiers back to front
        sim_env = params['sim_env']

        in_type_list = params['in_type_list']
        specfile_dict_list = params['specfile_dict_list']
        th_dict_list = params['th_dict_list']
        l_dict_list = params['l_dict_list']
        
        vdd = params['vdd']
        vref = params['vref']
        ibias_max = params['ibias']
        cload = params['cload']

        amp_dsn_params_list = params['amp_dsn_params_list']
        bias_dsn_params_list = params['bias_dsn_params_list']
        amp_optional_params = optional_params['amp']
        bias_optional_params = optional_params['bias']

        amp_optional_params.update('voutcm', vref)

        amp_update_dict_list = [dict(in_type=in_type_list[i],
                                     specfile_dict=specfile_dict_list[i],
                                     th_dict=th_dict_list[i],
                                     l_dict=l_dict_list[i],
                                     sim_env=sim_env,
                                     vincm=vref,
                                     optional_params=amp_optional_params) for i in range(3)]

        amp_dsn_mod = bag2_analog__amp_diff_mirr_dsn()
        amp_dsn_info_list = []

        # Split up total current between amplifiers
        ibias2_vec = np.arange(0, ibias_max, res_istep)
        for ibias2 in ibias2_vec:
            amp_dsn_params_list[2].update(ibias=ibias2,
                                          cload=C2) # pessimistic
            try:
                disable_print()
                amp2_dsn_lst = amp_dsn_mod.meet_spec(**(amp_dsn_params_list[2]))
            except ValueError:
                continue
            finally:
                enable_print()

            ibias1_max = ibias_max - ibias2
            ibias1_vec = np.arange(0, ibias1_max, res_istep)
            for ibias1 in ibias1_vec:
                for amp2_dsn_info in amp2_dsn_lst:
                    amp_dsn_params_list[1].update(ibias=ibias1,
                                                  cload=cload) # TODO include cgg2
                    try:
                        disable_print()
                        amp1_dsn_lst = amp_dsn_mod.meet_spec(**(amp_dsn_params_list[1]))
                    except ValueError:
                        continue
                    finally:
                        enable_print()

                    ibias0_max = ibias_max - ibias2 - ibias1
                    ibias0_vec = np.arange(0, ibias0_max, res_istep)
                    for ibias0 in ibias0_vec:
                        for amp1_dsn_info in amp1_dsn_lst:
                            amp_dsn_params_list[0].update(ibias=ibias0,
                                                          cload=C1) # TODO include cgg1
                            try:
                                disable_print()
                                amp0_dsn_lst = amp_dsn_mod.meet_spec(**(amp_dsn_params_list[0]))
                            except ValueError:
                                continue
                            finally:
                                enable_print()

                            for amp0_dsn_info in amp0_dsn_lst:
                                amp_dsn_info_list.append([amp0_dsn_info.copy(), 
                                                          amp1_dsn_info.copy(),
                                                          amp2_dsn_info.copy()])
        
        # Design biasing
        bias_dsn_mod_list = [bag2_analog__constant_gm_dsn()] * 3
        for amp_dsn_info in amp_dsn_info_list:
            try:
                disable_print()
                bias0_dsn_params = dict(bias_dsn_params_list[0])
                bias0.update(optional_params=bias_optional_params,
                             vref={in_type_list[0] : amp_dsn_info[0]['vgtail']})
                                
                bias1_dsn_params = dict(bias_dsn_params_list[1])
                bias1.update(optional_params=bias_optional_params)
                bias1.update(optional_params=bias_optional_params,
                             vref={in_type_list[1] : amp_dsn_info[1]['vgtail']})

                bias2_dsn_params = dict(bias_dsn_params_list[2])
                bias2.update(optional_params=bias_optional_params)
                bias2.update(optional_params=bias_optional_params,
                             vref={in_type_list[2] : amp_dsn_info[2]['vgtail']})

                bias0_sch_params, bias0_dsn_info = bias_dsn_mod_list[0].design(**bias0_dsn_params)
                bias1_sch_params, bias1_dsn_info = bias_dsn_mod_list[1].design(**bias1_dsn_params)
                bias2_sch_params, bias2_dsn_info = bias_dsn_mod_list[2].design(**bias2_dsn_params)
            except ValueError:
                continue
            finally:
                enable_print()

            viable_op = dict()
            viable_op_list.append(viable_op)
            print('(SUCCESS)')
            pprint(viable_op)

        return viable_op_list

    def dsn_passives(self, tdelay, k1, k2, C1, C2, R8, gain_target, scale_num):
        w0 = 1/tdelay

        b0 = 3 * w0**2
        a1 = 3 * w0
        a0 = 3 * w0**2

        # Change values to get the right DC gain
        gain_mult = gain_target/(b0 / a0)

        if scale_num:
            b0 = b0 * gain_mult
        else:
            a1 = a1 / gain_mult
            a0 = a0 / gain_mult

        # Transfer function
        num = [b0]
        den =[1, a1, a0]

        # Calculate remaining resistor values (R4 and R6 are removed)
        R1 = a1 * C1
        R2 = k1 / (np.sqrt(a0)*C2)
        R3 = 1/(k1*k2) * 1/(np.sqrt(a0)*C2)
        R5 = k1*np.sqrt(a0) / (b0*C2)
        R7 = k2 * R8

        wbw = get_w_3db(num, den)
        if wbw == None:
            wbw = 0
        fbw = wbw / (2*n.pi)

        return dict(R1 = a1 * C1,
                    R2 = k1 / (np.sqrt(a0)*C2),
                    R3 = 1/(k1*k2) * 1/(np.sqrt(a0)*C2),
                    R5 = k1*np.sqrt(a0) / (b0*C2),
                    R7 = k2 * R8,
                    gain = b0 / a0,
                    fbw = fbw)


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
        return

    def get_sch_params(self, op):
        return dict()