# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

import os
import pkg_resources
import numpy as np
import warnings

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add, enable_print, disable_print
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins, get_w_crossings

from .amp_gm_mirr import bag2_analog__amp_gm_mirr_dsn
from .constant_gm import bag2_analog__constant_gm_dsn

# noinspection PyPep8Naming
class span_ion__delay_tt1_ord2_dsn(DesignModule):
    """Module for library span_ion cell delay_tt1_ord2 for a 
    second order low-pass bessel filter from Vout2.

    Assumes all amplifiers are identical for simplicity

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
            specfile_dict = 'Transistor database spec file names for each device',
            th_dict = 'Transistor flavor dictionary.',
            l_dict = 'Transistor channel length dictionary',
            sim_env = 'Simulation environment',
            tdelay = 'Target low frequency group delay',
            vdd = 'Supply voltage in volts.',
            vref = 'Reference voltage for all of the amplifiers.',
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
            optional_params = ''
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
                                          scale_num=params['tf_scale_num'])

        assert False, 'blep'

        # Design amplifiers back to front
        sim_env = params['sim_env']

        in_type_list = params['in_type_list']

        specfile_dict= params['specfile_dict']
        amp_specfile_list = specfile_dict['amp']
        bias_specfile_list = specfile_dict['bias']

        th_dict = params['th_dict']
        amp_th_list = th_dict['amp']
        bias_th_list = th_dict['bias']
        
        l_dict = params['l_dict']
        amp_l_list = l_dict['amp']
        bias_l_list = l_dict['bias']
        
        vdd = params['vdd']
        vref = params['vref']
        cload = params['cload']

        amp_dsn_params_list = params['amp_dsn_params_list']
        bias_dsn_params_list = params['bias_dsn_params_list']
        amp_optional_params = optional_params_dict['amp']
        bias_optional_params = optional_params_dict['bias']

        amp_optional_params.update(dict(voutcm=vref,
                                        **optional_params_dict['amp']))

        amp_update_dict_list = [dict(in_type=in_type_list[i],
                                     specfile_dict=amp_specfile_list[i],
                                     th_dict=amp_th_list[i],
                                     l_dict=amp_l_list[i],
                                     optional_params=amp_optional_params,
                                     vdd=vdd,
                                     vincm=vref,
                                     sim_env=sim_env) for i in range(3)]

        amp_dsn_mod = bag2_analog__amp_gm_mirr_dsn()
        amp_dsn_info_list = []

        # Design amplifiers
        amp_dsn_params_list[2].update(dict(cload=params['C2']))
        amp_dsn_params_list[2].update(amp_update_dict_list[2])
        print('Designing AMP2...')
        try:
            disable_print()
            amp2_dsn_lst = amp_dsn_mod.meet_spec(**(amp_dsn_params_list[2]))
        except ValueError:
            amp2_dsn_lst = []
        finally:
            enable_print()

        print(f'{len(amp2_dsn_lst)} possibilities for AMP2')
        print('Designing AMP1...')
        for amp2_dsn_info in amp2_dsn_lst:
            amp_dsn_params_list[1].update(dict(cload=cload+amp2_dsn_info['cin']))
            amp_dsn_params_list[1].update(amp_update_dict_list[1])
            try:
                disable_print()
                amp1_dsn_lst = amp_dsn_mod.meet_spec(**(amp_dsn_params_list[1]))
            except ValueError:
                continue
            finally:
                enable_print()

            print(f'{len(amp1_dsn_lst)} possibilities for AMP1')

            for amp1_dsn_info in amp1_dsn_lst:
                amp_dsn_params_list[0].update(dict(cload=params['C1']+amp1_dsn_info['cin']))
                amp_dsn_params_list[0].update(amp_update_dict_list[0])
                try:
                    disable_print()
                    amp0_dsn_lst = amp_dsn_mod.meet_spec(**(amp_dsn_params_list[0]))
                except ValueError:
                    continue
                finally:
                    enable_print()

                print(f'{len(amp0_dsn_lst)} possibilities for AMP0')
                for amp0_dsn_info in amp0_dsn_lst:
                    amp_dsn_info_list.append([amp0_dsn_info.copy(), 
                                              amp1_dsn_info.copy(),
                                              amp2_dsn_info.copy()])
        
        print('Designing biasing...')
        # Design biasing
        bias_dsn_mod_list = [bag2_analog__constant_gm_dsn()] * 3
        bias_update_dict_list = [dict(specfile_dict=bias_specfile_list[i],
                                      th_dict=bias_th_list[i],
                                      l_dict=bias_l_list[i],
                                      sim_env=sim_env,
                                      res_side=in_type_list[i],
                                      vdd=vdd) for i in range(3)]
        for amp_dsn_info in amp_dsn_info_list:
            try:
                disable_print()
                bias0_dsn_params = dict(bias_dsn_params_list[0])
                bias0_dsn_params.update(dict(optional_params=bias_optional_params,
                                             vref={in_type_list[0] : amp_dsn_info[0]['vgtail']}))
                bias0_dsn_params.update(bias_update_dict_list[0])
                                
                bias1_dsn_params = dict(bias_dsn_params_list[1])
                bias1_dsn_params.update(dict(optional_params=bias_optional_params,
                                             vref={in_type_list[1] : amp_dsn_info[1]['vgtail']}))
                bias1_dsn_params.update(bias_update_dict_list[1])

                bias2_dsn_params = dict(bias_dsn_params_list[2])
                bias2_dsn_params.update(dict(optional_params=bias_optional_params,
                                             vref={in_type_list[2] : amp_dsn_info[2]['vgtail']}))
                bias2_dsn_params.update(bias_update_dict_list[2])

                bias0_sch_params, bias0_dsn_info = bias_dsn_mod_list[0].design(**bias0_dsn_params)
                bias1_sch_params, bias1_dsn_info = bias_dsn_mod_list[1].design(**bias1_dsn_params)
                bias2_sch_params, bias2_dsn_info = bias_dsn_mod_list[2].design(**bias2_dsn_params)
            except ValueError:
                continue
            finally:
                enable_print()

            viable_op = dict(amp_dsn_info=amp_dsn_info,
                             bias_sch_params=[bias0_sch_params.copy(),
                                              bias1_sch_params.copy(),
                                              bias2_sch_params.copy()],
                             bias_dsn_info=[bias0_dsn_info, bias1_dsn_info, bias2_dsn_info],
                             passives_info=passives_info)
            viable_op_list.append(viable_op)
            print('(SUCCESS)')
            pprint(viable_op)

        self.other_params = dict(in_type_list=in_type_list,
                                 amp_specfile_list=amp_specfile_list,
                                 amp_th_dict=amp_th_dict,
                                 amp_l_dict=amp_l_dict,
                                 bias_specfile_list=bias_specfile_list,
                                 bias_th_dict=bias_th_dict,
                                 bias_l_dict=bias_l_dict,
                                 )

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
        num = np.asarray([b0])
        den =np.asarray([1, a1, a0])

        # Calculate remaining resistor values (R4 and R6 are removed)
        R1 = 1/(a1 * C1)
        R2 = k1 / (np.sqrt(a0)*C2)
        R3 = 1/(k1*k2) * 1/(np.sqrt(a0)*C1)
        R5 = k1*np.sqrt(a0) / (b0*C2)
        R7 = k2 * R8

        wbw = get_w_3db(num, den)
        if wbw == None:
            wbw = 0
        fbw = wbw / (2*np.pi)

        return dict(R1 = R1,
                    R2 = R2,
                    R3 = R3,
                    R5 = R5,
                    R7 = R7,
                    k1=k1,
                    k2=k2,
                    C1=C1,
                    C2=C2,
                    R8=R8,
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
        iamp1 = sum([amp_op['ibias'] for amp_op in op1['amp_dsn_info']])
        iconstgm1 = sum([bias_op['ibias'] for bias_op in op1['bias_dsn_info']])
        ibias1 = iamp1 + iconstgm1

        iamp2 = sum([amp_op['ibias'] for amp_op in op2['amp_dsn_info']])
        iconstgm2 = sum([bias_op['ibias'] for bias_op in op2['bias_dsn_info']])
        ibias2 = iamp2 + iconstgm2

        return op1 if ibias1 < ibias2 else op2

    def get_sch_params(self, op):
        amp_dsn_info = op['amp_dsn_info']
        bias_dsn_info = op['bias_dsn_info']
        passives_info = op['passives_info']

        in_type_list = self.other_params['in_type_list']

        amp_specfile_list = self.other_params['amp_specfile_list']
        amp_l_list = self.other_params['amp_l_list']
        amp_th_list = self.other_params['amp_th_list']
        amp_db_list = [{k:get_mos_db(spec_file=amp_specfile_list[i][k],
                                     intent=amp_th_list[i][k],
                                     sim_env=sim_env) for k in amp_specfile_list[i][k].key()} for i in range(3)]

        bias_specfile_list = self.other_params['bias_specfile_list']
        bias_l_list = self.other_params['bias_l_list']
        bias_th_list = self.other_params['bias_th_list']
        bias_db_list = [{k:get_mos_db(spec_file=bias_specfile_list[i][k],
                                      intent=bias_th_list[i][k],
                                      sim_env=sim_env) for k in bias_specfile_list[i][k].key()} for i in range(3)]

        cap_sch_params = [{'cap_val' : passives_info['C1']},
                          {'cap_val' : passives_info['C2']}]

        res_name_map = ['R1', 'R2', 'R3', 'R5', 'R7', 'R8']
        res_sch_params = [dict(num_unit=1,
                               w=1e-6,
                               l=passives_info[res_name_map[i]]/600*1e-6, # TODO real resistors
                               intent=th_dict['res'][i])
                          for i in len(res_name_map)]

        amp_sch_params = [dict(in_type=in_type_list[i],
                               l_dict=amp_l_list[i],
                               th_dict=amp_th_list[i],
                               w_dict={k:db.width_list[0] for k,db in amp_db_list[i].items()},
                               seg_dict=amp_dsn_info[i]['nf_dict'])
                          for i in range(3)]

        bias_sch_params = op['bias_sch_params']

        return dict(cap_params_list=cap_sch_params,
                    res_params_list=res_sch_params,
                    amp_params_list=amp_sch_params,
                    constgm_params_list=bias_sch_params)