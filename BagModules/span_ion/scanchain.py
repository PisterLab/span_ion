# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__scanchain(Module):
    """Module for library span_ion cell scanchain.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'scanchain.yaml'))


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
            num_bits = 'Number of scan bits',
            scan_cell_params = 'Parameters for a singular scan chain cell',
            voter_params = 'Parameters for the 3-way majority voter'
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
        scan_cell_params = params['scan_cell_params']
        voter_params = params['voter_params']

        ### Design elements
        # Singular scan chains
        for i in range(3):
            self.instances[f'XCHAIN<{i}>'].design(num_bits=num_bits, **scan_cell_params)

        # Data voters
        self.array_instance('XVOTE_DATA', 
                            [f'XVOTE_DATA<{i}>' for i in range(num_bits)],
                            [{'in<2:0>' : f'SCAN_DATA2<{i}>,SCAN_DATA1<{i}>,SCAN_DATA0<{i}>',
                              'out' : f'SCAN_DATA<{i}>'} for i in range(num_bits)])
        for i in range(num_bits):
            self.instances['XVOTE_DATA'][i].design(**voter_params)

        # Scan out voter
        self.instances['XVOTE_OUTb'].design(**voter_params)

        ### Fix wiring
        # Singular scan chains
        for i in range(3):
            self.reconnect_instance_terminal(f'XCHAIN<{i}>', f'SCAN_DATA<{num_bits-1}:0>', f'SCAN_DATA{i}<{num_bits-1}:0>')

        ### Fix pins
        self.rename_pin('SCAN_DATA', f'SCAN_DATA<{num_bits-1}:0>')