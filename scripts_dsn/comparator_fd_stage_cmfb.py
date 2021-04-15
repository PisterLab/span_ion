# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any

import os
import pkg_resources
import numpy as np

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins, get_w_crossings

from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add, enable_print, disable_print
from .comparator_fd_main import span_ion__comparator_fd_main_dsn
from .comparator_fd_cmfb2 import span_ion__comparator_fd_cmfb2_dsn
from .constant_gm import bag2_analog__constant_gm_dsn

# noinspection PyPep8Naming
class span_ion__comparator_fd_stage_cmfb_dsn(DesignModule):
    """Module for library span_ion cell comparator_fd_stage_cmfb.
    This includes the comparator_fd_main, comparator_fd_cmfb,
    and constant_gm for biasing the common mode feedback amp.

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
            gain_lim = '(Min, max) small signal gain target in V/V',
            fbw = 'Minimum bandwidth in Hz',
            vdd = 'Supply voltage in volts.',
            vincm = 'Input common mode voltage.',
            ibias = 'Maximum bias current, in amperes.',
            cload = 'Output load capacitance in farads.',
            main_dsn_params = '',
            cmfb_dsn_params = '',
            constgm_dsn_params = ''
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
        cload = params['cload']
        gain_min, gain_max = params['gain_lim']
        fbw_min = params['fbw']
        ibias_max = params['ibias']

        n_in = in_type == 'n'

        # Spec out amplifiers and biasing
        main_specfile_dict = dict()
        main_th_dict = dict()
        main_l_dict = dict()
        for k in ('in', 'tail'):
            main_specfile_dict[k] = specfile_dict[f'main_{k}']
            main_th_dict[k] = th_dict[f'main_{k}']
            main_l_dict[k] = l_dict[f'main_{k}']
        main_dsn_params = dict(params['main_dsn_params'])
        main_dsn_params.update(dict(in_type=in_type,
                                    specfile_dict=main_specfile_dict,
                                    th_dict=main_th_dict,
                                    l_dict=main_l_dict,
                                    sim_env=sim_env,
                                    vdd=vdd,
                                    ibias=ibias_max,
                                    vincm=vincm,
                                    cload=cload,
                                    gain_lim=params['gain_lim'],
                                    fbw=fbw_min))

        cmfb_specfile_dict = dict()
        cmfb_th_dict = dict()
        cmfb_l_dict = dict()
        for k in ('in', 'tail', 'load', 'out'):
            cmfb_specfile_dict[k] = specfile_dict[f'cmfb_{k}']
            cmfb_th_dict[k] = th_dict[f'cmfb_{k}']
            cmfb_l_dict[k] = l_dict[f'cmfb_{k}']
        cmfb_dsn_params = dict(params['cmfb_dsn_params'])
        # cmfb_dsn_params.update(dict(in_type='p' if n_in else 'n',
        cmfb_dsn_params.update(dict(in_type=in_type,
                                    specfile_dict=cmfb_specfile_dict,
                                    th_dict=cmfb_th_dict,
                                    l_dict=cmfb_l_dict,
                                    sim_env=sim_env,
                                    vdd=vdd))

        constgm_specfile_dict = dict()
        constgm_th_dict = dict()
        constgm_l_dict = dict()
        for k in ('n', 'p'):
            constgm_specfile_dict[k] = specfile_dict[f'constgm_{k}']
            constgm_th_dict[k] = th_dict[f'constgm_{k}']
            constgm_l_dict[k] = l_dict[f'constgm_{k}']
        constgm_dsn_params = dict(params['constgm_dsn_params'])
        constgm_dsn_params.update(dict(specfile_dict=constgm_specfile_dict,
                                       th_dict=constgm_th_dict,
                                       l_dict=constgm_l_dict,
                                       sim_env=sim_env,
                                       vdd=vdd))

        # Design blocks
        main_dsn_mod = span_ion__comparator_fd_main_dsn()
        cmfb_dsn_mod = span_ion__comparator_fd_cmfb2_dsn()
        constgm_dsn_mod = bag2_analog__constant_gm_dsn()

        self.other_params = dict(in_type=in_type,
                                 main_dsn_mod=main_dsn_mod,
                                 cmfb_dsn_mod=cmfb_dsn_mod,
                                 constgm_dsn_mod=constgm_dsn_mod)

        viable_op_list = []

        # Design the main amplifier with 0 additional load (i.e. ignores load from cmfb amp)
        print('Designing the main amp...')
        try:
            disable_print()
            main_dsn_lst = main_dsn_mod.meet_spec(**main_dsn_params)
        except ValueError:
            print('0 load main amp failure')
        finally:
            enable_print()
        print(f'{len(main_dsn_lst)} viable main amps')

        for main_dsn_info in main_dsn_lst:
            # print(main_dsn_info)

            # Design the cmfb amp
            print('Designing the cmfb amp...')
            cmfb_dsn_params.update(dict(cload=main_dsn_info['cmfb_cload'],
                                        ibias=ibias_max-main_dsn_info['ibias'],
                                        vincm=main_dsn_info['voutcm'],
                                        voutcm=main_dsn_info['vgtail']))
            try:
                disable_print()
                cmfb_dsn_lst = cmfb_dsn_mod.meet_spec(**cmfb_dsn_params)
            except ValueError:
                continue
            finally:
                enable_print()

            print(f'{len(cmfb_dsn_lst)} viable cmfb amps')

            for cmfb_dsn_info in cmfb_dsn_lst:
                # Check the small signal parameters with the real capacitive load
                vtail_main = main_dsn_info['vtail']
                voutcm_main = main_dsn_info['voutcm']
                vgtail_main = main_dsn_info['vgtail']
                vout1_cmfb = cmfb_dsn_info['vout1']

                vb_in = 0 if in_type=='n' else vdd
                vb_load = vdd if in_type == 'n' else 0

                vtail_cmfb = cmfb_dsn_info['vtail']
                voutcm_cmfb = vgtail_main
                vgtail_cmfb = cmfb_dsn_info['vgtail']

                op_dict = dict(main_in = db_dict['main_in'].query(vgs=vincm-vtail_main, 
                                                                    vds=voutcm_main-vtail_main, 
                                                                    vbs=vb_in-vtail_main),
                               main_tail = db_dict['main_tail'].query(vgs=vgtail_main-vb_in,
                                                                        vds=vtail_main-vb_in,
                                                                        vbs=0),
                               cmfb_in = db_dict['cmfb_in'].query(vgs=voutcm_main-vtail_cmfb,
                                                                    vds=vout1_cmfb-vtail_cmfb,
                                                                    vbs=vb_in-vtail_cmfb),
                               cmfb_tail = db_dict['cmfb_tail'].query(vgs=vgtail_cmfb-vb_in,
                                                                        vds=vtail_cmfb-vb_in,
                                                                        vbs=0),
                               cmfb_load = db_dict['cmfb_load'].query(vgs=vout1_cmfb-vb_load,
                                                                      vds=vout1_cmfb-vb_load,
                                                                      vbs=0),
                               cmfb_load_copy = db_dict['cmfb_load'].query(vgs=vout1_cmfb-vb_load,
                                                                           vds=voutcm_cmfb-vb_load,
                                                                           vbs=0),
                               cmfb_out = db_dict['cmfb_out'].query(vgs=voutcm_cmfb-vb_in,
                                                                    vds=voutcm_cmfb-vb_in,
                                                                    vbs=0))

                nf_dict = dict(main_in = main_dsn_info['nf_in'],
                               main_tail = main_dsn_info['nf_tail'],
                               cmfb_in = cmfb_dsn_info['nf_in'],
                               cmfb_load = cmfb_dsn_info['nf_load'],
                               cmfb_load_copy = cmfb_dsn_info['nf_load_copy'],
                               cmfb_tail = cmfb_dsn_info['nf_tail'],
                               cmfb_out = cmfb_dsn_info['nf_out'])
                gain_lti, fbw_lti = self._get_ss_lti(op_dict=op_dict, nf_dict=nf_dict, cload=cload, rload=main_dsn_info['res_val'])

                if gain_lti < gain_min or gain_lti > gain_max:
                    print(f'gain {gain_lti}')
                    continue

                if fbw_lti < fbw_min:
                    print(f'fbw {fbw_lti}')
                    continue

                # Design constant gm
                print("Designing the constant gm...")
                constgm_dsn_params['ibias'] = ibias_max - main_dsn_info['ibias'] - cmfb_dsn_info['ibias']
                if not n_in:
                    constgm_dsn_params.update(dict(res_side='p',
                                                   vref=dict(p=cmfb_dsn_info['vgtail'])))
                else:
                    constgm_dsn_params.update(dict(res_side='n',
                                                   vref=dict(n=cmfb_dsn_info['vgtail'])))

                try:
                    disable_print()
                    _, constgm_dsn_info = constgm_dsn_mod.design(**constgm_dsn_params)
                except ValueError:
                    continue
                finally:
                    enable_print()

                # Keep track of all possibilities
                viable_op = dict(constgm_dsn=constgm_dsn_info.copy(),
                                 main_dsn=main_dsn_info.copy(),
                                 cmfb_dsn=cmfb_dsn_info.copy(),
                                 gain=gain_lti,
                                 fbw=fbw_lti,
                                 ibias=main_dsn_info['ibias']+cmfb_dsn_info['ibias']+constgm_dsn_info['ibias'])

                viable_op_list.append(viable_op)
                print(f'(SUCCESS)\n{viable_op}')

        return viable_op_list


    def _get_ss_lti(self, op_dict:Mapping[str,Any], nf_dict:Mapping[str,int], cload:float, rload:float) -> Tuple[float,float]:
        '''
        Return:
            gain
            fbw
        '''
        ckt_p = self.make_ltickt(op_dict=op_dict, nf_dict=nf_dict, cload=cload, rload=rload, meas_side='p')
        p2p_num, p2p_den = ckt_p.get_num_den(in_name='inp', out_name='main_outp', in_type='v')
        p2n_num, p2n_den = ckt_p.get_num_den(in_name='inp', out_name='main_outn', in_type='v')

        ckt_n = self.make_ltickt(op_dict=op_dict, nf_dict=nf_dict, cload=cload, rload=rload, meas_side='n')
        n2p_num, n2p_den = ckt_n.get_num_den(in_name='inn', out_name='main_outp', in_type='v')
        n2n_num, n2n_den = ckt_n.get_num_den(in_name='inn', out_name='main_outn', in_type='v')

        # Diff gain for p-input and n-input
        p_num, p_den = num_den_add(p2p_num, np.convolve(p2n_num, [-1]),
                                   p2p_den, p2n_den)
        n_num, n_den = num_den_add(n2p_num, np.convolve(n2n_num, [-1]),
                                   n2p_den, n2n_den)

        # Superposition for two inputs
        num, den = num_den_add(p_num, np.convolve(n_num, [-1]),
                               p_den, n_den)
        num = np.convolve(num, [0.5])

        # Calculate FoM using transfer function
        gain = num[-1]/den[-1]
        wbw = get_w_3db(num, den)
        
        if wbw == None:
            wbw = 0
        fbw = wbw / (2*np.pi)

        return gain, fbw

    def make_ltickt(self, op_dict:Mapping[str,Any], nf_dict:Mapping[str,int], cload:float, rload:float, meas_side:str) -> LTICircuit:
        ckt = LTICircuit()
        inp_conn = 'gnd' if meas_side=='n' else 'inp'
        inn_conn = 'gnd' if meas_side=='p' else 'inn'

        ckt.add_transistor(op_dict['main_in'], 'main_outn', inp_conn, 'main_tail', fg=nf_dict['main_in'])
        ckt.add_transistor(op_dict['main_in'], 'main_outp', inn_conn, 'main_tail', fg=nf_dict['main_in'])
        # ckt.add_transistor(op_dict['main_tail'], 'main_tail', 'cmfb_outp', 'gnd', fg=nf_dict['main_tail'])
        ckt.add_transistor(op_dict['main_tail'], 'main_tail', 'gnd', 'gnd', fg=nf_dict['main_tail'])
        ckt.add_res(rload, 'main_outn', 'gnd')
        ckt.add_res(rload, 'main_outp', 'gnd')

        ckt.add_cap(cload, 'main_outn', 'gnd')
        ckt.add_cap(cload, 'main_outp', 'gnd')

        # ckt.add_transistor(op_dict['cmfb_in'], 'cmfb_out1n', 'gnd', 'cmfb_tail', fg=nf_dict['cmfb_in']*2)
        # ckt.add_transistor(op_dict['cmfb_in'], 'cmfb_out1p', 'main_outn', 'cmfb_tail', fg=nf_dict['cmfb_in'])
        # ckt.add_transistor(op_dict['cmfb_in'], 'cmfb_out1p', 'main_outp', 'cmfb_tail', fg=nf_dict['cmfb_in'])
        # ckt.add_transistor(op_dict['cmfb_tail'], 'cmfb_tail', 'gnd', 'gnd', fg=nf_dict['cmfb_tail'])
        # ckt.add_transistor(op_dict['cmfb_load'], 'cmfb_out1n', 'cmfb_out1n', 'gnd', fg=nf_dict['cmfb_load'])
        # ckt.add_transistor(op_dict['cmfb_load'], 'cmfb_out1p', 'cmfb_out1p', 'gnd', fg=nf_dict['cmfb_load'])
        # ckt.add_transistor(op_dict['cmfb_load_copy'], 'cmfb_outp', 'cmfb_out1n', 'gnd', fg=nf_dict['cmfb_load_copy'])
        # ckt.add_transistor(op_dict['cmfb_load_copy'], 'cmfb_outn', 'cmfb_out1p', 'gnd', fg=nf_dict['cmfb_load_copy'])
        # ckt.add_transistor(op_dict['cmfb_out'], 'cmfb_outp', 'cmfb_outp', 'gnd', fg=nf_dict['cmfb_out'])
        # ckt.add_transistor(op_dict['cmfb_out'], 'cmfb_outn', 'cmfb_outn', 'gnd', fg=nf_dict['cmfb_out'])

        # assert False, 'blep'

        # ckt.add_transistor(op_dict['cmfb_in'], 'cmfb_outn', 'gnd', 'cmfb_tail', fg=nf_dict['cmfb_in']*2, neg_cap=False)
        # ckt.add_transistor(op_dict['cmfb_in'], 'cmfb_outp', 'main_outn', 'cmfb_tail', fg=nf_dict['cmfb_in'], neg_cap=False)
        # ckt.add_transistor(op_dict['cmfb_in'], 'cmfb_outp', 'main_outp', 'cmfb_tail', fg=nf_dict['cmfb_in'], neg_cap=False)
        # ckt.add_transistor(op_dict['cmfb_tail'], 'cmfb_tail', 'gnd', 'gnd', fg=nf_dict['cmfb_tail'], neg_cap=False)
        # ckt.add_transistor(op_dict['cmfb_out'], 'cmfb_outn', 'cmfb_outn', 'gnd', fg=nf_dict['cmfb_out'], neg_cap=False)
        # ckt.add_transistor(op_dict['cmfb_out'], 'cmfb_outp', 'cmfb_outp', 'gnd', fg=nf_dict['cmfb_out'], neg_cap=False)

        return ckt

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        if op2['fbw'] > op1['fbw']:
            return op2
        elif op1['fbw'] > op2['fbw']:
            return op1
        else:
            return op2 if op1['ibias'] > op2['ibias'] else op1

    def get_sch_params(self, op):
        return dict(in_type=self.other_params['in_type'],
                    main_params=self.other_params['main_dsn_mod'].get_sch_params(op['main_dsn']),
                    cmfb_params=self.other_params['cmfb_dsn_mod'].get_sch_params(op['cmfb_dsn']),
                    constgm_params=self.other_params['constgm_dsn_mod'].get_sch_params(op['constgm_dsn']))