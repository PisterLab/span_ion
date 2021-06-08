# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_cmfb(Module):
    """Module for library span_ion cell comparator_cmfb.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_cmfb.yaml'))


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
            stage_params_list='List of fully differential cmfb stage parameters',
            single_params='Single-ended amplifier parameters',
            constgm_params=''
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
        constgm_params = params['constgm_params']

        in_single = single_params['in_type']
        num_amps = len(stage_params_list)

        self.instances['XCHAIN'].design(stage_params_list=stage_params_list)
        self.instances['XSINGLE'].design(**single_params)
        self.instances['XCONSTGM'].design(res_side=in_single, **constgm_params)

        pin_gtail = 'VP' if in_single == 'p' else 'VN'
        self.reconnect_instance_terminal('XCONSTGM', pin_gtail, 'VGTAIL')

        if num_amps > 1:
            pin_voutcm = f'VOUTCM<{num_amps - 1}:0>'
            self.reconnect_instance_terminal('XCHAIN', pin_voutcm, pin_voutcm)
            self.rename_pin('VOUTCM', pin_voutcm)