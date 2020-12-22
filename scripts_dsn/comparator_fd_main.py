# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any

import os
import pkg_resources
import numpy as np

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins

# noinspection PyPep8Naming
class span_ion__comparator_fd_main_dsn(DesignModule):
    """Module for library span_ion cell comparator_fd_main.

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
            gain_lim = '(Min, max) small signal gain target in V/V',
            fbw = 'Minimum bandwidth in Hz',
            vdd = 'Supply voltage in volts.',
            vincm = 'Input common mode voltage.',
            ibias = 'Maximum bias current, in amperes.',
            cload = 'Output load capacitance in farads.'
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

        ### Design devices
        vdd = params['vdd']
        vincm = params['vincm']
        cload = params['cload']
        gain_min, gain_max = params['gain_lim']
        fbw_min = params['fbw']
        ibias_max = params['ibias']

        # Somewhat arbitrary vstar_min in this case
        vstar_min = 0.25

        # Estimate threshold of each device TODO can this be more generalized?
        vth_in = estimate_vth(is_nch=True, vgs=vdd/2, vbs=0, db=db_dict['in'])
        vth_tail = estimate_vth(is_nch=True, vgs=vdd/2, vbs=0, db=db_dict['tail'])

        ibias_min = np.inf
        # Keeping track of operating points which work for future comparison
        viable_op_list = []

        # Sweep tail voltage
        vtail_vec = np.arange(vstar_min, vincm-vth_in, 10e-3)
        print(f'Sweeping tail from {vstar_min} to {vincm-vth_in}')
        for vtail in vtail_vec:
            # voutcm_min = vincm - vth_in
            # voutcm_vec = np.arange(voutcm_min, vdd, 10e-3)
            # print(f'Sweeping output common mode from {voutcm_min} to {vdd}')
            voutcm_vec = [vincm]
            # Sweep output common mode
            for voutcm in voutcm_vec:
                in_op = db_dict['in'].query(vgs=vincm-vtail,
                                            vds=voutcm-vtail,
                                            vbs=-vtail)
                ibias_min = 2*in_op['ibias']
                # Step input device size (integer steps)
                nf_in_max = int(round(ibias_max/ibias_min))
                nf_in_vec = np.arange(2, nf_in_max, 2)
                for nf_in in nf_in_vec:
                    # Check against best current
                    ibias = ibias_min * nf_in
                    if ibias > ibias_max:
                        # print(f"(FAIL) ibias {ibias}")
                        break

                    res_val = (vdd-voutcm)/(ibias/2)
                    # Check approximate gain, bandwidth
                    Rout = parallel(res_val, 1/(in_op['gds']*nf_in))
                    gain = in_op['gm']*nf_in * Rout
                    if gain < gain_min or gain > gain_max:
                        # print(f"(FAIL) gain {gain}")
                        break

                    Cout = cload + nf_in*in_op['cgg']#(in_op['cds'] + in_op['cgd']*gain)*nf_in
                    fbw = 1/(2*np.pi*Rout*Cout)
                    if fbw < fbw_min:
                        # print(f"(FAIL) fbw {fbw}")
                        continue

                    # Design tail to current match
                    vgtail_min = vth_tail + vstar_min
                    vgtail_max = vtail + vth_tail
                    vgtail_vec = np.arange(vgtail_min, vgtail_max, 10e-3)
                    for vgtail in vgtail_vec:
                        tail_op = db_dict['tail'].query(vgs=vgtail,
                                                        vds=vtail,
                                                        vbs=0)
                        tail_success, nf_tail = verify_ratio(in_op['ibias']*2,
                                                            tail_op['ibias'],
                                                            nf_in,
                                                            0.05)
                        if not tail_success:
                            continue
                        
                        viable_op = dict(nf_in=nf_in,
                                         nf_tail=nf_tail,
                                         res_val=res_val,
                                         voutcm=voutcm,
                                         vgtail=vgtail,
                                         gain=gain,
                                         fbw=fbw,
                                         vtail=vtail,
                                         ibias=tail_op['ibias']*nf_tail)
                        viable_op_list.append(viable_op)
                        print("\n(SUCCESS)")
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
        # TODO: real resistors
        res_params = dict(num_unit=1,
                          l=best_op['res_val']/600,
                          w=1,
                          intent='ideal')
        bulk_conn = 'VSS'

        sch_params = dict(diffpair_params=diffpair_params,
                          res_params=res_params,
                          bulk_conn=bulk_conn)

        print(f"(RESULT) {sch_params}\n{best_op}")

        return sch_params, best_op

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1
