# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any

import os
import pkg_resources
import numpy as np

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins

# noinspection PyPep8Naming
class bag2_analog__constant_gm_dsn(DesignModule):
    """Module for library bag2_analog cell constant_gm.

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
            res_side = 'Which side the resistor is placed on',
            vref = 'Dictionary of "n" and "p" of target bias voltages. If no spec, do not include',
            vdd = 'Supply voltage (volts)',
            ibias = 'Maximum bias current',
            res_lim = 'Minimum and maximum resistor values'
            # vswing_lim = 'Tuple of lower and upper swing from the bias',
            # gain = '(Min, max) small signal gain target in V/V',
            # fbw = 'Minimum bandwidth in Hz',
            # vdd = 'Supply voltage in volts.',
            # vincm = 'Input common mode voltage.',
            # ibias = 'Maximum bias current, in amperes.',
            # cload = 'Output load capacitance in farads.'
        ))
        return ans

    def meet_spec(self, **params) -> Tuple[Mapping[str,Any],Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.

        Raises a ValueError if there is no solution.
        """
        ### Get DBs for each device
        specfile_dict = params['specfile_dict']
        l_dict = params['l_dict']
        th_dict = params['th_dict']
        sim_env = params['sim_env']

        # Databases
        db_dict = {k:get_mos_db(spec_file=specfile_dict[k],
                                intent=th_dict[k],
                                sim_env=sim_env) for k in specfile_dict.keys()}
        
        # Target spec
        vref_targets = params['vref']
        vdd = params['vdd']
        res_side = params['res_side']
        vn = None if 'n' not in vref_targets.keys() else vref_targets['n']
        vp = None if 'p' not in vref_targets.keys() else vref_targets['p']
        ibias_max = params['ibias']
        res_min, res_max = params['res_lim']

        assert vn != None or vp != None, f'At least one of vp or vn have to be assigned'

        vstar_min = 0.25
        vth_n = estimate_vth(is_nch=True, vgs=vdd/2, vbs=0, db=db_dict['n'])
        vth_p = estimate_vth(is_nch=False, vgs=-vdd/2, vbs=0, db=db_dict['p'])

        vg_p_vec = [vp] if vp != None else np.arange(min(vn-vth_n, vn+vth_p), vdd+vth_p-vstar_min, 10e-3)
        vg_n_vec = [vn] if vn != None else np.arange(vth_n+vstar_min, max(vp+vth_n, vp-vth_p), 10e-3)

        viable_op_list = []

        # Sweep possibilities: vgp, vgn, vsp, vsn
        print(f'VGP: {min(vg_p_vec)}/{max(vg_p_vec)}')
        print(f'VGN: {min(vg_n_vec)}/{max(vg_n_vec)}')

        for vg_p in vg_p_vec:
            p_diode_op = db_dict['p'].query(vgs=vg_p-vdd, vds=vg_p-vdd, vbs=0)
            for vg_n in vg_n_vec:
                n_diode_op = db_dict['n'].query(vgs=vg_n, vds=vg_n, vbs=0)

                vs_p_vec = [vdd] if res_side=='n' else np.arange(max(vg_p-vth_p+vstar_min, vg_n+vstar_min), vg_p-vth_p+vstar_min, 10e-3)
                vs_n_vec = [0] if res_side=='p' else np.arange(vg_n-vth_n-vstar_min, min(vg_n-vth_p-vstar_min, vg_p-vstar_min), 10e-3)
                
                print(f'VSP: {min(vs_p_vec)}/{max(vs_p_vec)}')
                print(f'VSN: {min(vs_n_vec)}/{max(vs_n_vec)}')

                for vs_p in vs_p_vec:
                    p_nondiode_op = db_dict['p'].query(vgs=vg_p-vs_p, vds=vg_n-vs_p, vbs=vdd-vs_p)
                    for vs_n in vs_n_vec:
                        n_nondiode_op = db_dict['n'].query(vgs=vg_n-vs_n, vds=vg_p-vs_n, vbs=0-vs_n)

                        main_diode_op = n_diode_op if res_side == 'n' else p_diode_op
                        main_nondiode_op = p_nondiode_op if res_side == 'n' else n_nondiode_op
                        side_diode_op = p_diode_op if res_side == 'n' else n_diode_op
                        side_nondiode_op = n_nondiode_op if res_side == 'n' else p_nondiode_op

                        imain_unit = main_diode_op['ibias']
                        nf_main_diode_max = int(round(ibias_max/imain_unit))
                        nf_main_diode_vec = np.arange(1, nf_main_diode_max, 1)
                        for nf_main_diode in nf_main_diode_vec:
                            imain = imain_unit * nf_main_diode

                            main_match, nf_main_nondiode = verify_ratio(main_diode_op['ibias'],
                                                                        main_nondiode_op['ibias'],
                                                                        nf_main_diode,
                                                                        0.1)
                            if not main_match:
                                continue

                            nf_side_diode = nf_main_nondiode

                            # Match the final device size
                            match_side, nf_side_nondiode = verify_ratio(side_diode_op['ibias'],
                                                                        side_nondiode_op['ibias'],
                                                                        nf_side_diode,
                                                                        0.1)
                            if not match_side:
                                # raise ValueError("pause")
                                # print("Side match fail")
                                continue

                            iside_unit = side_diode_op['ibias']
                            iside = iside_unit * nf_side_diode
                            res_val = vs_n/iside if res_side=='n' else vs_p/iside

                            if res_val > res_max or res_val < res_min:
                                # print("Res fail")
                                break

                            if imain + iside > ibias_max:
                                # print("Ibias fail")
                                break

                            viable_op = dict(nf_diode_p=nf_main_diode if res_side=='p' else nf_side_diode,
                                             nf_diode_n=nf_main_diode if res_side=='n' else nf_side_diode,
                                             nf_nondiode_p=nf_main_nondiode if res_side=='n' else nf_side_nondiode,
                                             nf_nondiode_n=nf_main_nondiode if res_side=='p' else nf_side_nondiode,
                                             vgn=vg_n,
                                             vgp=vg_p,
                                             vsn=vs_n,
                                             vsp=vs_p,
                                             imain=imain,
                                             iside=iside,
                                             ibias=imain+iside,
                                             res_val=res_val,
                                             nf_side_nondiode=nf_side_nondiode)
                            viable_op_list.append(viable_op)
                            print('\n(SUCCESS)')
                            print(viable_op)        

        if len(viable_op_list) < 1:
            raise ValueError("No solution")

        # Find the best operating point among those which do
        best_op = viable_op_list[0]
        for op in viable_op_list:
            best_op = self.op_compare(best_op, op)


        # Arranging schematic parameters
        mirr_n_params = dict(device_params=dict(l=l_dict['n'], 
                                                w=db_dict['n'].width_list[0],
                                                intent=th_dict['n']),
                             seg_in=best_op['nf_diode_n'],
                             seg_out_list=[best_op['nf_nondiode_n']])
        mirr_p_params = dict(device_params=dict(l=l_dict['p'], 
                                                w=db_dict['p'].width_list[0],
                                                intent=th_dict['p']),
                             seg_in=best_op['nf_diode_p'],
                             seg_out_list=[best_op['nf_nondiode_p']])

        # TODO real resistor
        res_params = dict(w=1e-6, l=1e-6*best_op['res_val']/600, intent='ideal', num_unit=1)

        sch_params = dict(res_side=res_side,
                          res_params=res_params,
                          mirr_n_params=mirr_n_params,
                          mirr_p_params=mirr_p_params,
                          bulk_conn='VSS')

        print(f"(RESULT) {sch_params}\n{best_op}")

        return sch_params, best_op

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['nf_side_nondiode'] > op2['nf_side_nondiode'] else op1