# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

import os
import pkg_resources
import numpy as np

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins, get_w_crossings


# noinspection PyPep8Naming
class span_ion__comparator_fd_cmfb3_dsn(DesignModule):
    """Module for library span_ion cell comparator_fd_cmfb3.

    Fill in high level description here.
    """

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
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
            in_type='Input pair type',
            specfile_dict='Transistor database spec file names for each device',
            th_dict='Transistor flavor dictionary.',
            l_dict='Transistor channel length dictionary',
            sim_env='Simulation environment',
            gain='(min, max) gain',
            fbw='Minimum bandwidth in Hz',
            ugf='Minimum unity gain frequency in Hz',
            pm='Minimum phase margin in degrees',
            vdd='Supply voltage in volts.',
            vincm='Input common mode voltage.',
            voutcm='Output common mode target voltage.',
            ibias='Maximum bias current, in amperes.',
            cload='Output load capacitance in farads.',
            optional_params='vstar_min, error_tol, res_vstep, vstar_in_min'
        ))
        return ans

    def meet_spec(self, **params) -> List[Mapping[str, Any]]:
        """To be overridden by subclasses to design this module.

        Raises a ValueError if there is no solution.
        """
        ### Get DBs for each device
        specfile_dict = params['specfile_dict']
        l_dict = params['l_dict']
        th_dict = params['th_dict']
        sim_env = params['sim_env']

        # Databases
        db_dict = {k: get_mos_db(spec_file=specfile_dict[k],
                                 intent=th_dict[k],
                                 lch=l_dict[k],
                                 sim_env=sim_env) for k in specfile_dict.keys()}

        ### Design devices
        in_type = params['in_type']
        vdd = params['vdd']
        vincm = params['vincm']
        voutcm = params['voutcm']
        cload = params['cload']
        fbw_min = params['fbw']
        gain_min, gain_max = params['gain']
        ugf_min = params['ugf']
        pm_min = params['pm']
        ibias_max = params['ibias']

        # Get optional parameters
        optional_params = params['optional_params']
        vstar_min = optional_params.get('vstar_min', 0.2)
        res_vstep = optional_params.get('res_vstep', vdd/1e3)
        error_tol = optional_params.get('error_tol', 0.01)
        vstar_in_min = optional_params.get('vstar_in_min', 0.1)

        n_in = in_type == 'n'
        vtest_in = vdd / 2 if n_in else -vdd / 2
        vtest_tail = vdd / 2 if n_in else -vdd / 2
        vtest_out = -vdd / 2 if n_in else vdd / 2

        vb_in = 0 if n_in else vdd
        vb_tail = 0 if n_in else vdd
        vb_out = vdd if n_in else 0

        # Estimate threshold of each device
        vth_in = estimate_vth(is_nch=n_in, vgs=vtest_in, vbs=0, db=db_dict['in'], lch=l_dict['in'])
        vth_tail = estimate_vth(is_nch=n_in, vgs=vtest_tail, vbs=0, db=db_dict['tail'], lch=l_dict['tail'])
        vth_out = estimate_vth(is_nch=(not n_in), vgs=vtest_out, vbs=0, db=db_dict['out'], lch=l_dict['out'])

        # Keeping track of operating points which work for future comparison
        viable_op_list = []
        op_dict = dict()
        nf_dict = dict()

        # Sweep tail voltage
        vtail_min = vstar_min if n_in else vincm-vth_in+vstar_in_min
        vtail_max = vincm-vth_in-vstar_in_min if n_in else vdd-vstar_min
        vtail_vec = np.arange(vtail_min, vtail_max, res_vstep)
        print(f'Sweeping tail from {vtail_min} to {vtail_max}')
        for vtail in vtail_vec:
            in_op = db_dict['in'].query(vgs=vincm - vtail,
                                        vds=voutcm - vtail,
                                        vbs=vb_in - vtail)
            out_op = db_dict['out'].query(vgs=voutcm - vb_out,
                                          vds=voutcm - vb_out,
                                          vbs=0)
            ibias_min = 4 * abs(in_op['ibias'])
            # Step input device size (integer steps)
            nf_in_max = int(round(ibias_max / ibias_min))
            nf_in_vec = np.arange(1, nf_in_max, 1)
            print(f'Number of input devices from 1 to {nf_in_max}')
            for nf_in in nf_in_vec:
                ibias = ibias_min * nf_in
                if ibias > ibias_max:
                    print(f'ibias {ibias}')
                    break

                # Match load device size
                out_match, nf_out = verify_ratio(in_op['ibias'] * 2,
                                                 out_op['ibias'],
                                                 nf_in,
                                                 error_tol)

                if not out_match:
                    print("out match")
                    continue

                # Design tail
                vgtail_min = vth_tail + vstar_min if n_in else vtail + vth_tail
                vgtail_max = vtail + vth_tail if n_in else vdd + vth_tail - vstar_min
                vgtail_vec = np.arange(vgtail_min, vgtail_max, res_vstep)
                print(f"Tail gate from {vgtail_min} to {vgtail_max}")
                for vgtail in vgtail_vec:
                    tail_op = db_dict['tail'].query(vgs=vgtail - vb_tail,
                                                    vds=vtail - vb_tail,
                                                    vbs=0)
                    tail_match, nf_tail = verify_ratio(in_op['ibias'] * 4,
                                                       tail_op['ibias'],
                                                       nf_in,
                                                       error_tol)

                    if not tail_match or nf_tail%2 != 0:
                        print(f"tail match {nf_tail}" if not tail_match else f'tail even {nf_tail}')
                        continue

                    # Check spec
                    op_dict['in'] = in_op
                    op_dict['tail'] = tail_op
                    op_dict['out'] = out_op

                    nf_dict['in'] = nf_in
                    nf_dict['tail'] = nf_tail
                    nf_dict['out'] = nf_out

                    gain_lti, fbw_lti, ugf_lti, pm_lti = self._get_ss_lti(op_dict=op_dict,
                                                                          nf_dict=nf_dict,
                                                                          cload=cload)

                    if gain_lti < gain_min or gain_lti > gain_max:
                        print(f'gain {gain_lti}')
                        break

                    if fbw_lti < fbw_min:
                        print(f'fbw {fbw_lti}')
                        continue

                    if ugf_lti < ugf_min:
                        print(f'ugf {ugf_lti}')
                        continue

                    if pm_lti < pm_min:
                        print(f'pm {pm_lti}')
                        continue

                    print('(SUCCESS)')
                    viable_op = dict(nf_in=nf_in,
                                     nf_out=nf_out,
                                     nf_tail=nf_tail,
                                     vgtail=vgtail,
                                     gain=gain_lti,
                                     fbw=fbw_lti,
                                     ugf=ugf_lti,
                                     pm=pm_lti,
                                     vtail=vtail,
                                     ibias=abs(tail_op['ibias']) * nf_tail)
                    print(viable_op)
                    viable_op_list.append(viable_op)
        self.other_params = dict(in_type=in_type,
                                 lch_dict=l_dict,
                                 wch_dict={k: db.width_list[0] for k, db in db_dict.items()},
                                 th_dict=th_dict)

        return viable_op_list

    def op_compare(self, op1: Mapping[str, Any], op2: Mapping[str, Any]):
        """Returns the best operating condition based on
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1

    def get_sch_params(self, op):
        lch_dict = self.other_params['lch_dict']
        wch_dict = self.other_params['wch_dict']
        seg_dict = {'in': op['nf_in'],
                    'tail': op['nf_tail'],
                    'out': op['nf_out']}

        ### Cleaning up data types for yaml readability
        for k, v in lch_dict.items():
            lch_dict[k] = float(v)

        for k, v in wch_dict.items():
            wch_dict[k] = float(v)

        for k, v in seg_dict.items():
            seg_dict[k] = int(v)

        return dict(in_type=self.other_params['in_type'],
                    lch_dict=lch_dict,
                    wch_dict=wch_dict,
                    th_dict=self.other_params['th_dict'],
                    seg_dict=seg_dict)

    def _get_ss_lti(self, op_dict: Mapping[str, Any],
                    nf_dict: Mapping[str, int],
                    cload: float) -> Tuple[float, float]:
        ckt_p = self.make_ltickt(op_dict=op_dict, nf_dict=nf_dict, cload=cload, meas_side='p')
        p_num, p_den = ckt_p.get_num_den(in_name='inp', out_name='out', in_type='v')

        ckt_n = self.make_ltickt(op_dict=op_dict, nf_dict=nf_dict, cload=cload, meas_side='n')
        n_num, n_den = ckt_n.get_num_den(in_name='inn', out_name='out', in_type='v')

        num, den = num_den_add(p_num, np.convolve(n_num, [-1]),
                               p_den, n_den)

        num = np.convolve(num, [0.5])

        gain = num[-1] / den[-1]
        wbw = get_w_3db(num, den)
        pm, _ = get_stability_margins(num, den)
        ugw, _ = get_w_crossings(num, den)

        if wbw == None:
            wbw = 0
        fbw = wbw / (2 * np.pi)

        if ugw == None:
            ugw = 0
        ugf = ugw / (2 * np.pi)

        return gain, fbw, ugf, pm

    def make_ltickt(self, op_dict:Mapping[str,Any], nf_dict:Mapping[str,int],
                    cload:float, meas_side:str) -> LTICircuit:
        inn_conn = 'gnd' if meas_side=='p' else 'inn'
        inp_conn = 'gnd' if meas_side=='n' else 'inp'

        ckt = LTICircuit()
        ckt.add_transistor(op_dict['tail'], 'tail', 'gnd', 'gnd', fg=nf_dict['tail'])
        ckt.add_transistor(op_dict['in'], 'out', inn_conn, 'tail', fg=nf_dict['in']*2)
        ckt.add_transistor(op_dict['in'], 'outx', inp_conn, 'tail', fg=nf_dict['in']*2)
        ckt.add_transistor(op_dict['out'], 'outx', 'outx', 'gnd', fg=nf_dict['out'])
        ckt.add_transistor(op_dict['out'], 'out', 'outx', 'gnd', fg=nf_dict['out'])
        ckt.add_cap(cload, 'out', 'gnd')

        return ckt