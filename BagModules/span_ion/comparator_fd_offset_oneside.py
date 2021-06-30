# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_offset_oneside(Module):
    """Module for library span_ion cell comparator_fd_offset_oneside.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_offset_oneside.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            in_type='"p" or "n" for NMOS or PMOS input pair',
            num_bits='Number of binary bits for tuning',
            l_dict='Channel and resistor lengths (in, tail, enable)',
            w_dict='Channel and resistor widths',
            th_dict='Device and resistor flavors',
            seg_dict='Device and resistor number of devices (in, tail, enable, bias)',
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
        num_bits = params['num_bits']
        l_dict = params['l_dict']
        w_dict = params['w_dict']
        th_dict = params['th_dict']
        seg_dict = params['seg_dict']

        # Replace instances with PMOS if necessary
        if in_type == 'p':
            fet_insts = ['INA', 'INB', 'EN', 'TAIL']
            for inst in fet_insts:
                self.replace_instance_master(inst_name=f'X{inst}',
                                             lib_name='BAG_prim',
                                             cell_name='pmos4_standard')

        # Design instances
        key_map = dict(XEN='en',
                       XTAIL='tail',
                       XINA='in',
                       XINB='in')
        for name, dict_key in key_map.items():
            self.instances[name].design(l=l_dict[dict_key],
                                        w=w_dict[dict_key],
                                        nf=seg_dict[dict_key],
                                        intent=th_dict[dict_key])

        # Array DAC components for tuning and adjust wiring
        ctrl_base = 'Bb' if in_type == 'p' else 'B'
        conn_body = 'VDD' if in_type == 'p' else 'VSS'
        if num_bits > 1:
            num_dac_elems = 2 ** num_bits - 1
            ctrl_gate_lst = []  # Construct the gate connection
            for i in range(num_bits)[::-1]:
                prefix = f'<*{2 ** i}>' if i > 0 else ''
                suffix = f'<{i}>'
                ctrl_gate_lst = ctrl_gate_lst + [f'{prefix}{ctrl_base}{suffix}']
            ctrl_gate = ','.join(ctrl_gate_lst)
            self.array_instance('XEN', [f'XEN<{num_dac_elems - 1}:0>'], [dict(D='VTAIL',
                                                                              G=ctrl_gate,
                                                                              S=f'VTAIL_EN<{num_dac_elems - 1}:0>',
                                                                              B=conn_body)])
            self.array_instance('XTAIL', [f'XTAIL<{num_dac_elems - 1}:0>'], [dict(D=f'VTAIL_EN<{num_dac_elems - 1}:0>',
                                                                                  G='VAZ',
                                                                                  S=conn_body,
                                                                                  B=conn_body)])
        else:
            self.reconnect_instance_terminal('XEN', 'G', ctrl_base)

        self.reconnect_instance_terminal('XINA', 'B', conn_body)
        self.reconnect_instance_terminal('XINB', 'B', conn_body)

        # Remove any unnecessary supply pin
        if in_type == 'p':
            self.remove_pin('VSS')
        else:
            self.remove_pin('VDD')

        # Rename gate pin as necessary
        if num_bits > 1:
            self.rename_pin('B', f'{ctrl_base}<{num_bits - 1}:0>')