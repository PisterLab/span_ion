# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any

import os
import pkg_resources
import numpy as np

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins

# noinspection PyPep8Naming
class bag2_analog__amp_gm_mirr_dsn(DesignModule):
    """Module for library bag2_analog cell amp_gm_mirr.

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
            in_type = '"p" or "n" for NMOS or PMOS input pair',
            specfile_dict = 'Transistor database spec file names for each device',
            th_dict = 'Transistor flavor dictionary.',
            l_dict = 'Transistor channel length dictionary',
            sim_env = 'Simulation environment',
            vswing_lim = 'Tuple of lower and upper swing from the bias',
            gain = '(Min, max) small signal gain target in V/V',
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
        in_type = params['in_type']
        vdd = params['vdd']
        vincm = params['vincm']
        vswing_low, vswing_high = params['vswing_lim']
        cload = params['cload']
        gain_min = params['gain']
        fbw_min = params['fbw']
        ibias_max = params['ibias']

        # Somewhat arbitrary vstar_min in this case
        vstar_min = 0.25

        # Estimate threshold of each device TODO can this be more generalized?
        n_in = in_type=='n'

        vtest_in = vdd/2 if n_in else -vdd/2
        vtest_tail = vdd/2 if n_in else -vdd/2
        vtest_load = -vdd/2 if n_in else vdd/2
        vtest_flip = vdd/2 if n_in else -vdd/2

        vb_in = 0 if n_in else vdd
        vb_tail = 0 if n_in else vdd
        vb_load = vdd if n_in else 0
        vb_flip = 0 if n_in else vdd

        vth_in = estimate_vth(is_nch=n_in, vgs=vtest_in, vbs=0, db=db_dict['in'])
        vth_load = estimate_vth(is_nch=(not n_in), vgs=vtest_load, vbs=0, db=db_dict['load'])
        vth_tail = estimate_vth(is_nch=n_in, vgs=vtest_tail, vbs=0, db=db_dict['tail'])
        vth_flip = estimate_vth(is_nch=n_in, vgs=vtest_flip, vbs=0, db=db_dict['flip'])

        # Keeping track of operating points which work for future comparison
        viable_op_list = []

        # Sweep tail voltage
        vtail_min = vstar_min if n_in else vincm-vth_in
        vtail_max = vincm-vth_in if n_in else vdd-vstar_min
        vtail_vec = np.arange(vtail_min, vtail_max, 10e-3)
        print(f'Sweeping tail from {vtail_min} to {vtail_max}')
        for vtail in vtail_vec:
            # Sweep out1 common mode
            vout1_min = vincm-vth_in if n_in else vstar_min+vth_load
            vout1_max = vdd+vth_load-vstar_min if n_in else vincm-vth_in
            vout1_vec = np.arange(vout1_min, vout1_max, 10e-3)
            for vout1 in vout1_vec:
                in_op = db_dict['in'].query(vgs=vincm-vtail,
                                            vds=vout1-vtail,
                                            vbs=vb_in-vtail)
                load_op = db_dict['load'].query(vgs=vout1-vb_load,
                                                vds=vout1-vb_load,
                                                vbs=0)
                itail_min = 2*in_op['ibias']

                # Sweep output bias
                vout_min = vstar_min+vswing_low if n_in else vout1-vth_load+vswing_low
                vout_max = vout1-vth_load-vswing_high if n_in else vdd-vstar_min-vswing_high
                vout_vec = np.arange(vout_min, vout_max, 10e-3)
                for vout in vout_vec:
                    load_copy_op = db_dict['load'].query(vgs=vout1-vb_load,
                                                         vds=vout-vb_load,
                                                         vbs=0)
                    flip_op = db_dict['flip'].query(vgs=vout-vb_flip,
                                                    vds=vout-vb_flip,
                                                    vbs=0)
                    nf_in_max = int(round(ibias_max/itail_min))
                    nf_in_vec = np.arange(1, nf_in_max, 1)
                    # Step input device size (integer steps)
                    for nf_in in nf_in_vec:
                        itail = itail_min * nf_in

                        # Match device sizing for input and load
                        match_load, nf_load = verify_ratio(in_op['ibias'],
                                                           load_op['ibias'],
                                                           nf_in,
                                                           0.1)

                        if not match_load:
                            continue

                        # Design tail to current match
                        vgtail_min = vth_tail + vstar_min if n_in else vtail + vth_tail
                        vgtail_max = vtail + vth_tail if n_in else vdd + vth_tail - vstar_min
                        vgtail_vec = np.arange(vgtail_min, vgtail_max, 10e-3)
                        for vgtail in vgtail_vec:
                            tail_op = db_dict['tail'].query(vgs=vgtail-vb_tail,
                                                            vds=vtail-vb_tail,
                                                            vbs=0)
                            tail_success, nf_tail = verify_ratio(in_op['ibias']*2,
                                                                 tail_op['ibias'],
                                                                 nf_in,
                                                                 0.1)
                            if not tail_success:
                                continue

                            # raise ValueError("Pause")

                            # Step flip device size (integer steps)
                            ibias_left = ibias_max - itail
                            nf_flip_max = int(round(ibias_left/(2*flip_op['ibias'])))
                            nf_flip_vec = np.arange(1, nf_flip_max, 1)
                            for nf_flip in nf_flip_vec:
                                iflip = flip_op['ibias']*2 * nf_flip

                                # Match load copy device
                                match_load_copy, nf_load_copy = verify_ratio(flip_op['ibias'],
                                                                             load_op['ibias'],
                                                                             nf_flip,
                                                                             0.1)
                                if not match_load_copy:
                                    continue

                                # Check gain, bandwidth
                                ckt_p = LTICircuit()
                                ckt_p.add_transistor(tail_op, 'vtail', 'gnd', 'gnd', fg=nf_tail, neg_cap=False)
                                ckt_p.add_transistor(in_op, 'out1x', 'gnd', 'vtail', fg=nf_in, neg_cap=False)
                                ckt_p.add_transistor(in_op, 'out1', 'inp', 'vtail', fg=nf_in, neg_cap=False)
                                ckt_p.add_transistor(load_op, 'out1x', 'out1x', 'gnd', fg=nf_load, neg_cap=False)
                                ckt_p.add_transistor(load_op, 'out1', 'out1', 'gnd', fg=nf_load, neg_cap=False)
                                ckt_p.add_transistor(load_copy_op, 'outx', 'out1x', 'gnd', fg=nf_load_copy, neg_cap=False)
                                ckt_p.add_transistor(load_copy_op, 'out', 'out1', 'gnd', fg=nf_load_copy, neg_cap=False)
                                ckt_p.add_transistor(flip_op, 'outx', 'outx', 'gnd', fg=nf_flip, neg_cap=False)
                                ckt_p.add_transistor(flip_op, 'out', 'outx', 'gnd', fg=nf_flip, neg_cap=False)
                                ckt_p.add_cap(cload, 'out', 'gnd')

                                p_num, p_den = ckt_p.get_num_den(in_name='inp', out_name='out', in_type='v')

                                ckt_n = LTICircuit()
                                ckt_n.add_transistor(tail_op, 'vtail', 'gnd', 'gnd', fg=nf_tail, neg_cap=False)
                                ckt_n.add_transistor(in_op, 'out1x', 'inn', 'vtail', fg=nf_in, neg_cap=False)
                                ckt_n.add_transistor(in_op, 'out1', 'gnd', 'vtail', fg=nf_in, neg_cap=False)
                                ckt_n.add_transistor(load_op, 'out1x', 'out1x', 'gnd', fg=nf_load, neg_cap=False)
                                ckt_n.add_transistor(load_op, 'out1', 'out1', 'gnd', fg=nf_load, neg_cap=False)
                                ckt_n.add_transistor(load_copy_op, 'outx', 'out1x', 'gnd', fg=nf_load_copy, neg_cap=False)
                                ckt_n.add_transistor(load_copy_op, 'out', 'out1', 'gnd', fg=nf_load_copy, neg_cap=False)
                                ckt_n.add_transistor(flip_op, 'outx', 'outx', 'gnd', fg=nf_flip, neg_cap=False)
                                ckt_n.add_transistor(flip_op, 'out', 'outx', 'gnd', fg=nf_flip, neg_cap=False)
                                ckt_n.add_cap(cload, 'out', 'gnd')

                                n_num, n_den = ckt_n.get_num_den(in_name='inn', out_name='out', in_type='v')

                                num, den = num_den_add(p_num, np.convolve(n_num, [-1]),
                                                       p_den, n_den)

                                num = np.convolve(num, [0.5])

                                gain = num[-1]/den[-1]
                                wbw = get_w_3db(num, den)

                                if wbw == None:
                                    wbw = 0
                                fbw = wbw/(2*np.pi)
                                
                                if fbw < fbw_min:
                                    continue
                                if gain < gain_min:
                                    break

                                viable_op = dict(nf_in=nf_in,
                                                 nf_tail=nf_tail,
                                                 nf_load=nf_load,
                                                 nf_load_copy=nf_load_copy,
                                                 nf_flip=nf_flip,
                                                 vout=vout,
                                                 vout1=vout1,
                                                 gain=gain,
                                                 fbw=fbw,
                                                 vtail=vtail,
                                                 vgtail=vgtail,
                                                 itail=tail_op['ibias']*nf_tail,
                                                 iflip=flip_op['ibias']*nf_flip*2,
                                                 ibias=tail_op['ibias']*nf_tail + 2*nf_flip*flip_op['ibias'])

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
                               th_dict=th_dict)

        load_params = dict(device_params=dict(w=db_dict['load'].width_list[0],
                                                  l=l_dict['load'],
                                                  intent=th_dict['load']),
                                seg_in=best_op['nf_load'],
                                seg_out_list=[best_op['nf_load_copy']])

        flip_params = dict(device_params=dict(w=db_dict['flip'].width_list[0],
                                              l=l_dict['flip'],
                                              intent=th_dict['flip']),
                           seg_in=best_op['nf_flip'],
                           seg_out_list=[best_op['nf_flip']])

        mirr_params_dict = dict(load_out=load_params,
                                load=load_params,
                                flip_out=flip_params)

        sch_params = dict(diffpair_params=diffpair_params,
                          mirr_params_dict=mirr_params_dict,
                          in_type=in_type)

        print(f"(RESULT) {sch_params}\n{best_op}")

        return sch_params, best_op

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1