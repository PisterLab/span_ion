# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

import os
import pkg_resources
import numpy as np
import warnings
from pprint import pprint

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins

# noinspection PyPep8Naming
class bag2_analog__amp_single_sf_dsn(DesignModule):
    """Module for library bag2_analog cell amp_single for 
    a basic 3-transistor souce follower

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
            specfile_dict = 'Transistor database spec file names for each device (for stacks, list)',
            l_dict = 'Transistor channel length dictionary (for stacks, list)',
            th_dict = 'Transistor flavor dictionary (for stacks, list)',
            sim_env = 'Simulation environment',
            vswing_lim = 'Tuple of lower and upper swing from the bias',
            gain_lim = '(Min, max) small signal gain target in V/V',
            fbw = 'Minimum bandwidth in Hz',
            vdd = 'Supply voltage in volts.',
            vincm = 'Input bias mode voltage.',
            ibias = 'Maximum bias current, in amperes.',
            cload = 'Output load capacitance in farads.',
            in_conn = 'Which gate to connect to (e.g. GP<0>, GN<1>, etc.)',
            optional_params = 'Optional parameters. voutcm=output bias voltage.',
        ))
        return ans

    def meet_spec(self, **params) -> List[Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.
        Returns collection of all possible solutions.
        Raises a ValueError if there is no solution.
        """
        optional_params = params['optional_params']
        
        # Somewhat arbitrary vstar_min in this case
        vstar_min = 0.2

        ### Get DBs for each device
        specfile_dict = params['specfile_dict']
        l_dict = params['l_dict']
        th_dict = params['th_dict']
        sim_env = params['sim_env']

        n_stack = len(specfile_dict['n'])
        p_stack = len(specfile_dict['p'])
        
        db_n_list = [get_mos_db(spec_file=specfile_dict['n'][i],
                                intent=th_dict['n'][i],
                                sim_env=sim_env) for i in range(len(specfile_dict['n']))]
        db_p_list = [get_mos_db(spec_file=specfile_dict['p'][i],
                                intent=th_dict['p'][i],
                                sim_env=sim_env) for i in range(len(specfile_dict['p']))]
        db_dict = dict(n=db_n_list, p=db_p_list)
        w_dict = dict(n=[db.width_list[0] for db in db_n_list],
                      p=[db.width_list[0] for db in db_p_list])

        ### Design devices
        vswing_low, vswing_high = params['vswing_lim']
        gain_min, gain_max = params['gain_lim']
        fbw_min = params['fbw']
        vdd = params['vdd']
        vincm = params['vincm']
        ibias_max = params['ibias']
        cload = params['cload']

        # Figuring out the input connection
        in_conn = params['in_conn']
        assert '<0>' not in in_conn, f"Input connection {in_conn} shouldn't be at the outermost device"
        
        gp_conn = [f'GP<{i}>' for i in range(p_stack)]
        gn_conn = [f'GN<{i}>' for i in range(n_stack)]
        assert in_conn in gp_conn + gn_conn, f'in_conn {in_conn} is not a valid gate connection (must be GN or GP<number>)' 
        
        in_side = 'n' if 'GN' in in_conn else 'p'
        opp_side = 'p' if in_side=='n' else 'n'
        opp_stack = p_stack if opp_side=='p' else n_stack
        n_in = in_side == 'n'
        if in_side == 'n':
            assert n_stack == 2, 'Currently only supports source follower with no more than 3 devices'
            assert p_stack < 2, 'Currently only supports source follower with no more than 3 devices'
        else:
            assert p_stack == 2, 'Currently only supports source follower with no more than 3 devices'
            assert n_stack < 2, 'Currently only supports source follower with no more than 3 devices'

        # Keeping track of swept bias voltages by sticking them in a dictionary
        vtest_in = vdd/2 if n_in else -vdd/2
        vtest_p = -vdd/2
        vtest_n = vdd/2

        vb_in = 0 if n_in else vdd
        vb_same = 0 if n_in else vdd
        vb_opp = vdd if n_in else 0

        vth_in = estimate_vth(is_nch=n_in, vgs=vtest_in,
                              vbs=0, db=db_dict[in_side][1],
                              lch=l_dict[in_side][1])

        if p_stack > 0:
            vth_p = estimate_vth(is_nch=False, vgs=-vdd/2,
                                 vbs=0, db=db_dict['p'][0],
                                 lch=l_dict['p'][0])
        if n_stack > 0:
            vth_n = estimate_vth(is_nch=True, vgs=vdd/2,
                                 vbs=0, db=db_dict['n'][0],
                                 lch=l_dict['n'][0])

        # Keep track of viable operating points
        viable_op_list = []

        voutcm_min = vstar_min if n_in else vincm-vth_in+vswing_low
        voutcm_max = vincm-vth_in-vswing_high if n_in else vdd-vstar_min
        voutcm_opt = optional_params.get('voutcm', None)

        if not bool(voutcm_opt):
            voutcm_vec = np.arange(voutcm_min, voutcm_max, 10e-3)
        else:
            if (voutcm_opt < voutcm_min) or (voutcm_opt > voutcm_max):
                warnings.warn(f"voutcm_opt {voutcm_opt} doesn't fall into [{voutcm_min}, {voutcm_max}]")
            voutcm_vec = [voutcm_opt]
        
        # Sweep output bias voltage
        for voutcm in voutcm_vec:
            # Sweep gate voltage of device touching the source of the input device
            vg_same_min = vth_n+vstar_min if n_in else voutcm+vth_p
            vg_same_max = voutcm+vth_n if n_in else vdd+vth_p-vstar_min
            vg_same_vec = np.arange(vg_same_min, vg_same_max, 10e-3)

            for vg_same in vg_same_vec:
                # Operating point of device touching the input device's source
                op_same = db_dict[in_side][0].query(vgs=vg_same-vb_same, vds=voutcm-vb_same, vbs=0)

                # Sweep drain of input device (unless it's shorted to a rail)
                if opp_stack > 0:
                    vd_in_min = vincm-vth_in if n_in else vstar_min
                    vd_in_max = vdd-vstar_min if n_in else vincm-vth_in
                    vd_in_vec = np.arange(vd_in_min, vd_in_max, 10e-3)
                else:
                    vd_in_vec = [vb_opp]

                for vd_in in vd_in_vec:
                    # Operating point of input device
                    op_in = db_dict[in_side][1].query(vgs=vincm-voutcm, vds=vd_in-voutcm, vbs=vb_in-voutcm)

                    # Sweep gate of device touching the drain of the input device
                    if opp_stack > 0:
                        vg_opp_min = vd_in+vth_p if n_in else vth_n+vstar_min
                        vg_opp_max = vdd+vth_p-vstar_min if n_in else vd_in+vth_n
                        vg_opp_vec = np.arange(vg_opp_min, vg_opp_max, 10e-3)
                    else:
                        vg_opp_vec = [vb_opp]

                    for vg_opp in vg_opp_vec:
                        # Calculate the max number of devices to meet current spec
                        nf_same_max = int(round(ibias_max/op_same['ibias']))
                        nf_same_vec = np.arange(2, nf_same_max, 2)
                        for nf_same in nf_same_vec:
                            # Match input device size
                            match_in, nf_in = verify_ratio(op_same['ibias'],
                                                           op_in['ibias'],
                                                           nf_same, 0.01)
                            if not match_in:
                                continue

                            if opp_stack > 0:
                                # Operating point of device touching the input device's drain
                                op_opp = db_dict[opp_side][0].query(vgs=vg_opp-vb_opp, vds=vd_in-vb_opp, vbs=0)
                                # Match opposite device size
                                match_opp, nf_opp = verify_ratio(op_same['ibias'],
                                                                 op_opp['ibias'],
                                                                 nf_same, 0.01)
                                if not match_opp:
                                    continue
                            else:
                                op_opp = None
                                nf_opp = 0

                            # Check LTICircuit
                            op_dict = {'in' : op_in,
                                       'same' : op_same,
                                       'opp' : op_opp}
                            nf_dict = {'in' : nf_in,
                                       'same' : nf_same,
                                       'opp' : nf_opp}

                            gain_lti, fbw_lti = self._get_ss_lti(op_dict=op_dict,
                                                                 nf_dict=nf_dict,
                                                                 cload=cload)

                            if gain_lti < gain_min or gain_lti > gain_max:
                                # print(f'gain {gain_lti}')
                                break

                            if fbw_lti < fbw_min:
                                # print(f'fbw {fbw_lti}')
                                continue

                            viable_op = dict(vout=voutcm,
                                             vin=vincm,
                                             vd=vd_in,
                                             ibias=op_in['ibias']*nf_in,
                                             gain=gain_lti,
                                             fbw=fbw_lti,
                                             nf_dict=nf_dict)
                            if n_in:
                                viable_op['vgn'] = vg_same
                                if opp_stack > 0:
                                    viable_op['vgp'] = vg_opp
                            else:
                                viable_op['vgp'] = vg_same
                                if opp_stack > 0:
                                    viable_op['vgp'] = vg_opp
                                             
                            print('(SUCCESS)')
                            pprint(viable_op)
                            viable_op_list.append(viable_op)

        # Used for getting schematic parameters
        self.other_params = dict(in_conn=in_conn,
                                 w_dict=w_dict,
                                 l_dict=l_dict,
                                 th_dict=th_dict)

        return viable_op_list

    def _get_ss_lti(self, op_dict:Mapping[str,Any], nf_dict:Mapping[str,int], cload:float):
        '''
        Inputs:
            op_dict: Dictionary of queried database operating points.
            nf_dict: Dictionary of number of fingers for devices.
            cload: Load capacitance in farads.
        Return:
            gain: Gain from the input to output in V/V
            fbw: 3dB bandwidth in Hz
        '''
        in_d = 'd' if nf_dict['opp'] > 0 else 'gnd'

        ckt = LTICircuit()
        ckt.add_cap(cload, 'out', 'gnd')
        ckt.add_transistor(op_dict['in'], in_d, 'in', 'out', fg=nf_dict['in'], neg_cap=False)
        ckt.add_transistor(op_dict['same'], 'out', 'gnd', 'gnd', fg=nf_dict['same'], neg_cap=False)
        if nf_dict['opp'] > 0:
            ckt.add_transistor(op_dict['opp'], 'd', 'gnd', 'gnd', fg=nf_dict['opp'], neg_cap=False)

        num, den = ckt.get_num_den(in_name='in', out_name='out', in_type='v')
        gain = num[-1]/den[-1]
        wbw = get_w_3db(num, den)
        if wbw == None:
            wbw = 0
        fbw = wbw/(2*np.pi)

        return gain, fbw


    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1

    def get_sch_params(self, op):
        '''
        '''
        nf_dict = op['nf_dict']
        l_dict = self.other_params['l_dict']
        w_dict = self.other_params['w_dict']
        th_dict = self.other_params['th_dict']
        in_conn = self.other_params['in_conn']

        in_side = 'n' if 'GN' in in_conn else 'p'
        n_in = in_side == 'n'

        stack_p = 1 if n_in else 2
        stack_n = 2 if n_in else 1
        seg_p_list = [nf_dict['opp']] if n_in else [nf_dict['same'], nf_dict['in']]
        seg_n_list = [nf_dict['same'], nf_dict['in']] if n_in else [nf_dict['opp']]

        p_params = dict(stack=stack_p,
                        lch_list=l_dict['p'],
                        w_list=w_dict['p'],
                        intent_list=th_dict['p'],
                        seg_list=seg_p_list)
        n_params = dict(stack=stack_n,
                        lch_list=l_dict['n'],
                        w_list=w_dict['n'],
                        intent_list=th_dict['n'],
                        seg_list=seg_n_list)
        
        out_conn = f'D{in_side.upper()}<0>'

        return dict(p_params=p_params,
                    n_params=n_params,
                    in_conn=in_conn,
                    out_conn=out_conn,
                    inv_out=False,
                    export_mid=True)