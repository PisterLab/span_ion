# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_chain_az(Module):
    """Module for library span_ion cell comparator_fd_chain_az.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_chain_az.yaml'))


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
            stage_params_list = 'List of comparator_fd_stage parameters, in order',
            az_params = 'comparator_az_connection parameters'
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
        az_params = params['az_params']
        stage_params_list = params['stage_params_list']

        # Design instances
        self.instances['XAZ'].design(**az_params)
        self.instances['XAMP'].design(stage_params_list=stage_params_list)

        # Remove unnecessary pins
        in_params = az_params['in_params']
        sample_params = az_params['sample_params']
        fb_params = az_params['fb_params']
        
        in_type = in_params['mos_type']
        sample_type = sample_params['mos_type']
        fb_type = fb_params['mos_type']
        pin_needs = dict(PHI=(in_type != 'p' or sample_type != 'n'),
                         PHIb=(in_type != 'n' or sample_type != 'p'),
                         PHI_EARLY=(fb_type != 'p'),
                         PHI_EARLYb=(fb_type != 'n'))

        for pin,needed in pin_needs.items():
            if not needed:
                self.remove_pin(pin)

        # Rename pins as necessary
        num_stages = len(stage_params_list)
        if num_stages > 1:
            voutcm_pin = f'VOUTCM<{num_stages-1}:0>'
            self.reconnect_instance_terminal('XAMP', voutcm_pin, voutcm_pin)
            self.rename_pin('VOUTCM', voutcm_pin)