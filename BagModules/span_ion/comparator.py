# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator(Module):
    """Module for library span_ion cell comparator.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator.yaml'))


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
            stage_params_list = 'List of fully differential cmfb stage parameters',
            single_params = 'Single-ended amplifier parameters',
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
        stage_params_list = params['stage_params_list']
        single_params = params['single_params']

        in_single = single_params['in_type']
        num_amps = len(stage_params_list)

        self.instances['XCHAIN'].design(stage_params_list=stage_params_list)
        self.instances['XSINGLE'].design(**single_params)

        # if num_amps > 1:
        #     pin_voutcm = f'VOUTCM<{num_amps-1}:0>'
        #     self.reconnect_instance_terminal('XCHAIN', pin_voutcm, pin_voutcm)
        #     self.rename_pin('VOUTCM', pin_voutcm)
            
        # Fixing biasing pins
        in_type_list = [s['in_type'] for s in stage_params_list]
        num_p = in_type_list.count('p')
        num_n = in_type_list.count('n')

        # Connecting differential stages
        if num_n > 1:
            self.reconnect_instance_terminal('XCHAIN', f'IBN<{num_n-1}:0>', f'IBN<{num_n-1}:0>')
        if num_p > 1:
            self.reconnect_instance_terminal('XCHAIN', f'IBP<{num_p-1}:0>', f'IBP<{num_p-1}:0>')

        # Connecting single-ended stage
        if single_params['in_type'] == 'p':
            num_p = num_p + 1
            pin_single = 'IBP'
            suffix_single = f'<{num_p-1}>' if num_p > 1 else ''
        else:
            num_n = num_n + 1
            pin_single = 'IBN'
            suffix_single = f'<{num_n-1}>' if num_n > 1 else ''

        self.reconnect_instance_terminal('XSINGLE', pin_single, f'{pin_single}{suffix_single}')

        # Adjusting pin names
        if num_p < 1:
            self.remove_pin(f'IBP<1:0>')
        elif num_p != 2:
            suffix_p = f'<{num_p-1}:0>' if num_p > 1 else ''
            pin_ibp = f'IBP{suffix_p}'
            self.rename_pin('IBP<1:0>', pin_ibp)

        if num_n < 1:
            self.remove_pin('IBN<1:0>')
        elif num_n != 2:
            suffix_n = f'<{num_n-1}:0>' if num_n > 1 else ''
            pin_ibn = f'IBN{suffix_n}'
            self.rename_pin('IBN<1:0>', pin_ibn)