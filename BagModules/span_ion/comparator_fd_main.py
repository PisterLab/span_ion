# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_main(Module):
    """Module for library span_ion cell comparator_fd_main.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_main.yaml'))


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
            diffpair_params = 'Differential pair parameters',
            res_params = 'Resistor strip parameters',
            bulk_conn = 'Bulk connection for resistors'
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
        diffpair_params = params['diffpair_params']
        res_params = params['res_params']
        bulk_conn = params['bulk_conn']

        assert bulk_conn in ('VDD', 'VSS'), f'Bulk must be connected to VDD or VSS, not {bulk_conn}'

        self.instances['RN'].design(**res_params)
        self.instances['RP'].design(**res_params)
        self.instances['XDIFFPAIR'].design(**diffpair_params)

        self.reconnect_instance_terminal('RN', 'BULK', bulk_conn)
        self.reconnect_instance_terminal('RP', 'BULK', bulk_conn)