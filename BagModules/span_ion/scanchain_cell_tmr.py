# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__scanchain_cell_tmr(Module):
    """Module for library span_ion cell scanchain_cell_tmr.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'scanchain_cell_tmr.yaml'))


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
            cell_params = 'Individual scan_cell parameters',
            vote_3x3_params = '3x3 voter parameters',
            vote_3x1_params = '3x1 voter parameters'
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
        cell_params = params['cell_params']
        vote_3x3_params = params['vote_3x3_params']
        vote_3x1_params = params['vote_3x1_params']

        self.instances['XCELL<2:0>'].design(**cell_params)
        self.instances['XVOTE_DATAOUT'].design(**vote_3x1_params)
        self.instances['XVOTE_DATANEXT'].design(**vote_3x3_params)
