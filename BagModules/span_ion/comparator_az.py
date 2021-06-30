# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_az(Module):
    """Module for library span_ion cell comparator_az.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_az.yaml'))


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
            num_bits = 'THermometer; number of DAC elements for offset control',
            cap_params = 'Parameters for autozero voltage storage caps',
            main_os_params = 'Offset removal amplifier stage for main amplifier',
            aux_os_params = 'Offset removal amplifier stage for auxiliary amplifier',
            main_amp_params = 'Amplifier stage for main amplifier',
            aux_amp_params = 'Amplifier stage for auxiliary amplifier',
            sw_store_params = 'Switches which lead up to the large capacitors',
            sw_in_params = 'Switches which connect to the inputs of the auxiliary amplifier'
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
        cap_params = params['cap_params']
        main_os_params = params['main_os_params']
        aux_os_params = params['aux_os_params']
        main_amp_params = params['main_amp_params']
        aux_amp_params = params['aux_amp_params']
        sw_store_params = params['sw_store_params']
        sw_in_params = params['sw_in_params']

        ### Design instances
        self.instances['XMAIN_OS'].design(num_bits=num_bits, **main_os_params)
        self.instances['XAUX_OS'].design(num_bits=num_bits, **aux_os_params)
        self.instances['XMAIN_AMP'].design(**main_amp_params)
        self.instances['XAUX_AMP'].design(**aux_amp_params)
        self.instances['XSW_MAIN<1:0>'].design(**sw_store_params)
        self.instances['XSW_AUX<1:0>'].design(**sw_store_params)
        self.instances['XSW_A'].design(**sw_in_params)
        self.instances['XSW_B'].design(**sw_in_params)

        self.instances['XC_MAIN<1:0>'].parameters = cap_params
        self.instances['XC_AUX<1:0>'].parameters = cap_params

        ### Wiring up biasing
        # Main offset
        rm_main_os = 'IBN' if main_os_params['in_type'] == 'p' else 'IBP'
        self.remove_pin(f'{rm_main_os}_MAIN_OS_CANCEL')
        self.remove_pin(f'{rm_main_os}_MAIN_OS_AMP')

        # Aux offset
        rm_aux_os = 'IBN' if aux_os_params['in_type'] == 'p' else 'IBP'
        self.remove_pin(f'{rm_aux_os}_AUX_OS_CANCEL')
        self.remove_pin(f'{rm_aux_os}_AUX_OS_AMP')

        # Main amp
        main_amp_list = [s['in_type'] for s in main_amp_params['stage_params_list']]\
                        + [main_amp_params['single_params']['in_type']]

        num_main_amp_p = main_amp_list.count('p')
        if num_main_amp_p < 1:
            self.remove_pin('IBP_MAIN_AMP<1:0>')
        elif num_main_amp_p != 2:
            suffix_main_amp_p = '' if num_main_amp_p < 2 else f'<{num_main_amp_p-1}:0>'
            self.rename_pin('IBP_MAIN_AMP<1:0>', f'IBP_MAIN_AMP{suffix_main_amp_p}')
            self.reconnect_instance_terminal('XMAIN_AMP', f'IBP{suffix_main_amp_p}', f'IBP_MAIN_AMP{suffix_main_amp_p}')

        num_main_amp_n = main_amp_list.count('n')
        if num_main_amp_n < 1:
            self.remove_pin('IBN_MAIN_AMP<1:0>')
        elif num_main_amp_n != 2:
            suffix_main_amp_n = '' if num_main_amp_n < 2 else f'<{num_main_amp_n-1}:0>'
            self.rename_pin('IBN_MAIN_AMP<1:0>', f'IBN_MAIN_AMP{suffix_main_amp_n}')
            self.reconnect_instance_terminal('XMAIN_AMP', f'IBN{suffix_main_amp_n}', f'IBN_MAIN_AMP{suffix_main_amp_n}')

        # Aux amp
        aux_amp_list = [s['in_type'] for s in aux_amp_params['stage_params_list']]

        num_aux_amp_p = aux_amp_list.count('p')
        if num_aux_amp_p < 1:
            self.remove_pin('IBP_AUX_AMP')
        elif num_aux_amp_p > 1:
            suffix_aux_amp_p = '' if num_aux_amp_p < 1 else f'<{num_aux_amp_p-1}:0>'
            self.rename_pin('IBP_AUX_AMP', f'IBP_AUX_AMP{suffix_aux_amp_p}')
            self.reconnect_instance_terminal('XAUX_AMP', f'IBP{suffix_aux_amp_p}', f'IBP_AUX_AMP{suffix_aux_amp_p}')

        num_aux_amp_n = aux_amp_list.count('n')
        if num_aux_amp_n < 1:
            self.remove_pin('IBN_AUX_AMP')
        elif num_aux_amp_n > 1:
            suffix_aux_amp_n = '' if num_aux_amp_n < 1 else f'<{num_aux_amp_n - 1}:0>'
            self.rename_pin('IBN_AUX_AMP', f'IBN_AUX_AMP{suffix_aux_amp_n}')
            self.reconnect_instance_terminal('XAUX_AMP', f'IBN{suffix_aux_amp_n}', f'IBN_AUX_AMP{suffix_aux_amp_n}')

        ### Wiring up tuning bits
        main_in_type = main_os_params['in_type']
        aux_in_type = aux_os_params['in_type']
        rm_bb = 'p' not in (main_in_type, aux_in_type)
        rm_b = 'n' not in (main_in_type, aux_in_type)
        keep_bb = not rm_bb
        keep_b = not rm_b

        if rm_bb:
            self.remove_pin('Bb')
        if rm_b:
            self.remove_pin('B')

        if num_bits > 1:
            suffix_bits = f'<{num_bits-1}:0>'
            if keep_bb:
                self.rename_pin('Bb', f'Bb{suffix_bits}')
                if main_in_type == 'p':
                    self.reconnect_instance_terminal('XMAIN_OS', f'Bb{suffix_bits}', f'Bb{suffix_bits}')
                if aux_in_type == 'p':
                    self.reconnect_instance_terminal('XAUX_OS', f'Bb{suffix_bits}', f'Bb{suffix_bits}')
            if keep_b:
                self.rename_pin('B', f'B{suffix_bits}')
                if main_in_type == 'n':
                    self.reconnect_instance_terminal('XMAIN_OS', f'B{suffix_bits}', f'B{suffix_bits}')
                if aux_in_type == 'n':
                    self.reconnect_instance_terminal('XAUX_OS', f'B{suffix_bits}', f'B{suffix_bits}')