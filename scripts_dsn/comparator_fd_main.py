# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

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
            in_type = 'Input pair type',
            th_dict = 'Transistor flavor dictionary.',
            l_dict = 'Transistor channel length dictionary',
            sim_env = 'Simulation environment',
            gain_lim = '(Min, max) small signal gain target in V/V',
            fbw = 'Minimum bandwidth in Hz',
            vdd = 'Supply voltage in volts.',
            vincm = 'Input common mode voltage.',
            ibias = 'Maximum bias current, in amperes.',
            cload = 'Output load capacitance in farads.',
            optional_params = 'Optional parameters. voutcm=outpu common mode, vstar_min, res_vstep, error_tol'
        ))
        return ans

    def meet_spec(self, **params) -> List[Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.

        Raises a ValueError if there is no solution.
        """
        ### Get DBs for each device
        specfile_dict = params['specfile_dict']
        in_type = params['in_type']
        l_dict = params['l_dict']
        th_dict = params['th_dict']
        sim_env = params['sim_env']
        
        # Databases
        db_dict = {k:get_mos_db(spec_file=specfile_dict[k],
                                intent=th_dict[k],
                                lch=l_dict[k],
                                sim_env=sim_env) for k in specfile_dict.keys()}

        ### Design devices
        vdd = params['vdd']
        vincm = params['vincm']
        cload = params['cload']
        gain_min, gain_max = params['gain_lim']
        fbw_min = params['fbw']
        ibias_max = params['ibias']
        optional_params = params['optional_params']

        # Pulling out optional parameters
        vstar_min = optional_params.get('vstar_min', 0.2)
        res_vstep = optional_params.get('res_vstep', 10e-3)
        error_tol = optional_params.get('error_tol', 0.01)

        n_in = in_type=='n'

        # Estimate threshold of each device
        vtest = vdd/2 if n_in else -vdd/2
        vb = 0 if n_in else vdd

        vth_in = estimate_vth(is_nch=n_in, vgs=vtest, vbs=0, db=db_dict['in'], lch=l_dict['in'])
        vth_tail = estimate_vth(is_nch=n_in, vgs=vtest, vbs=0, db=db_dict['tail'], lch=l_dict['tail'])

        # Keeping track of operating points which work for future comparison
        viable_op_list = []

        # Sweep tail voltage
        vtail_min = vstar_min if n_in else vincm-vth_in
        vtail_max = vincm-vth_in if n_in else vdd-vstar_min
        vtail_vec = np.arange(vtail_min, vtail_max, res_vstep)
        print(f'Sweeping tail from {vtail_min} to {vtail_max}')
        for vtail in vtail_vec:
            voutcm_min = vincm-vth_in if n_in else 0
            voutcm_max = vdd if n_in else vincm-vth_in

            voutcm = optional_params.get('voutcm', None)

            if voutcm == None:
                voutcm_vec = np.arange(voutcm_min, voutcm_max, res_vstep)
            else:
                voutcm_vec = [voutcm]
            # Sweep output common mode
            for voutcm in voutcm_vec:
                in_op = db_dict['in'].query(vgs=vincm-vtail,
                                            vds=voutcm-vtail,
                                            vbs=vb-vtail)
                ibias_min = 2*in_op['ibias']
                # Step input device size (integer steps)
                nf_in_max = int(round(ibias_max/ibias_min))
                nf_in_vec = np.arange(2, nf_in_max, 2)
                for nf_in in nf_in_vec:
                    ibias = ibias_min * nf_in
                    ibranch = ibias/2
                    res_val = (vdd-voutcm)/ibranch if n_in else voutcm/ibranch
                    # Check gain, bandwidth
                    ckt_half = LTICircuit()
                    ckt_half.add_transistor(in_op, 'out', 'in', 'gnd', fg=nf_in, neg_cap=False)
                    ckt_half.add_res(res_val, 'out', 'gnd')
                    ckt_half.add_cap(cload, 'out', 'gnd')

                    num, den = ckt_half.get_num_den(in_name='in', out_name='out', in_type='v')
                    gain = -(num[-1]/den[-1])
                    wbw = get_w_3db(num, den)
                    if wbw == None:
                        wbw = 0
                    fbw = wbw/(2*np.pi)

                    if gain < gain_min or gain > gain_max:
                        print(f'gain: {gain}')
                        break

                    if fbw < fbw_min:
                        print(f'fbw: {fbw}')
                        continue

                    # Design tail to current match
                    vgtail_min = vth_tail+vstar_min if n_in else vtail+vth_tail
                    vgtail_max = vtail+vth_tail if n_in else vdd+vth_tail-vstar_min
                    vgtail_vec = np.arange(vgtail_min, vgtail_max, res_vstep)
                    print(f'vgtail {vgtail_min} to {vgtail_max}')
                    for vgtail in vgtail_vec:
                        tail_op = db_dict['tail'].query(vgs=vgtail-vb,
                                                        vds=vtail-vb,
                                                        vbs=0)
                        tail_success, nf_tail = verify_ratio(in_op['ibias']*2,
                                                             tail_op['ibias'],
                                                             nf_in,
                                                             error_tol)
                        if not tail_success:
                            print('tail match')
                            continue
                        
                        viable_op = dict(nf_in=nf_in,
                                         nf_tail=nf_tail,
                                         res_val=res_val,
                                         voutcm=voutcm,
                                         vgtail=vgtail,
                                         gain=gain,
                                         fbw=fbw,
                                         vtail=vtail,
                                         ibias=tail_op['ibias']*nf_tail,
                                         cmfb_cload=tail_op['cgg']*nf_tail)
                        viable_op_list.append(viable_op)
                        print("\n(SUCCESS)")
                        print(viable_op)

        self.other_params = dict(in_type=in_type,
                                 l_dict=l_dict,
                                 w_dict={k:db.width_list[0] for k,db in db_dict.items()},
                                 th_dict=th_dict)

        return viable_op_list

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1

    def get_sch_params(self, op):
        # TODO real resistor
        l_dict = dict(self.other_params['l_dict'])
        l_dict.update(dict(res=1e-6*op['res_val']/600))
        w_dict = dict(self.other_params['w_dict'])
        w_dict.update(dict(res=1e-6))
        seg_dict = {'in' : op['nf_in'],
                  'tail' : op['nf_tail'],
                  'res' : 1} # TODO real resistor

        # Cleaning up data types
        for k, v in l_dict.items():
            l_dict[k] = float(v)

        for k, v in w_dict.items():
            w_dict[k] = float(v)

        for k, v in seg_dict.items():
            seg_dict[k] = int(v)

        return dict(in_type=self.other_params['in_type'],
                    bulk_conn='VSS', # TODO real resistor
                    l_dict=l_dict,
                    w_dict=w_dict,
                    th_dict=self.other_params['th_dict'],
                    seg_dict=seg_dict)