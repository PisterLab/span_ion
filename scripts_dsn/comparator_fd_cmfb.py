# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any

import os
import pkg_resources
import numpy as np

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins

# noinspection PyPep8Naming
class span_ion__comparator_fd_cmfb_dsn(DesignModule):
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
            fbw = 'Minimum bandwidth in Hz',
            ugf = 'Minimum unity gain frequency in Hz',
            vdd = 'Supply voltage in volts.',
            vincm = 'Input common mode voltage.',
            voutcm = 'Output common mode target voltage.',
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
        voutcm = params['voutcm']
        cload = params['cload']
        fbw_min = params['fbw']
        ugf_min = params['ugf']
        ibias_max = params['ibias']

        # Somewhat arbitrary vstar_min in this case
        vstar_min = 0.25

        # Estimate threshold of each device TODO can this be more generalized?
        vth_in = estimate_vth(is_nch=False, vgs=-vdd/2, vbs=0, db=db_dict['in'])
        vth_tail = estimate_vth(is_nch=False, vgs=-vdd/2, vbs=0, db=db_dict['tail'])
        vth_out = estimate_vth(is_nch=True, vgs=vdd/2, vbs=0, db=db_dict['out'])

        ibias_min = np.inf
        # Keeping track of operating points which work for future comparison
        viable_op_list = []

        # Sweep tail voltage
        vtail_vec = np.arange(vincm-vth_in, vdd-vstar_min, 10e-3)
        # print(f'Sweeping tail from {vincm-vth_in} to {vdd-vstar_min}')
        for vtail in vtail_vec:
            in_op = db_dict['in'].query(vgs=vincm-vtail,
                                        vds=voutcm-vtail,
                                        vbs=vdd-vtail)
            out_op = db_dict['out'].query(vgs=voutcm,
                                          vds=voutcm,
                                          vbs=0)
            ibias_min = 4*abs(in_op['ibias'])
            # Step input device size (integer steps)
            nf_in_max = int(round(ibias_max/ibias_min))
            nf_in_vec = np.arange(1, nf_in_max, 1)
            # print(f'Number of input devices from 1 to {nf_in_max}')
            for nf_in in nf_in_vec:
                ibias = ibias_min * nf_in
                if ibias > ibias_max:
                    # print("(FAIL) ibias")
                    break

                # Match load device size
                out_match, nf_out = verify_ratio(abs(in_op['ibias']*2),
                                                abs(out_op['ibias']),
                                                nf_in,
                                                0.05)

                if not out_match:
                    # print("(FAIL) out match")
                    continue

                # Check target specs
                Rout = parallel(1/(nf_in*2*in_op['gds']), 
                                1/(nf_out*out_op['gm']),
                                1/(nf_out*out_op['gds']))
                Gm = abs(in_op['gm'])*nf_in*2
                gain = Gm * Rout
                Cout = cload + (nf_in*2*in_op['cgs']) + (1+gain)*(nf_in*2*in_op['cds'])
                fbw = 1/(2*np.pi*Rout*Cout)
                ugf = Gm / Cout * (1/2*np.pi)
                if fbw < fbw_min:
                    # print(f"(FAIL) fbw {fbw}")
                    continue

                if ugf < ugf_min:
                    # print(f"(FAIL) ugf {ugf}")
                    break

                # Design matching tail
                vgtail_min = vtail + vth_tail
                vgtail_max = vdd + vth_tail - vstar_min
                vgtail_vec = np.arange(vgtail_min, vgtail_max, 10e-3)
                # print(f"Tail gate from {vgtail_min} to {vgtail_max}")
                for vgtail in vgtail_vec:
                    tail_op = db_dict['tail'].query(vgs=vgtail-vdd,
                                                    vds=vtail-vdd,
                                                    vbs=0)
                    tail_match, nf_tail = verify_ratio(abs(in_op['ibias']*4),
                                                       abs(tail_op['ibias']),
                                                       nf_in,
                                                       0.05)

                    if not tail_match:
                        # print("(FAIL) tail match")
                        continue

                    print('(SUCCESS)')
                    viable_op = dict(nf_in=nf_in,
                                     nf_out=nf_out,
                                     nf_tail=nf_tail,
                                     vgtail=vgtail,
                                     fbw=fbw,
                                     ugf=ugf,
                                     vtail=vtail,
                                     ibias=abs(tail_op['ibias'])*nf_tail)
                    print(viable_op)
                    viable_op_list.append(viable_op)

        if len(viable_op_list) < 1:
            raise ValueError("No solution")

        # Find the best operating point among those which do
        best_op = dict(ibias=np.inf)
        for op in viable_op_list:
            best_op = self.op_compare(best_op, op)


        # Arranging schematic parameters
        sch_params = dict(lch_dict=l_dict,
                          wch_dict={k:db.width_list[0] for k, db in db_dict.items()},
                          th_dict=th_dict,
                          seg_dict={'in': best_op['nf_in'],
                                      'out': best_op['nf_out'],
                                      'tail': best_op['nf_tail']})

        print(f"(RESULT) {sch_params}\n{best_op}")

        return sch_params, best_op

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1
