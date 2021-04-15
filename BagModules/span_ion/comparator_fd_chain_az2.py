# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources
import warnings

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_chain_az2(Module):
    """Module for library span_ion cell comparator_fd_chain_az2.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_chain_az2.yaml'))


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
            sample_params = 'comparator_az_sample parameters',
            stage_params_list = 'List of comparator_fd_stage_cmfb parameters, in order',
            fb_params='comparator_az_fb parameters',
            comp_params_list='List of compensation block parameters',
            comp_conn_list='List of where to connect two ends of compensation',
            inv_clk_params = 'Initial clock inverter parameters',
            buf_clk_params = 'Clock buffer parameters'
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
        sample_params = params['sample_params']
        stage_params_list = params['stage_params_list']
        fb_params = params['fb_params']
        comp_params_list = params['comp_params_list']
        comp_conn_list = params['comp_conn_list']
        inv_clk_params = params['inv_clk_params']
        buf_clk_params = params['buf_clk_params']

        ## Design instances
        self.instances['XSAMPLE'].design(**sample_params)
        self.instances['XCHAIN_FB'].design(stage_params_list=stage_params_list,
                                           az_params=fb_params,
                                           comp_params_list=comp_params_list,
                                           comp_conn_list=comp_conn_list)
        self.instances['XINV'].design(stack_n=1, stack_p=1, **inv_clk_params)

        buf_lst = buf_clk_params['inv_param_list']
        assert len(buf_lst) > 1, f'Must have at least 2 inverters in clock buffer'
        for inv in buf_lst:
            if inv.get('stack_n', 0) != 1 or inv.get('stack_p', 0) != 1:
                warnings.warn('(comparator_fd_chain_az2) changing all inverters to have stack 1')
                inv.update(dict(stack_n=1, stack_p=1))

        self.instances['XBUF'].design(dual_output=True, **buf_clk_params)

        ## Renaming pins to match indices
        num_stages = len(stage_params_list)
        if num_stages > 1:
            suffix_voutcm = f'<{num_stages-1}:0>'
            self.reconnect_instance_terminal('XCHAIN_FB', f'VOUTCM{suffix_voutcm}', f'VOUTCM{suffix_voutcm}')
            self.rename_pin('VOUTCM', f'VOUTCM{suffix_voutcm}')