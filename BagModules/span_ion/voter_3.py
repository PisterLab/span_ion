# -*- coding: utf-8 -*-

from typing import Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__voter_3(Module):
    """Module for library span_ion cell voter_3.

    3-input majority gate, implemented with NAND logic.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'voter_3.yaml'))


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
            in_params = 'Input NAND parameters',
            out_params = 'Output NAND parameters'
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
        in_params = params['in_params']
        out_params = params['out_params']

        # Design instances
        for i in range(3):
            self.instances[f'XIN<{i}>'].design(num_in=2, **in_params)

        self.instances['XOUT'].design(num_in=3, **out_params)

        # Wire me up, Scotty!
        for i in range(3):
            self.reconnect_instance_terminal(f'XIN<{i}>', 'in<1:0>', f'in<{i}>,in<{(i+1)%3}>')

        self.reconnect_instance_terminal('XOUT', 'in<2:0>', 'mid<2:0>')