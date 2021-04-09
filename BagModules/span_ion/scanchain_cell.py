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
            buf_load_params = 'inv_chain load buffer parameters. Must have an even number of inverters.',
            buf_clk_params = 'inv_chain clock buffer parameters. Must have an even number of inverters.',
            inv_data_params = 'Parameters for the inverter spitting out the data_out going outside scan',
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
        buf_clk_params = params['buf_clk_params']
        buf_load_params = params['buf_load_params']
        inv_data_params = params['inv_data_params']
        dff_params = params['dff_params']

        ### Enforcing a lot of necessary relative timing conditions
        assert len(buf_clk_params['inv_param_list']) % 2 == 0, f'Clock buffer must have an even number of inverters'
        assert len(buf_load_params['inv_param_list']) % 2 == 0, f'Load buffer must have an even number of inverters'
        assert len(buf_data_params['inv_param_list']) % 2 == 0, f'Data next buffer must have an even number of inverters'

        ### Enforcing stack = 1 for all inverters
        for inv in buf_data_params['inv_param_list']:
            assert inv['stack_n'] == inv['stack_p'] == 1, f'Data buffer should have a stack of 1 for inverters'

        for inv in buf_clk_params['inv_param_list']:
            assert inv['stack_n'] == inv['stack_p'] == 1, f'Data buffer should have a stack of 1 for inverters'

        for inv in buf_load_params['inv_param_list']:
            assert inv['stack_n'] == inv['stack_p'] == 1, f'Data buffer should have a stack of 1 for inverters'

        inv_data_params.update(dict(stack_n=1, stack_p=1))

        ### Design instances
        for i in range(3):
            self.instances[f'XDFF<{i}>'].design(diff_clk=False, pos_edge=True, **dff_params)

        self.instances['XBUF_CLK'].design(dual_output=True, **buf_clk_params)
        self.instances['XBUF_LOAD'].design(dual_output=True, **buf_load_params)
        self.instances['XBUF_DATA'].design(dual_output=False, **buf_data_params)
        self.instances['XINV_DATA'].design(**inv_data_params)