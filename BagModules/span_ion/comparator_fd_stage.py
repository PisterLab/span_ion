# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_stage(Module):
    """Module for library span_ion cell comparator_fd_stage.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_stage.yaml'))


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
            in_type = 'n or p for NMOS or PMOS input pair',
            l_dict = 'Dictionary of channel and resistor lengths, keys (res, in, tail)',
            w_dict = 'Dictionary of channel and resistor widhts, keys (res, in, tail)',
            th_dict = 'Dictionary of channel and resistor flavors, keys (res, in, tail)',
            seg_dict = 'Dictionary of number of segments of devices (in, tail, bias)',
            has_diode = 'True to include diode-connecting biasing device, False to just have the gate connection.'
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
        has_diode = params['has_diode']

        ### Replace instances if necessary
        if in_type == 'p':
            for inst in ('XINA', 'XINB'):
                self.replace_instance_master(inst_name=inst,
                                             lib_name='BAG_prim',
                                             cell_name='pmos4_standard')

            if has_diode:
                self.replace_instance_master(inst_name='XIBIAS',
                                             lib_name='bag2_analog',
                                             cell_name='mirror_p')
            else:
                self.replace_instance_master(inst_name='XIBIAS',
                                             lib_name='BAG_prim',
                                             cell_name='pmos4_standard')
        elif not has_diode:
            self.replace_instance_master(inst_name='XIBIAS',
                                         lib_name='BAG_prim',
                                         cell_name='nmos4_standard')

        ### Design instances
        # Input
        self.instances['XINA'].design(l=l_dict['in'],
                                      w=w_dict['in'],
                                      nf=seg_dict['in'],
                                      intent=th_dict['in'])
        self.instances['XINB'].design(l=l_dict['in'],
                                      w=w_dict['in'],
                                      nf=seg_dict['in'],
                                      intent=th_dict['in'])
        # Tail
        if has_diode:
            self.instances['XIBIAS'].design(device_params=dict(l=l_dict['tail'],
                                                               w=w_dict['tail'],
                                                               intent=th_dict['tail']),
                                            seg_in=seg_dict['bias'],
                                            seg_out_list=[seg_dict['tail']])
        else:
            self.instances['XIBIAS'].design(l=l_dict['tail'],
                                            w=w_dict['tail'],
                                            intent=th_dict['tail'],
                                            nf=seg_dict['tail'])

        # Resistors
        self.instances['XRA'].design(w=w_dict['res'],
                                     l=l_dict['res'],
                                     intent=th_dict['res'])
        self.instances['XRB'].design(w=w_dict['res'],
                                     l=l_dict['res'],
                                     intent=th_dict['res'])

        ### Reconnect instances if necessary
        ibias_reconn_dict = dict()

        if in_type == 'p':
            # Resistors
            self.reconnect_instance_terminal('XRA', 'MINUS', 'VOUTN')
            self.reconnect_instance_terminal('XRB', 'MINUS', 'VOUTP')
            self.reconnect_instance_terminal('XRA', 'PLUS', 'VSS')
            self.reconnect_instance_terminal('XRB', 'PLUS', 'VSS')

            # Input
            self.reconnect_instance_terminal('XINA', 'B', 'VDD')
            self.reconnect_instance_terminal('XINB', 'B', 'VDD')

            # Biasing
            if has_diode:
                ibias_reconn_dict.update({'VDD' : 'VDD',
                                          's_in' : 'VDD',
                                          's_out' : 'VDD',
                                          'in' : 'IBP',
                                          'out' : 'VTAIL'})
            else:
                ibias_reconn_dict.update({'G' : 'VBP',
                                          'S' : 'VDD',
                                          'D' : 'VTAIL',
                                          'B' : 'VDD'})
        elif not has_diode:
            ibias_reconn_dict.update({'G' : 'VBN',
                                      'S' : 'VSS',
                                      'D' : 'VTAIL',
                                      'B' : 'VSS'})

        for port, net in ibias_reconn_dict.items():
            self.reconnect_instance_terminal('XIBIAS', port, net)

        ### Change pins as necessary
        if in_type == 'p':
            if has_diode:
                self.rename_pin('IBN', 'IBP')
            else:
                self.rename_pin('IBN', 'VBP')
        elif not has_diode:
            self.rename_pin('IBN', 'VBN')