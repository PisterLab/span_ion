# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__inv_delay_line_unit(Module):
    """Module for library span_ion cell inv_delay_line_unit.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'inv_delay_line_unit.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            inv_tristate_params = 'Tristate inverter parameters',
            inv_params = 'Standard inverter parameters',
            cap_params = 'Cap parameters'
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
        inv_tristate_params = params['inv_tristate_params']
        inv_params = params['inv_params']
        cap_params = params['cap_params']

        # Design instances
        self.instances['XINV_TRI'].design(**inv_tristate_params)
        self.instances['XINV'].design(stack_n=1, stack_p=1, **inv_params)
        self.instances['XCAP'].parameters = cap_params