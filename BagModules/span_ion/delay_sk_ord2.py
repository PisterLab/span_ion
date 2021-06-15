# -*- coding: utf-8 -*-

from typing import Mapping

import os
import pkg_resources
import warnings

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__delay_sk_ord2(Module):
    """Module for library span_ion cell delay_sk_ord2.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'delay_sk_ord2.yaml'))


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
            num_bits = 'Number of bits for resistor tuning',
            res_params_list = 'List of resistor parameters. Ordering is indicated in the schematic by the index of the resistor.',
            cap_params_list = 'List of cap parameters. Ordering is indicated in schematic indices.',
            amp_params = 'Amplifier parameters',
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
        num_bits = params['num_bits']
        amp_params = params['amp_params']
        res_params_list = params['res_params_list']
        cap_params_list = params['cap_params_list']

        # Design instances
        self.instances['XAMP'].design(**amp_params)

        for i, res_params in enumerate(res_params_list):
            res_params_copy = res_params.copy()
            res_params_copy.update(dict(res_groupings=[2**j for j in range(num_bits)]))
            self.instances[f'XR<{i}>'].design(**res_params_copy)

            if num_bits > 1:
                suffix_ctrl = f'<{num_bits-1}:0>'
                self.reconnect_instance_terminal(f'XR<{i}>', f'CTRL{suffix_ctrl}', f'CTRL{suffix_ctrl}')
                self.reconnect_instance_terminal(f'XR<{i}>', f'CTRLb{suffix_ctrl}', f'CTRLb{suffix_ctrl}')
                self.rename_pin('CTRL', f'CTRL{suffix_ctrl}')
                self.rename_pin('CTRLb', f'CTRLb{suffix_ctrl}')

        for i in range(2):
            self.instances[f'XC<{i}>'].parameters = cap_params_list[i]
        
        warnings.warn('(delay_sk_ord2) Check generated cap values.')

        # Rewire tail biasing if necessary
        if amp_params['in_type'].lower() == 'p':
            self.reconnect_instance_terminal('XAMP', 'IBP', 'IBP')
            self.rename_pin('IBN', 'IBP')
        else:
             raise ValueError(f"in_type of amplifier {amp_params['in_type']} is invalid (should be p or n)")

        # Removing unnecessary pins
        if num_bits < 1:
            self.remove_pin('CTRL')
            self.remove_pin('CTRLb')