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
            vref = 'Dictionray of "n" and "p" of target bias voltages. If no spec, set to None',
            vdd = 'Supply voltage (volts)',
            ibias = 'Maximum bias current'
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
        iref_targets = params['iref']
        vref_targets = params['vref']
        vdd = params['vdd']
        res_side = params['res_side']
        vn = vref_targets['n']
        vp = vref_targets['p']
        ibias_max = params['ibias']

        assert vn != None or vp != None, f'At least one of vp or vn have to be assigned'

        vstar_min = 0.25
        vth_n = estimate_vth(is_nch=True, vgs=vdd/2, vbs=0, db=db_dict['n'])
        vth_p = estimate_vth(is_nch=False, vgs=-vdd/2, vbs=0, db=db_dict['p'])

        vg_p_vec = [vp] if vp != None else np.arange(vn-vth_n, vn+vth_p, 10e-3)
        vg_n_vec = [vn] if vn != None else np.arange(vp+vth_n, vp-vth_p, 10e-3)

        vs_p_vec = [vdd] if res_side=='n' else np.arange(max(vp-vth_p+vstar_min, vn+vstar_min), vdd, 10e-3)
        vs_n_vec = [0] if res_side=='p' else np.arange(0, min(vn-vth_p-vstar_min, vp-vstar_min), 10e-3)

        # Sweep possibilities: vgp, vgn, vsp, vsn
        for vg_p in vg_p_vec:
            p_diode_op = db_dict['p'].query(vgs=vg_p-vdd, vds=vg_p-vdd, vbs=0)
            for vg_n in vg_n_vec:
                n_diode_op = db_dict['n'].query(vgs=vg_n, vds=vg_n, vbs=0)
                for vs_p in vs_p_vec:
                    p_nondiode_op = db_dict['p'].query(vgs=vp-vs_p, vds=vn-vs_p, vbs=vdd-vs_p)
                    for vs_n in vs_n_vec:
                        n_nondiode_op = db_dict['n'].query(vgs=vn-vs_n, vds=vp-vs_n, vbs=0-vs_n)

                        main_diode_op = n_diode_op if res_side == 'n' else p_diode_op
                        main_nondiode_op = p_extra_op if res_side == 'n' else n_extra_op
                        side_diode_op = p_diode_op if res_side == 'n' else n_diode_op
                        side_nondiode_op = n_extra_op if res_side == 'n' else p_extra_op

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
                                continue

                            iside_unit = side_diode_op['ibias']
                            iside = iside_unit * nf_side_diode
                            res_val = vs_n/iside if res_side=='n' else vs_p/iside

                            if imain + iside > ibias_max:
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
                                             res_val=res_val)
                            print('\n(SUCCESS)')
                            print(viable_op)        

        if len(viable_op_list) < 1:
            raise ValueError("No solution")

        # Find the best operating point among those which do
        best_op = dict(ibias=np.inf)
        for op in viable_op_list:
            best_op = self.op_compare(best_op, op)


        # Arranging schematic parameters
        diffpair_params = dict(lch_dict=l_dict,
                               w_dict={k:db.width_list[0] for k,db in db_dict.items()},
                               seg_dict={'in' : best_op['nf_in'],
                                         'tail' : best_op['nf_tail']},
                               th_dict=th_dict,)

        mirr_params = dict(device_params=dict(w=db_dict['load'].width_list[0],
                                              l=l_dict['load'],
                                              intent=th_dict['load']),
                           seg_in=best_op['nf_load'],
                           seg_out_list=[best_op['nf_load']])

        sch_params = dict(diffpair_params=diffpair_params,
                          mirr_params=mirr_params,
                          in_type=in_type)

        print(f"(RESULT) {sch_params}\n{best_op}")

        return sch_params, best_op

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1