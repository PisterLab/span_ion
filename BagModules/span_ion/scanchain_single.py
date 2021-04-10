# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__scanchain_single(Module):
    """Module for library span_ion cell scanchain_single.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'scanchain_single.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping:
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            num_bits = 'Number of scan chain bits',
            buf_data_params = 'Scan cell inv_chain data buffer parameters',
            inv_params = 'Scan cell parameters for inverters not in the data buffer',
            dff_params = 'Scan cell flip-flop parameters'
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
        buf_data_params = params['buf_data_params']
        inv_params = params['inv_params']
        dff_params = params['dff_params']

        assert num_bits > 2, f'Currently need more than 2 bits'

        suffix_backward_full = f'<0:{num_bits-1}>'
        suffix_backward_short = f'<0:{num_bits-2}>'
        suffix_forward_full = f'<{num_bits-1}:0>'

        # Array cells
        pin_conn = dict(LOAD_INb=f'SCAN_LOADb,LOADb{suffix_backward_short}',
                        DATA_INb=f'SCAN_INb,SHIFTb{suffix_backward_short}',
                        CLK_IN=f'SCAN_CLKb,CLKINT{suffix_backward_short}',
                        LOAD_NEXTb=f'LOADb{suffix_forward_full}',
                        DATA_OUT=f'SCAN_DATA{suffix_forward_full}',
                        DATA_NEXTb=f'SHIFTb{suffix_backward_short},SCAN_OUTb',
                        CLK_NEXT=f'CLKINT{suffix_backward_full}')

        self.array_instance('XCELL', [f'XCELL{suffix_backward_full}'], [pin_conn])

        # Design cells
        self.instances['XCELL'][0].design(buf_data_params=buf_data_params,
                                          inv_params=inv_params,
                                          dff_params=dff_params)

        # NoConns for unused intermediate signals
        self.reconnect_instance_terminal('XNOCONN_LOAD', 'noConn', f'LOADb<{num_bits-1}>')
        self.reconnect_instance_terminal('XNOCONN_CLK', 'noConn', f'CLKINT<{num_bits-1}>')

        # Rename data out pin
        self.rename_pin('SCAN_DATA', f'SCAN_DATA{suffix_forward_full}')