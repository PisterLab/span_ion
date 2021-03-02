# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

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
            res_lim = 'Minimum and maximum resistor values',
            optional_params = 'res_vstep=resolution of voltage step, error_tol, vstar_min'
        ))
        return ans

    def meet_spec(self, **params) -> List[Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.

        Raises a ValueError if there is no solution.
        """
        optional_params = params['optional_params']
        res_vstep = optional_params.get('res_vstep', 10e-3)
        error_tol = optional_params.get('error_tol', 0.05)

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
        vn = vref_targets.get('n', None)
        vp = vref_targets.get('p', None)
        ibias_max = params['ibias']
        res_min, res_max = params['res_lim']

        res_n = res_side == 'n'
        assert vn != None or vp != None, f'At least one of vp or vn have to be assigned'

        vstar_min = optional_params.get('vstar_min', 0.2)
        vth_n = estimate_vth(is_nch=True, vgs=vdd/2, vbs=0, db=db_dict['n'], lch=l_dict['n'])
        vth_p = estimate_vth(is_nch=False, vgs=-vdd/2, vbs=0, db=db_dict['p'], lch=l_dict['p'])

        vg_p_vec = [vp] if vp != None else np.arange(max(0, vn-vth_n, vn+vth_p), min(vdd, vdd+vth_p-vstar_min), res_vstep)
        vg_n_vec = [vn] if vn != None else np.arange(max(0, vth_n+vstar_min), min(vdd, vp+vth_n, vp-vth_p), res_vstep)

        viable_op_list = []

        # Sweep possibilities: vgp, vgn, vsp, vsn
        for vg_p in vg_p_vec:
            p_diode_op = db_dict['p'].query(vgs=vg_p-vdd, vds=vg_p-vdd, vbs=0)
            for vg_n in vg_n_vec:
                n_diode_op = db_dict['n'].query(vgs=vg_n, vds=vg_n, vbs=0)

                vs_p_vec = [vdd] if res_n else np.arange(vg_p-vth_p+vstar_min, vdd, res_vstep)
                vs_n_vec = [0] if not res_n else np.arange(0, vg_n-vth_n-vstar_min, res_vstep)

                for vs_p in vs_p_vec:
                    p_nondiode_op = db_dict['p'].query(vgs=vg_p-vs_p, vds=vg_n-vs_p, vbs=vdd-vs_p)
                    for vs_n in vs_n_vec:
                        n_nondiode_op = db_dict['n'].query(vgs=vg_n-vs_n, vds=vg_p-vs_n, vbs=0-vs_n)

                        main_diode_op = n_diode_op if res_n else p_diode_op
                        main_nondiode_op = p_nondiode_op if res_n else n_nondiode_op
                        side_diode_op = p_diode_op if res_n else n_diode_op
                        side_nondiode_op = n_nondiode_op if res_n else p_nondiode_op

                        imain_unit = main_diode_op['ibias']
                        nf_main_diode_max = int(round(ibias_max/imain_unit))
                        nf_main_diode_vec = np.arange(1, nf_main_diode_max, 1)
                        for nf_main_diode in nf_main_diode_vec:
                            imain = imain_unit * nf_main_diode

                            main_match, nf_main_nondiode = verify_ratio(main_diode_op['ibias'],
                                                                        main_nondiode_op['ibias'],
                                                                        nf_main_diode,
                                                                        error_tol)
                            if not main_match:
                                continue

                            nf_side_diode = nf_main_nondiode

                            # Match the final device size
                            match_side, nf_side_nondiode = verify_ratio(side_diode_op['ibias'],
                                                                        side_nondiode_op['ibias'],
                                                                        nf_side_diode,
                                                                        0.05)
                            if not match_side:
                                print("side match")
                                continue

                            if nf_side_nondiode == nf_main_diode:
                                continue

                            iside_unit = side_diode_op['ibias']
                            iside = iside_unit * nf_side_diode
                            res_val = vs_n/iside if res_n else (vdd-vs_p)/iside

                            if res_val > res_max or res_val < res_min:
                                print(f"res {res_val}")
                                break

                            if imain + iside > ibias_max:
                                print(f"ibias {imain+iside}")
                                break

                            viable_op = dict(nf_diode_p=nf_main_diode if not res_n else nf_side_diode,
                                             nf_diode_n=nf_main_diode if res_n else nf_side_diode,
                                             nf_nondiode_p=nf_main_nondiode if res_n else nf_side_nondiode,
                                             nf_nondiode_n=nf_main_nondiode if not res_n else nf_side_nondiode,
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

    
        self.other_params = dict(res_side=res_side,
                                 l_dict=l_dict,
                                 w_dict={k:db.width_list[0] for k,db in db_dict.items()},
                                 th_dict=th_dict)

        return viable_op_list

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['nf_side_nondiode'] > op2['nf_side_nondiode'] else op1

    def get_sch_params(self, op):
        res_side = self.other_params['res_side']
        self.other_params['l_dict'].update(dict(res=op['res_val']*1e-6/600))  # TODO real resistor
        self.other_params['w_dict'].update(dict(res=1e-6))

        return dict(bulk_conn='VDD',
                    res_side=res_side,
                    l_dict=self.other_params['l_dict'],
                    w_dict=self.other_params['w_dict'],
                    th_dict=self.other_params['th_dict'],
                    seg_dict=dict(n=op['nf_diode_n'], p=op['nf_diode_p'], res=1), # TODO real resistor
                    device_mult=op['nf_nondiode_n']/op['nf_diode_n'] if res_side=='n' else \
                                op['nf_nondiode_p']/op['nf_diode_p'])
