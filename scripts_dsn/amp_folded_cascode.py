# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

import os
import pkg_resources
import numpy as np
from math import isnan
from pprint import pprint

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins

# noinspection PyPep8Naming
class bag2_analog__amp_folded_cascode_dsn(DesignModule):
    """Module for library bag2_analog cell amp_folded_cascode.
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
            in_type = '"p" or "n" for NMOS or PMOS input pair',
            diff_out = 'Boolean. True to have a differential output.',
            specfile_dict = 'Transistor database spec file names for each device',
            th_dict = 'Transistor flavor dictionary.',
            l_dict = 'Transistor channel length dictionary',
            sim_env = 'Simulation environment',
            vswing_lim = 'Tuple of lower and upper output swing from the bias',
            gain = '(Min, max) small signal gain target in V/V',
            fbw = 'Minimum bandwidth in Hz',
            pm = 'Minimum unity gain phase margin in degrees',
            vdd = 'Supply voltage in volts.',
            vincm = 'Input common mode voltage.',
            ibias = 'Maximum bias current, in amperes.',
            cload = 'Output load capacitance in farads.',
            optional_params = 'Optional parameters. voutcm=output bias voltage.'
        ))
        return ans

    def meet_spec(self, **params) -> List[Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.
        Returns collection of all possible solutions.
        Currently assumes biasing is all self-biased via drain-to-source diode connection
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
        in_type = params['in_type']
        diff_out = params['diff_out']
        vdd = params['vdd']
        vincm = params['vincm']
        vswing_low, vswing_high = params['vswing_lim']
        cload = params['cload']
        gain_min = params['gain']
        fbw_min = params['fbw']
        pm_min = params['pm']
        ibias_max = params['ibias']
        cload = params['cload']

        assert not diff_out, f'Currently only supports single-ended output with self-biasing'

        # Somewhat arbitrary vstar_min in this case
        vstar_min = 0.2

        # Estimate threshold of each device TODO can this be more generalized?
        n_in = in_type=='n'

        vtest_in = vdd/2 if n_in else -vdd/2
        vtest_tail = vdd/2 if n_in else -vdd/2
        vtest_load = -vdd/2 if n_in else vdd/2

        # same = the part of the cascode which touches the input pair
        vb_in = 0 if n_in else vdd
        vb_tail = 0 if n_in else vdd
        vb_load = vdd if n_in else 0
        vb_same = vdd if n_in else 0
        vb_opp = 0 if n_in else vdd

        db_same = db_dict['p'] if n_in else db_dict['n']
        db_opp = db_dict['n'] if n_in else db_dict['p']

        vth_in = estimate_vth(is_nch=n_in, vgs=vtest_in, vbs=0, db=db_dict['in'], lch=l_dict['in'])
        vth_p = estimate_vth(is_nch=False, vgs=-vdd/2, vbs=0, db=db_dict['p'], lch=l_dict['p'])
        vth_n = estimate_vth(is_nch=True, vgs=vdd/2, vbs=0, db=db_dict['n'], lch=l_dict['n'])
        vth_tail = estimate_vth(is_nch=n_in, vgs=vtest_tail, vbs=0, db=db_dict['tail'], lch=l_dict['tail'])
        vth_same = vth_p if n_in else vth_n
        vth_opp = vth_n if n_in else vth_p

        ibias_min = np.inf
        # Keeping track of operating points which work for future comparison
        viable_op_list = []

        # Sweep output bias (or use optional input)
        voutcm_min = max((vth_n+vstar_min)*2, vstar_min*2+vswing_low) if n_in else vstar_min*2+vswing_low
        voutcm_max = vdd-(vstar_min*2)-vswing_high if n_in else min(vdd+vth_p*2-vstar_min*2, vdd-vstar_min*2-vswing_high)
        voutcm_opt = optional_params.get('voutcm', None)
        if voutcm_opt == None:
            voutcm_vec = np.arange(voutcm_min, voutcm_max, 10e-3)
        elif voutcm_opt < voutcm_min or voutcm_opt > voutcm_max:
            raise ValueError(f'No solution. voutcm value {voutcm_opt} falls outside ({voutcm_min}, {voutcm_max})')
        else:
            voutcm_vec = [voutcm_opt]
        print(f"voutcm {min(voutcm_vec)} to {max(voutcm_vec)}")
        for voutcm in voutcm_vec:
            # Sweep tail voltage
            vtail_min = vstar_min if n_in else vincm-vth_in
            vtail_max = vincm-vth_in if n_in else vdd-vstar_min
            vtail_vec = np.arange(vtail_min, vtail_max, 10e-3)
            print(f'vtail {vtail_min} to {vtail_max}')
            for vtail in vtail_vec:
                vgtail_min = vth_n+vstar_min if n_in else vtail+vth_p
                vgtail_max = vtail+vth_n if n_in else vdd+vth_p-vstar_min
                vgtail_vec = np.arange(vgtail_min, vgtail_max, 10e-3)
                if vgtail_min == vgtail_max:
                    vgtail_vec = [vgtail_min]
                print(f'******* vgtail {vgtail_min} to {vgtail_max}')

                # Sweep vout1 bias point
                vout1_min = max(vincm-vth_in, voutcm+vstar_min) if n_in else vstar_min
                vout1_max = vdd-vstar_min if n_in else min(vincm-vth_in, voutcm-vstar_min)
                vout1_vec = np.arange(vout1_min, vout1_max, 10e-3)
                print(f'* vout1 {vout1_min} to {vout1_max}')
                for vout1 in vout1_vec:
                    op_in = db_dict['in'].query(vgs=vincm-vtail, vds=vout1-vtail, vbs=vb_in-vtail)

                    # Sweep gate voltage of outer device in cascode connected to diffpair
                    vg_same_outer_min = vout1+vth_p if n_in else vth_n+vstar_min
                    vg_same_outer_max = vdd+vth_p-vstar_min if n_in else vout1+vth_n
                    vg_same_outer_vec = np.arange(max(vg_same_outer_min, 0), vg_same_outer_max, 10e-3)
                    print(f'** vg_same_outer {vg_same_outer_min} to {vg_same_outer_max}')
                    for vg_same_outer in vg_same_outer_vec:
                        op_same_outer = db_same.query(vgs=vg_same_outer-vb_same,
                                                      vds=vout1-vb_same,
                                                      vbs=0)
                        nf_same_outer_max = int(round((ibias_max/op_same_outer['ibias']) / 2))
                        # Sweep the gate voltage of the inner "same"-side device
                        vg_same_inner_min = voutcm+vth_p if n_in else vout1+vth_n+vstar_min
                        vg_same_inner_max = vout1+vth_p-vstar_min if n_in else voutcm+vth_n
                        vg_same_inner_vec = np.arange(max(0, vg_same_inner_min), vg_same_inner_max, 10e-3)
                        print(f'*** vg_same_inner {vg_same_inner_min} to {vg_same_inner_max}')
                        for vg_same_inner in vg_same_inner_vec:
                            op_same_inner = db_same.query(vgs=vg_same_inner_min-vout1, vds=voutcm-vout1, vbs=vb_same-vout1)
                            # Sweep the gate voltage of the outer "opposite"-side device
                            vg_opp_outer_min = vth_n+vstar_min if n_in else voutcm+vth_p-vstar_min
                            vg_opp_outer_max = voutcm-vth_n-vstar_min if n_in else vdd+vth_p-vstar_min
                            vg_opp_outer_vec = np.arange(max(vg_opp_outer_min, 0), vg_opp_outer_max, 10e-3)
                            print(f'**** vg_opp_outer {vg_opp_outer_min} to {vg_opp_outer_max}')
                            for vg_opp_outer in vg_opp_outer_vec:
                                op_opp_outer = db_opp.query(vgs=vg_opp_outer-vb_opp, vds=vg_opp_outer-vb_opp, vbs=0)
                                op_opp_inner = db_opp.query(vgs=voutcm-vg_opp_outer, vds=voutcm-vg_opp_outer, vbs=vb_opp-vg_opp_outer)
                                # Sweep device sizes to meet current
                                nf_same_outer_vec = np.arange(2, nf_same_outer_max, 2)
                                print(f'***** nf_same_outer {2} to {nf_same_outer_max}')
                                for nf_same_outer in nf_same_outer_vec:
                                    # Sweep the proportion of the current split between the input devices vs. rest of the cascode
                                    # Match device sizing for desired current (since prior loops already give bias voltages)
                                    ibranch_big = op_same_outer['ibias']*nf_same_outer
                                    nf_in_max = int(round(ibranch_big/op_in['ibias']))
                                    nf_in_vec = np.arange(2, nf_in_max, 1)
                                    print(f'****** nf_in {2} to {nf_in_max}')
                                    for nf_in in nf_in_vec:
                                        ibranch_in = op_in['ibias']*nf_in
                                        ibranch_small = ibranch_big - ibranch_in
                                        match_small, nf_opp_outer = verify_ratio(ibranch_small,
                                                                                 op_opp_outer['ibias'],
                                                                                 1, 0.01)
                                        if not match_small:
                                            # print("x opp outer match", flush=True)
                                            continue

                                        match_small, nf_opp_inner = verify_ratio(ibranch_small,
                                                                                 op_opp_inner['ibias'],
                                                                                 1, 0.01)

                                        if not match_small:
                                            # print("x opp inner match", flush=True)
                                            continue

                                        match_small, nf_same_inner = verify_ratio(ibranch_small,
                                                                                  op_same_inner['ibias'],
                                                                                  1, 0.01)
                                        if not match_small:
                                            # print("x same inner match", flush=True)
                                            continue

                                        # Sweep potential tail gate voltage and match tail sizing
                                        # vgtail_min = vth_n+vstar_min if n_in else vtail+vth_p
                                        # vgtail_max = vtail+vth_n if n_in else vdd+vth_p-vstar_min
                                        # vgtail_vec = np.arange(vgtail_min, vgtail_max, 10e-3)
                                        # if vgtail_min == vgtail_max:
                                        #     vgtail_vec = [vgtail_min]
                                        # print(f'******* vgtail {vgtail_min} to {vgtail_max}')
                                        for vgtail in vgtail_vec:
                                            op_tail = db_dict['tail'].query(vgs=vgtail-vb_tail, vds=vtail-vb_tail, vbs=0)
                                            match_tail, nf_tail = verify_ratio(ibranch_in*2,
                                                                               op_tail['ibias'],
                                                                               1, 0.01)
                                            if not match_tail:
                                                # print(f"tail match {nf_tail}")
                                                continue

                                            # Construct LTICircuit to check small signal against spec
                                            op_dict = {'in' : op_in,
                                                       'tail' : op_tail,
                                                       'same_outer' : op_same_outer,
                                                       'same_inner' : op_same_inner,
                                                       'opp_inner' : op_opp_inner,
                                                       'opp_outer' : op_opp_outer}
                                            nf_dict = {'in' : nf_in,
                                                       'tail' : nf_tail,
                                                       'same_outer' : nf_same_outer,
                                                       'same_inner' : nf_same_inner,
                                                       'opp_inner' : nf_opp_inner,
                                                       'opp_outer' : nf_opp_outer}
                                            bias_dict = {'vgtail': vgtail,
                                                         'voutcm': voutcm,
                                                         'vout1' : vout1,
                                                         'vg_opp_outer' : vg_opp_outer,
                                                         'vg_same_inner' : vg_same_inner,
                                                         'vg_same_outer' : vg_same_outer,
                                                         'vtail' : vtail,
                                                         'ibranch_in' : ibranch_in,
                                                         'ibranch_big' : ibranch_big,
                                                         'ibranch_small' : ibranch_small}
                                            
                                            ckt_p = self.make_ltickt(op_dict=op_dict, nf_dict=nf_dict, meas_side='p', cload=cload)
                                            p_num, p_den = ckt_p.get_num_den(in_name='inp', out_name='out', in_type='v')

                                            ckt_n = self.make_ltickt(op_dict=op_dict, nf_dict=nf_dict, meas_side='n', cload=cload)
                                            n_num, n_den = ckt_n.get_num_den(in_name='inn', out_name='out', in_type='v')

                                            num, den = num_den_add(p_num, np.convolve(n_num, [-1]),
                                                                   p_den, n_den)
                                            num = np.convolve(num, [0.1])

                                            gain = num[-1]/den[-1]
                                            wbw = get_w_3db(num, den)
                                            pm, _ = get_stability_margins(num, den)

                                            if wbw == None:
                                                wbw = 0
                                            fbw = wbw/(2*np.pi)

                                            if fbw < fbw_min:
                                                print(f"bw: {fbw}")
                                                continue

                                            if isnan(pm) or pm < pm_min:
                                                print(f"pm: {pm}")
                                                continue
                                            
                                            if gain < gain_min:
                                                pprint(nf_dict)
                                                pprint(bias_dict)
                                                print(f"gain: {gain}")
                                                raise ValueError("Pause")
                                                break

                                            viable_op = dict(nf_dict=nf_dict,
                                                             voutcm=voutcm,
                                                             gain=gain,
                                                             fbw=fbw,
                                                             pm=pm,
                                                             vgtail=vgtail,
                                                             vtail=vtail,
                                                             vout1=vout1,
                                                             vg_same_outer=vg_same_outer,
                                                             vg_same_inner=vg_same_inner,
                                                             vg_opp_outer=vg_opp_outer,
                                                             ibias=op_same_outer['ibias']*nf_same_outer*2)
                                            viable_op_list.append(viable_op)
                                            print("(SUCCESS)")
                                            print(viable_op)

        self.other_params = dict(in_type=in_type,
                                 w_dict={k:db.width_list[0] for k,db in db_dict.items()},
                                 l_dict=l_dict,
                                 th_dict=th_dict)

        return viable_op_list

    def make_ltickt(self, op_dict:Mapping[str,Any], nf_dict:Mapping[str,int], cload:float, meas_side:str) -> LTICircuit:
        ckt = LTICircuit()
        inp_conn = 'gnd' if meas_side=='n' else 'inp'
        inn_conn = 'gnd' if meas_side=='p' else 'inn'

        ckt.add_transistor(op_dict['in'], 'out1n', inp_conn, 'tail', fg=nf_dict['in'], neg_cap=False)
        ckt.add_transistor(op_dict['in'], 'out1p', inn_conn, 'tail', fg=nf_dict['in'], neg_cap=False)
        ckt.add_transistor(op_dict['tail'], 'tail', 'gnd', 'gnd', fg=nf_dict['tail'], neg_cap=False)
        ckt.add_transistor(op_dict['same_outer'], 'out1n', 'gnd', 'gnd', fg=nf_dict['same_outer'], neg_cap=False)
        ckt.add_transistor(op_dict['same_outer'], 'out1p', 'gnd', 'gnd', fg=nf_dict['same_outer'], neg_cap=False)
        ckt.add_transistor(op_dict['same_inner'], 'outx', 'gnd', 'out1n', fg=nf_dict['same_inner'], neg_cap=False)
        ckt.add_transistor(op_dict['same_inner'], 'out', 'gnd', 'out1p', fg=nf_dict['same_inner'], neg_cap=False)
        ckt.add_transistor(op_dict['opp_inner'], 'outx', 'outx', 'gopp', fg=nf_dict['opp_inner'], neg_cap=False)
        ckt.add_transistor(op_dict['opp_inner'], 'out', 'outx', 'goppx', fg=nf_dict['opp_inner'], neg_cap=False)
        ckt.add_transistor(op_dict['opp_outer'], 'gopp', 'gopp', 'gnd', fg=nf_dict['opp_outer'], neg_cap=False)
        ckt.add_transistor(op_dict['opp_outer'], 'goppx', 'gopp', 'gnd', fg=nf_dict['opp_outer'], neg_cap=False)
        ckt.add_cap(cload, 'out', 'gnd')
        return ckt


    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1

    def get_sch_params(self, op):
        return dict()