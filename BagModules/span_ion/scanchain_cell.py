# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__scanchain_cell(Module):
    """Module for library span_ion cell scanchain_cell.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'scanchain_cell.yaml'))


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
            buf_data_params = 'inv_chain data buffer parameters',
            inv_params = 'Parameters for inverters not in the data buffer',
            dff_params = 'Flip-flop parameters'
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
        buf_data_params = params['buf_data_params']
        inv_params = params['inv_params']
        dff_params = params['dff_params']

        buf_not_data_params = dict(dual_output=True,
                                   inv_param_list=[inv_params]*2)

        for i in range(3):
            self.instances[f'XDFF<{i}>'].design(**dff_params)

        self.instances['XBUF_CLK'].design(**buf_not_data_params)
        self.instances['XBUF_LOAD'].design(**buf_not_data_params)
        self.instances['XBUF_DATA'].design(dual_output=False, **buf_data_params)
        self.instances['XINV_DATA'].design(**inv_params)