# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_az_cmfb(Module):
    """Module for library span_ion cell comparator_az_cmfb.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_az_cmfb.yaml'))


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
            num_bits='',
            cap_params='Parameters for autozero voltage storage caps',
            main_os_params='',
            aux_os_params='',
            main_amp_params='',
            aux_amp_params='',
            sw_store_params='',
            sw_in_params=''
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

        self.instances['XMAIN_OS'].design(num_bits=num_bits, **main_os_params)
        self.instances['XAUX_OS'].design(num_bits=num_bits, **aux_os_params)
        self.instances['XMAIN_AMP'].design(**main_amp_params)
        self.instances['XAUX_AMP'].design(**aux_amp_params)
        self.instances['XSW_MAIN'].design(**sw_store_params)
        self.instances['XSW_AUX'].design(**sw_store_params)
        self.instances['XSW_A'].design(**sw_in_params)
        self.instances['XSW_B'].design(**sw_in_params)

        num_main_stages = len(main_amp_params['stage_params_list'])
        num_aux_stages = len(aux_amp_params['stage_params_list'])

        if num_main_stages > 1:
            suffix_voutcm_main = f'<{num_main_stages - 1}:0>'
            pin_voutcm_main = f'VOUTCM_MAIN{suffix_voutcm_main}'
            self.rename_pin('VOUTCM_MAIN', pin_voutcm_main)
            self.reconnect_instance_terminal('XMAIN_AMP', f'VOUTCM{suffix_voutcm_main}', pin_voutcm_main)
        if num_aux_stages > 1:
            suffix_voutcm_aux = f'<{num_aux_stages - 1}:0>'
            pin_voutcm_aux = f'VOUTCM_AUX{suffix_voutcm_aux}'
            self.rename_pin('VOUTCM_AUX', pin_voutcm_aux)
            self.reconnect_instance_terminal('XAUX_AMP', f'VOUTCM{suffix_voutcm_aux}', pin_voutcm_aux)

        main_in_type = main_os_params['in_type']
        aux_in_type = aux_os_params['in_type']

        rm_b = 'n' not in (main_in_type, aux_in_type)
        rm_bb = 'p' not in (main_in_type, aux_in_type)

        if rm_b:
            self.remove_pin('B')
        if rm_bb:
            self.remove_pin('Bb')

        if num_bits > 1:
            suffix_bits = f'<{num_bits - 1}:0>'
            if not rm_b:
                self.rename_pin('B', f'B{suffix_bits}')
                self.reconnect_instance_terminal('XMAIN_OS', f'B{suffix_bits}', f'B{suffix_bits}')
                self.reconnect_instance_terminal('XAUX_OS', f'B{suffix_bits}', f'B{suffix_bits}')
            if not rm_bb:
                self.rename_pin('Bb', f'Bb{suffix_bits}')
                self.reconnect_instance_terminal('XMAIN_OS', f'Bb{suffix_bits}', f'Bb{suffix_bits}')
                self.reconnect_instance_terminal('XAUX_OS', f'Bb{suffix_bits}', f'Bb{suffix_bits}')
