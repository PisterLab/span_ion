# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_offset(Module):
    """Module for library span_ion cell comparator_fd_offset.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_offset.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str,str]:
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            in_type='"p" or "n" for NMOS or PMOS input pair',
            l_dict='Channel and resistor lengths (in, tail, en, res)',
            w_dict='Channel and resistor widths',
            th_dict='Device and resistor flavors',
            seg_dict='Device and resistor number of devices (in, tail, bias, en_tail, en_bias, res)',
        )

    def design(self, **params):
        """To be overridden by subclasses to design this module.

        This method should fill in values for all parameters in
        self.parameters.  To design instances of this module, you can
        call their design() method or any other ways you coded.

        To modify schematic structure, call:

        rename_pin()
        delete_instance()
        replace_instance_master()
        reconnect_instance_terminal()
        restore_instance()
        array_instance()
        """
        in_type = params['in_type']
        l_dict = params['l_dict']
        w_dict = params['w_dict']
        th_dict = params['th_dict']
        seg_dict = params['seg_dict']

        ### Replace instances with PMOS if necessary
        if in_type == 'p':
            self.replace_instance_master(inst_name='XDIFFPAIR',
                                         lib_name='bag2_analog',
                                         cell_name='diffpair_p')
            change_insts = ['XEN_TAIL', 'XEN_BIAS', 'XBIAS', 'XTAIL']
            for inst in change_insts:
                self.replace_instance_master(inst_name=inst,
                                             lib_name='BAG_prim',
                                             cell_name='pmos4_standard')
            for inst in ('XEN_RESA', 'XEN_RESB'):
                self.replace_instance_master(inst_name=inst,
                                             lib_name='BAG_prim',
                                             cell_name='nmos4_standard')

        ### Design instances
        inst_key_gen = dict(XEN_TAIL='en_tail',
                            XEN_BIAS='en_tail',
                            XTAIL='tail',
                            XBIAS='tail',
                            XEN_RESA='en_res',
                            XEN_RESB='en_res')
        inst_key_spec = dict(XEN_TAIL='en_tail',
                             XEN_BIAS='en_bias',
                             XTAIL='tail',
                             XBIAS='bias',
                             XEN_RESA='en_res',
                             XEN_RESB='en_res')
        diffpair_params = dict(lch=l_dict['in'],
                               wch=w_dict['in'],
                               nf=seg_dict['in'],
                               intent=th_dict['in'])
        res_params = dict(l=l_dict['res'],
                          w=w_dict['res'],
                          intent=th_dict['res'])

        for inst in inst_key_gen.keys():
            gen_key = inst_key_gen[inst]
            spec_key = inst_key_spec[inst]
            self.instances[inst].design(l=l_dict[gen_key],
                                        w=w_dict[gen_key],
                                        intent=th_dict[gen_key],
                                        nf=seg_dict[spec_key])

        self.instances['XDIFFPAIR'].design(**diffpair_params)
        self.instances['XRA'].design(**res_params)
        self.instances['XRB'].design(**res_params)

        ### Reconnect if PMOS
        if in_type == 'p':
            diffpair_conn = dict(VINP='VINP',
                                 VINN='VINN',
                                 VOUTP='VOUTP',
                                 VOUTN='VOUTN',
                                 VDD='VDD')
            tail_conn = dict(D='VTAIL_EN',
                             G='IBP',
                             S='VDD',
                             B='VDD')
            bias_conn = dict(D='VBIAS_EN',
                             G='IBP',
                             S='VDD',
                             B='VDD')
            en_tail_conn = dict(D='VTAIL',
                                G='Bb',
                                S='VTAIL_EN',
                                B='VDD')
            en_bias_conn = dict(D='IBP',
                                G='Bb',
                                S='VBIAS_EN',
                                B='VDD')
            en_res_conn = dict(G='B',
                               B='VSS',
                               S='VSS')

            conn_map = dict(XDIFFPAIR=diffpair_conn,
                            XTAIL=tail_conn,
                            XBIAS=bias_conn,
                            XEN_TAIL=en_tail_conn,
                            XEN_BIAS=en_bias_conn,
                            XEN_RESA=en_res_conn,
                            XEN_RESB=en_res_conn,)

            for inst, conn_dict in conn_map.items():
                for pin, net in conn_dict.items():
                    self.reconnect_instance_terminal(inst, pin, net)

            self.reconnect_instance_terminal('XRA', 'PLUS', 'VOUTP_EN')
            self.reconnect_instance_terminal('XRB', 'PLUS', 'VOUTN_EN')
            self.reconnect_instance_terminal('XRA', 'MINUS', 'VOUTP')
            self.reconnect_instance_terminal('XRB', 'MINUS', 'VOUTN')
            self.reconnect_instance_terminal('XEN_RESA', 'D', 'VOUTP_EN')
            self.reconnect_instance_terminal('XEN_RESB', 'D', 'VOUTN_EN')

        ### Remove unused bias pin
        rm_bias = 'IBN' if in_type == 'p' else 'IBP'
        self.remove_pin(rm_bias)