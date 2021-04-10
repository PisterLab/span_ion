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

        assert num_bits > 1, f'Currently only supports 2 or more cells'

        ### Array TMR scan cells
        suffix_forward_full = f'<{num_bits-1}:0>'
        suffix_backward_full = f'<0:{num_bits - 1}>'
        suffix_backward_short = f'<0:{num_bits - 2}>'
        cells_conn_dict = { 'LOAD_INb'      : f'SCAN_LOADb,LOADb{suffix_backward_short}',
                            'DATA_INb<0>'   : f'SCAN_INb,SHIFTb0{suffix_backward_short}',
                            'DATA_INb<1>'   : f'SCAN_INb,SHIFTb1{suffix_backward_short}',
                            'DATA_INb<2>'   : f'SCAN_INb,SHIFTb2{suffix_backward_short}',
                            'CLK_IN'        : f'SCAN_CLKb,CLKINT{suffix_backward_short}',
                            'LOAD_NEXTb'    : f'LOADb{suffix_backward_full}',
                            'DATA_OUT'      : f'SCAN_DATA{suffix_forward_full}',
                            'DATA_NEXTb<0>' : f'SHIFTb0{suffix_backward_short},SCAN_OUTb',
                            'DATA_NEXTb<1>' : f'SHIFTb1{suffix_backward_short},SCAN_OUTb',
                            'DATA_NEXTb<2>' : f'SHIFTb2{suffix_backward_short},SCAN_OUTb',
                            'CLK_NEXT'      : f'CLKINT{suffix_backward_full}'}

        self.array_instance('XCELL', [f'XCELL{suffix_backward_full}'], [cells_conn_dict])

        ### Design cells
        self.instances['XCELL'][0].design(**scan_cell_params)

        ### NoConns used for intermediate signals
        self.reconnect_instance_terminal('XNOCONN_LOAD', 'noConn', f'LOADb<{num_bits-1}>')
        self.reconnect_instance_terminal('XNOCONN_CLK', 'noConn', f'CLKINT<{num_bits - 1}>')

        ### Rename data out pin
        self.rename_pin('SCAN_DATA', f'SCAN_DATA{suffix_forward_full}')