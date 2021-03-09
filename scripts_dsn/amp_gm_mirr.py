# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any

import os
import pkg_resources
import numpy as np
from pprint import pprint
from math import floor

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins, get_w_crossings

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
            ugf = '',
            pm = '',
            vdd = 'Supply voltage in volts.',
            vincm = 'Input common mode voltage.',
            ibias = 'Maximum bias current, in amperes.',
            cload = 'Output load capacitance in farads.',
            optional_params = 'Optional parameters. voutcm=output bias voltage, error_tol, \
                res_vstep, vstar_min'
        ))
        return ans

    def meet_spec(self, **params) -> Tuple[Mapping[str,Any],Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.

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
        vdd = params['vdd']
        vincm = params['vincm']
        vswing_low, vswing_high = params['vswing_lim']
        cload = params['cload']
        gain_min = params['gain']
        fbw_min = params['fbw']
        ugf_min = params['ugf']
        pm_min = params['pm']
        ibias_max = params['ibias']

        vstar_min = optional_params.get('vstar_min', 0.2)
        vstar_in_min = optional_params.get('vstar_in_min', 0.0)
        vout_opt = optional_params.get('voutcm', None)
        error_tol = optional_params.get('error_tol', 0.1)
        res_vstep = optional_params.get('res_vstep', 10e-3)

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

        vth_in = estimate_vth(is_nch=n_in, vgs=vtest_in, vbs=0, db=db_dict['in'], lch=l_dict['in'])
        vth_load = estimate_vth(is_nch=(not n_in), vgs=vtest_load, vbs=0, db=db_dict['load'], lch=l_dict['load'])
        vth_tail = estimate_vth(is_nch=n_in, vgs=vtest_tail, vbs=0, db=db_dict['tail'], lch=l_dict['tail'])
        vth_flip = estimate_vth(is_nch=n_in, vgs=vtest_flip, vbs=0, db=db_dict['flip'], lch=l_dict['flip'])

        # Keeping track of operating points which work for future comparison
        viable_op_list = []

        ### 1. Sweep tail voltage
        vtail_min = vstar_min if n_in else vincm-vth_in+vstar_in_min
        vtail_max = vincm-vth_in-vstar_in_min if n_in else vdd-vstar_min
        vtail_vec = np.arange(vtail_min, vtail_max, res_vstep)
        for vtail in vtail_vec:
            ### 2. Sweep out1 common mode
            vout1_min = vincm-vth_in if n_in else vstar_min+vth_load
            vout1_max = vdd+vth_load-vstar_min if n_in else vincm-vth_in
            vout1_vec = np.arange(vout1_min, vout1_max, res_vstep)
            for vout1 in vout1_vec:
                in_op = db_dict['in'].query(vgs=vincm-vtail,
                                            vds=vout1-vtail,
                                            vbs=vb_in-vtail)
                load_op = db_dict['load'].query(vgs=vout1-vb_load,
                                                vds=vout1-vb_load,
                                                vbs=0)

                ### 3. Sweep output bias
                vout_min = vth_flip+vstar_min+vswing_low if n_in else vout1-vth_load+vswing_low
                vout_max = vout1-vth_load-vswing_high if n_in else vdd+vth_flip-vstar_min-vswing_high
                if vout_opt == None:
                    vout_vec = np.arange(vout_min, vout_max, res_vstep)
                else:
                    vout_vec = [vout_opt]

                for vout in vout_vec:
                    load_copy_op = db_dict['load'].query(vgs=vout1-vb_load,
                                                         vds=vout-vb_load,
                                                         vbs=0)
                    flip_op = db_dict['flip'].query(vgs=vout-vb_flip,
                                                    vds=vout-vb_flip,
                                                    vbs=0)
                    nf_in_max = int(floor(ibias_max/in_op['ibias'] * 0.5))
                    nf_in_vec = np.arange(2, nf_in_max, 2)
                    ### 4. Step input device size (integer steps)
                    for nf_in in nf_in_vec:
                        itail = in_op['ibias'] * 2*nf_in

                        # Match device sizing for input and load
                        match_load, nf_load = verify_ratio(in_op['ibias'],
                                                           load_op['ibias'],
                                                           nf_in, error_tol)

                        if not match_load:
                            # print('load match')
                            continue

                        ### 5. Design tail to current match
                        vgtail_min = vth_tail+vstar_min if n_in else vtail+vth_tail
                        vgtail_max = vtail+vth_tail if n_in else vdd+vth_tail-vstar_min
                        vgtail_vec = np.arange(vgtail_min, vgtail_max, 10e-3)
                        for vgtail in vgtail_vec:
                            tail_op = db_dict['tail'].query(vgs=vgtail-vb_tail,
                                                            vds=vtail-vb_tail,
                                                            vbs=0)
                            tail_success, nf_tail = verify_ratio(in_op['ibias']*2,
                                                                 tail_op['ibias'],
                                                                 nf_in, error_tol)
                            if not tail_success:
                                # print('tail match')
                                continue

                            ### 6. Step flip device size (integer steps)
                            ibias_left = ibias_max - itail
                            nf_flip_max = int(floor(ibias_left/flip_op['ibias'] * 0.5))
                            nf_flip_vec = np.arange(2, nf_flip_max, 2)
                            for nf_flip in nf_flip_vec:
                                # Match load copy device
                                match_load_copy, nf_load_copy = verify_ratio(flip_op['ibias'],
                                                                             load_copy_op['ibias'],
                                                                             nf_flip, error_tol)
                                if not match_load_copy:
                                    # print('load copy match')
                                    continue

                                op_dict = {'in' : in_op,
                                           'tail' : tail_op,
                                           'load' : load_op,
                                           'load_copy': load_copy_op,
                                           'flip' : flip_op}

                                nf_dict = {'in' : nf_in,
                                           'tail' : nf_tail,
                                           'load' : nf_load,
                                           'load_copy': nf_load_copy,
                                           'flip' : nf_flip}

                                # Calculate figures of merit
                                gain_lti, fbw_lti, ugf_lti, pm_lti = self._get_ss_lti(op_dict=op_dict,
                                                                     nf_dict=nf_dict,
                                                                     cload=cload)

                                if gain_lti < gain_min:
                                    print(f'gain {gain_lti}')
                                    continue
                                        
                                if fbw_lti < fbw_min:
                                    print(f'fbw {fbw_lti}')
                                    continue

                                if ugf_lti < ugf_min:
                                    print(f'ugf {ugf_lti}' )
                                    continue

                                if pm_lti < pm_min:
                                    print(f'pm {pm_lti}')
                                    continue

                                viable_op = dict(nf_dict=nf_dict,
                                                 vout=vout,
                                                 vout1=vout1,
                                                 vincm=vincm,
                                                 gain=gain_lti,
                                                 fbw=fbw_lti,
                                                 ugf=ugf_lti,
                                                 pm=pm_lti,
                                                 vtail=vtail,
                                                 vgtail=vgtail,
                                                 itail=tail_op['ibias']*nf_tail,
                                                 iflip=flip_op['ibias']*nf_flip*2,
                                                 ibias=tail_op['ibias']*nf_tail + 2*nf_flip*flip_op['ibias'],
                                                 cin=in_op['cgg']*nf_in)

                                viable_op_list.append(viable_op)
                                print("\n(SUCCESS)")
                                pprint(viable_op)

        self.other_params = dict(db_dict=db_dict,
                                 l_dict=l_dict,
                                 th_dict=th_dict,
                                 in_type=in_type)

        return viable_op_list

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1

    def _get_ss_lti(self, op_dict:Mapping[str,Any], 
                    nf_dict:Mapping[str,int], 
                    cload:float) -> Tuple[float,float]:
        ckt_p = self.make_ltickt(op_dict=op_dict, nf_dict=nf_dict, cload=cload, meas_side='p')
        p_num, p_den = ckt_p.get_num_den(in_name='inp', out_name='out', in_type='v')

        ckt_n = self.make_ltickt(op_dict=op_dict, nf_dict=nf_dict, cload=cload, meas_side='n')
        n_num, n_den = ckt_n.get_num_den(in_name='inn', out_name='out', in_type='v')

        num, den = num_den_add(p_num, np.convolve(n_num, [-1]),
                               p_den, n_den)

        num = np.convolve(num, [0.5])

        gain = num[-1]/den[-1]
        wbw = get_w_3db(num, den)
        pm, _ = get_stability_margins(num, den)
        ugw, _ = get_w_crossings(num, den)

        if wbw == None:
            wbw = 0
        fbw = wbw/(2*np.pi)

        if ugw == None:
            ugw = 0
        ugf = ugw/(2*np.pi)

        return gain, fbw, ugf, pm

    def make_ltickt(self, op_dict:Mapping[str,Any], nf_dict:Mapping[str,int], 
                    cload:float, meas_side:str) -> LTICircuit:

        ckt = LTICircuit()
        inp_conn = 'gnd' if meas_side=='n' else 'inp'
        inn_conn = 'gnd' if meas_side=='p' else 'inn'
        # Tail
        ckt.add_transistor(op_dict['tail'], 'tail', 'gnd', 'gnd', fg=nf_dict['tail'])
        
        # Input
        ckt.add_transistor(op_dict['in'], 'out1x', inn_conn, 'tail', fg=nf_dict['in'])
        ckt.add_transistor(op_dict['in'], 'out1', inp_conn, 'tail', fg=nf_dict['in'])
        
        # Load
        ckt.add_transistor(op_dict['load'], 'out1x', 'out1x', 'gnd', fg=nf_dict['load'])
        ckt.add_transistor(op_dict['load'], 'out1', 'out1', 'gnd', fg=nf_dict['load'])
        
        # Load copy
        ckt.add_transistor(op_dict['load_copy'], 'outx', 'out1x', 'gnd', fg=nf_dict['load_copy'])
        ckt.add_transistor(op_dict['load_copy'], 'out', 'out1', 'gnd', fg=nf_dict['load_copy'])
        
        # Flip devices
        ckt.add_transistor(op_dict['flip'], 'outx', 'outx', 'gnd', fg=nf_dict['flip'])
        ckt.add_transistor(op_dict['flip'], 'out', 'outx', 'gnd', fg=nf_dict['flip'])
        
        # Capacitive load
        ckt.add_cap(cload, 'out', 'gnd')

        return ckt

    def get_sch_params(self, op):
        db_dict = self.other_params['db_dict']
        l_dict = self.other_params['l_dict']
        th_dict = self.other_params['th_dict']
        in_type = self.other_params['in_type']

        return dict(in_type=in_type,
                    l_dict=l_dict,
                    w_dict={k:db.width_list[0] for k,db in db_dict.items()},
                    seg_dict=op['nf_dict'])