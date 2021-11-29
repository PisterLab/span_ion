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
class bag2_analog__amp_diff_mirr_bias_dsn(DesignModule):
    """Module for library bag2_analog cell amp_diff_mirr_bias.

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
            in_type='"p" or "n" for NMOS or PMOS input pair',
            specfile_dict='Transistor database spec file names for each device',
            th_dict='Transistor flavor dictionary.',
            l_dict='Transistor channel length dictionary',
            sim_env='Simulation environment',
            vswing_lim='Tuple of lower and upper swing from the bias',
            gain='(Min, max) small signal gain target in V/V',
            fbw='Minimum bandwidth in Hz',
            ugf='Minimum unity gain frequency in Hz',
            pm='Minimum unity gain phase margin (calculated from in/out transfer function, does not account for changes in biaing)',
            vdd='Supply voltage in volts.',
            vincm='Input common mode voltage.',
            ibias='Maximum bias current, in amperes.',
            cload='Output load capacitance in farads.',
            optional_params='Optional parameters. voutcm=output bias voltage. res_vstep, vstar_min, error_tol, vstar_in_min'
        ))
        return ans

    def meet_spec(self, **params) -> List[Mapping[str, Any]]:
        """To be overridden by subclasses to design this module.
        Returns collection of all possible solutions.
        Raises a ValueError if there is no solution.
        """
        optional_params = params['optional_params']

        ### Get DBs for each device
        specfile_dict = params['specfile_dict']
        l_dict = params['l_dict']
        th_dict = params['th_dict']
        sim_env = params['sim_env']

        # Databases
        db_dict = {k: get_mos_db(spec_file=specfile_dict[k],
                                 intent=th_dict[k],
                                 sim_env=sim_env,
                                 lch=l_dict[k]) for k in specfile_dict.keys()}


        ### Design devices
        in_type = params['in_type']
        vdd = params['vdd']
        vincm = params['vincm']
        vswing_low, vswing_high = params['vswing_lim']
        cload = params['cload']
        gain_min, gain_max = params['gain']
        fbw_min = params['fbw']
        ugf_min = params['ugf']
        pm_min = params['pm']
        ibias_max = params['ibias']

        # Somewhat arbitrary vstar_min in this case
        vstar_min = optional_params.get('vstar_min', 0.2)
        res_vstep = optional_params.get('res_vstep', 10e-3)
        error_tol = optional_params.get('error_tol', 0.01)
        vstar_in_min = optional_params.get('vstar_in_min', 0.1)

        # Estimate threshold of each device TODO can this be more generalized?
        n_in = in_type == 'n'

        vtest_in = vdd / 2 if n_in else -vdd / 2
        vtest_tail = vdd / 2 if n_in else -vdd / 2
        vtest_load = -vdd / 2 if n_in else vdd / 2

        vb_in = 0 if n_in else vdd
        vb_tail = 0 if n_in else vdd
        vb_load = vdd if n_in else 0

        vth_in = estimate_vth(is_nch=n_in, vgs=vtest_in, vbs=0, db=db_dict['in'], lch=l_dict['in'])
        vth_load = estimate_vth(is_nch=(not n_in), vgs=vtest_load, vbs=0, db=db_dict['load'], lch=l_dict['load'])
        vth_tail = estimate_vth(is_nch=n_in, vgs=vtest_tail, vbs=0, db=db_dict['tail'], lch=l_dict['tail'])

        # Keeping track of operating points which work for future comparison
        viable_op_list = []

        # Sweep tail voltage
        vtail_min = vstar_min if n_in else vincm - vth_in + vstar_in_min
        vtail_max = vincm - vth_in - vstar_in_min if n_in else vdd - vstar_min
        vtail_vec = np.arange(vtail_min, vtail_max, res_vstep)
        print(f'Sweeping tail from {vtail_min} to {vtail_max}')

        for vtail in vtail_vec:
            # Sweep output common mode or use taken-in optional parameter
            voutcm_min = max(vincm - vth_in + vswing_low, vtail) if n_in else vstar_min + vth_load + vswing_low
            voutcm_max = vdd + vth_load - vstar_min - vswing_high if n_in else min(vincm - vth_in - vswing_high, vtail)

            voutcm_opt = optional_params.get('voutcm', None)
            if voutcm_opt == None:
                voutcm_vec = np.arange(voutcm_min, voutcm_max, res_vstep)
            elif (n_in and (voutcm_opt < vtail)) or ((not n_in) and (voutcm_opt > vtail)):
                warnings.warn(f'voutcm {voutcm_opt} vs. vtail {vtail}')
                continue
            elif voutcm_opt < voutcm_min or voutcm_opt > voutcm_max:
                warnings.warn(f'voutcm {voutcm_opt} not in [{voutcm_min}, {voutcm_max}]')
                voutcm_vec = [voutcm_opt]
            else:
                voutcm_vec = [voutcm_opt]

            for voutcm in voutcm_vec:
                in_op = db_dict['in'].query(vgs=vincm - vtail,
                                            vds=voutcm - vtail,
                                            vbs=vb_in - vtail)
                load_op = db_dict['load'].query(vgs=voutcm - vb_load,
                                                vds=voutcm - vb_load,
                                                vbs=0)
                ibias_min = 2 * in_op['ibias']
                # Step input device size (integer steps)
                nf_in_max = int(round(ibias_max / ibias_min))
                nf_in_vec = np.arange(1, nf_in_max, 1)
                # print(nf_in_max)
                for nf_in in nf_in_vec:
                    # Match device sizing for input and load
                    match_load, nf_load = verify_ratio(in_op['ibias'],
                                                       load_op['ibias'],
                                                       nf_in,
                                                       error_tol)
                    if not match_load:
                        # assert False, 'blep'
                        print(f"Load match {nf_load}")
                        continue

                    # Design tail to current match
                    vgtail_min = vth_tail + vstar_min if n_in else vtail + vth_tail
                    vgtail_max = vtail + vth_tail if n_in else vdd + vth_tail - vstar_min
                    vgtail_vec = np.arange(vgtail_min, vgtail_max, res_vstep)
                    for vgtail in vgtail_vec:
                        tail_op = db_dict['tail'].query(vgs=vgtail - vb_tail,
                                                        vds=vtail - vb_tail,
                                                        vbs=0)
                        tail_success, nf_tail = verify_ratio(in_op['ibias'] * 2,
                                                             tail_op['ibias'],
                                                             nf_in,
                                                             error_tol)
                        if not tail_success:
                            print('Tail match')
                            continue

                        # Check against spec again, now with full circuit
                        op_dict = {'in': in_op,
                                   'tail': tail_op,
                                   'load': load_op}
                        nf_dict = {'in': nf_in,
                                   'tail': nf_tail,
                                   'load': nf_load}

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

                        viable_op = dict(nf_in=int(nf_in),
                                         nf_tail=int(nf_tail),
                                         nf_load=int(nf_load),
                                         voutcm=float(voutcm),
                                         vgtail=float(vgtail),
                                         gain=float(gain_lti),
                                         fbw=float(fbw_lti),
                                         ugf=float(ugf_lti),
                                         pm=float(pm_lti),
                                         vtail=float(vtail),
                                         ibias=float(tail_op['ibias'] * nf_tail),
                                         op_in=in_op,
                                         op_tail=tail_op,
                                         op_load=load_op)
                        viable_op_list.append(viable_op)
                        print("\n(SUCCESS)")
                        print(viable_op)

        self.other_params = dict(in_type=in_type,
                                 w_dict={k: db.width_list[0] for k, db in db_dict.items()},
                                 l_dict=l_dict,
                                 th_dict=th_dict)

        return viable_op_list

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

    def make_ltickt(self, op_dict: Mapping[str, Any], nf_dict: Mapping[str, int],
                    cload: float, meas_side: str) -> LTICircuit:
        inn_conn = 'gnd' if meas_side == 'p' else 'inn'
        inp_conn = 'gnd' if meas_side == 'n' else 'inp'

        ckt = LTICircuit()
        ckt.add_transistor(op_dict['tail'], 'tail', 'gnd', 'gnd', fg=nf_dict['tail'])
        ckt.add_transistor(op_dict['in'], 'out', inn_conn, 'tail', fg=nf_dict['in'])
        ckt.add_transistor(op_dict['in'], 'outx', inp_conn, 'tail', fg=nf_dict['in'])
        ckt.add_transistor(op_dict['load'], 'outx', 'outx', 'gnd', fg=nf_dict['load'])
        ckt.add_transistor(op_dict['load'], 'out', 'outx', 'gnd', fg=nf_dict['load'])
        ckt.add_cap(cload, 'out', 'gnd')

        return ckt

    def op_compare(self, op1: Mapping[str, Any], op2: Mapping[str, Any]):
        """Returns the best operating condition based on
        minimizing bias current.
        """
        return op2 if op2['gain'] > op1['gain'] else op1

    def get_sch_params(self, op):
        l_dict = self.other_params['l_dict']
        w_dict = self.other_params['w_dict']
        seg_dict = {'in': op['nf_in'],
                    'tail': op['nf_tail'],
                    'load': op['nf_load'],
                    'bias': op['nf_bias']}

        for k, v in l_dict.items():
            l_dict[k] = float(v)

        for k, v in w_dict.items():
            w_dict[k] = float(v)

        for k, v in seg_dict.items():
            seg_dict[k] = int(v)

        return dict(in_type=self.other_params['in_type'],
                    l_dict=l_dict,
                    w_dict=w_dict,
                    th_dict=self.other_params['th_dict'],
                    seg_dict=seg_dict)