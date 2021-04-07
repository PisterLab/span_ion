# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

import os
import pkg_resources
import numpy as np
import warnings

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins, get_w_crossings

# noinspection PyPep8Naming
class span_ion__comparator_fd_cmfb2_dsn(DesignModule):
    """Module for library span_ion cell comparator_fd_cmfb2.

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
            in_type = 'Input pair type',
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
            cload = 'Output load capacitance in farads.',
            optional_params = 'vstar_min, res_vstep, error_tol, vout1'
        ))
        return ans

    def meet_spec(self, **params) -> List[Mapping[str,Any]]:
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
                                lch=l_dict[k],
                                sim_env=sim_env) for k in specfile_dict.keys()}

        ### Design devices
        in_type = params['in_type']
        vdd = params['vdd']
        vincm = params['vincm']
        voutcm = params['voutcm']
        cload = params['cload']
        gain_min = params['gain']
        fbw_min = params['fbw']
        ugf_min = params['ugf']
        ibias_max = params['ibias']

        # Somewhat arbitrary vstar_min in this case
        optional_params = params['optional_params']
        vstar_min = optional_params.get('vstar_min', 0.2)
        res_vstep = optional_params.get('res_vstep', 10e-3)
        error_tol = optional_params.get('error_tol', 0.01)
        vout1_opt = optional_params.get('vout1', None)

        n_in = in_type == 'n'
        vtest_in = vdd/2 if n_in else -vdd/2
        vtest_tail = vdd/2 if n_in else -vdd/2
        vtest_out = -vdd/2 if n_in else vdd/2

        vb_in = 0 if n_in else vdd
        vb_tail = 0 if n_in else vdd
        vb_load = vdd if n_in else 0
        vb_out = 0 if n_in else vdd

        # Estimate threshold of each device TODO can this be more generalized?
        vth_in = estimate_vth(is_nch=n_in, vgs=vtest_in, vbs=0, db=db_dict['in'], lch=l_dict['in'])
        vth_tail = estimate_vth(is_nch=n_in, vgs=vtest_tail, vbs=0, db=db_dict['tail'], lch=l_dict['tail'])
        vth_load = estimate_vth(is_nch=(not n_in), vgs=vtest_out, vbs=0, db=db_dict['load'], lch=l_dict['load'])
        vth_out = estimate_vth(is_nch=n_in, vgs=vtest_in, vbs=0, db=db_dict['out'], lch=l_dict['out'])

        # Keeping track of operating points which work for future comparison
        viable_op_list = []

        # Get tail voltage range
        vtail_min = vstar_min if n_in else vincm-vth_in
        vtail_max = vincm-vth_in if n_in else vdd-vstar_min
        vtail_vec = np.arange(vtail_min, vtail_max, res_vstep)
        print(f'Sweeping tail from {vtail_min} to {vtail_max}')

        # Get out1 common mode range
        vout1_min = vincm-vth_in if n_in else vth_load+vstar_min
        vout1_max = vdd+vth_load-vstar_min if n_in else vincm-vth_in
        if vout1_opt == None:
            vout1_vec = np.arange(vout1_min, vout1_max, res_vstep)
        else:
            vout1_vec = [vout1_opt]
            if vout1_opt < vout1_min or vout1_opt > vout1_max:
                warnings.warn(f'vout11 {vout1_opt} falls outside recommended range ({vout1_min}, {vout1_max})')

        # Sweep tail voltage
        for vtail in vtail_vec:
            # Sweep out1 common mode
            for vout1 in vout1_vec:
                in_op = db_dict['in'].query(vgs=vincm-vtail,
                                            vds=vout1-vtail,
                                            vbs=vb_in-vtail)
                load_op = db_dict['load'].query(vgs=vout1-vb_load,
                                                vds=vout1-vb_load,
                                                vbs=0)
                load_copy_op = db_dict['load'].query(vgs=vout1-vb_load,
                                                     vds=voutcm-vb_load,
                                                     vbs=0)
                out_op = db_dict['out'].query(vgs=voutcm-vb_out,
                                              vds=voutcm-vb_out,
                                              vbs=0)

                itail_min = 4*in_op['ibias']

                # Step input device size (integer steps)
                nf_in_max = int(round(ibias_max/itail_min))
                nf_in_vec = np.arange(1, nf_in_max, 1)
                # if len(nf_in_vec) > 0:
                #     print(f'Number of input devices {min(nf_in_vec)} to {max(nf_in_vec)}')

                for nf_in in nf_in_vec:
                    itail = itail_min * nf_in

                    # Match load device size
                    load_match, nf_load = verify_ratio(in_op['ibias']*2,
                                                       load_op['ibias'],
                                                       nf_in,
                                                       error_tol)

                    if not load_match:
                        print(f"load match {nf_load}")
                        # assert False, 'blep'
                        continue

                    iflip_max = (ibias_max - itail)/2
                    nf_out_max = int(round(iflip_max/out_op['ibias']))
                    nf_out_vec = [1] if nf_out_max == 1 else np.arange(1, nf_out_max, 1)
                    # if len(nf_out_vec) > 0:
                    #     print(f'Number of output devices {min(nf_out_vec)} to {max(nf_out_vec)}')

                    # Step output device size
                    for nf_out in nf_out_vec:
                        iflip_branch = out_op['ibias']*nf_out
                        # Match load copy device size
                        load_copy_match, nf_load_copy = verify_ratio(out_op['ibias'],
                                                                     load_copy_op['ibias'],
                                                                     nf_out,
                                                                     error_tol)
                        if not load_copy_match:
                            print('load copy match')
                            continue

                        # Check target specs
                        ckt_half = LTICircuit()
                        ckt_half.add_transistor(in_op, 'out', 'in', 'gnd', fg=nf_in*2, neg_cap=False)
                        ckt_half.add_transistor(load_op, 'out1', 'out1', 'gnd', fg=nf_load, neg_cap=False)
                        ckt_half.add_transistor(load_copy_op, 'out', 'out1', 'gnd', fg=nf_load_copy, neg_cap=False)
                        ckt_half.add_transistor(out_op, 'out', 'out', 'gnd', fg=nf_out, neg_cap=False)
                        ckt_half.add_cap(cload, 'out', 'gnd')

                        num, den = ckt_half.get_num_den(in_name='in', out_name='out', in_type='v')
                        # num = np.convolve(num, [-1]) # To get positive gain

                        wbw = get_w_3db(num, den)
                        if wbw == None:
                            wbw = 0
                        fbw = wbw/(2*np.pi)

                        # wu, _ = get_w_crossings(num, den)
                        # if wu == None:
                        #     wu = 0
                        # ugf = wu/(2*np.pi)

                        # Rout = parallel(1/(nf_in*2*in_op['gds']), 
                        #                 1/(nf_out*out_op['gm']),
                        #                 1/(nf_out*out_op['gds']))
                        # Gm = in_op['gm']*nf_in*2
                        # gain = Gm * Rout
                        # Cout = cload + (nf_in*2*in_op['cgs']) + (1+gain)*(nf_in*2*in_op['cds'])
                        # fbw = 1/(2*np.pi*Rout*Cout)
                        # ugf = Gm / Cout * (1/2*np.pi)
                        gain = -num[-1]/den[-1]
                        ugf = fbw * gain
                        if fbw < fbw_min:
                            print(f"fbw {fbw}")
                            continue

                        if ugf < ugf_min:
                            print(f"ugf {ugf}")
                            break

                        if gain < gain_min:
                            print(f'gain {gain}')
                            break

                        # Design matching tail
                        vgtail_min = vth_tail+vstar_min if n_in else vtail+vth_tail
                        vgtail_max = vtail+vth_tail if n_in else vdd+vth_tail-vstar_min
                        vgtail_vec = np.arange(vgtail_min, vgtail_max, res_vstep)
                        print(f"Tail gate from {vgtail_min} to {vgtail_max}")
                        for vgtail in vgtail_vec:
                            tail_op = db_dict['tail'].query(vgs=vgtail-vb_tail,
                                                            vds=vtail-vb_tail,
                                                            vbs=0)
                            tail_match, nf_tail = verify_ratio(in_op['ibias']*4,
                                                               tail_op['ibias'],
                                                               nf_in,
                                                               error_tol)

                            if not tail_match:
                                print("tail match")
                                continue

                            print('(SUCCESS)')
                            viable_op = dict(nf_in=nf_in,
                                             nf_load=nf_load,
                                             nf_load_copy=nf_load_copy,
                                             nf_out=nf_out,
                                             nf_tail=nf_tail,
                                             vgtail=vgtail,
                                             gain=gain,
                                             fbw=fbw,
                                             ugf=ugf,
                                             vtail=vtail,
                                             vout1=vout1,
                                             itail=itail,
                                             iflip_branch=nf_out*out_op['ibias'],
                                             ibias=itail+2*nf_out*out_op['ibias'])
                            print(viable_op)
                            viable_op_list.append(viable_op)
        self.other_params = dict(in_type=in_type,
                                 lch_dict=l_dict,
                                 w_dict={k:db.width_list[0] for k,db in db_dict.items()},
                                 th_dict=th_dict)
        return viable_op_list

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1

    def get_sch_params(self, op):
        l_dict = self.other_params['lch_dict']
        w_dict = self.other_params['w_dict']
        seg_dict = {'in': op['nf_in'],
                     'load': op['nf_load'],
                     'load_copy': op['nf_load_copy'],
                     'tail': op['nf_tail'],
                     'out': op['nf_out']}

        for k, v in l_dict.items():
            l_dict[k] = float(v)

        for k, v in w_dict.items():
            w_dict[k] = float(v)

        for k, v in seg_dict.items():
            seg_dict[k] = int(v)

        return dict(in_type=self.other_params['in_type'],
                    lch_dict=l_dict,
                    wch_dict=w_dict,
                    th_dict=self.other_params['th_dict'],
                    seg_dict=seg_dict)