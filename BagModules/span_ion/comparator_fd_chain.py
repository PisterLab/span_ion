# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_chain(Module):
    """Module for library span_ion cell comparator_fd_chain.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_chain.yaml'))


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
            stage_params_list = 'List of comparator_fd_stage parameters, in order',
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
        stage_params_list = params['stage_params_list']

        num_stages = len(stage_params_list)
        assert num_stages > 0, f'Number of stages {num_stages} should be > 0'

        ### Fixing indices of biasing pins
        in_type_list = [s['in_type'] for s in stage_params_list]
        num_p = in_type_list.count('p')
        num_n = in_type_list.count('n')

        # Change the pin
        if num_p < 1:
            self.remove_pin('IBP')
        elif num_p > 1:
            self.rename_pin('IBP', f'IBP<{num_p - 1}:0>')

        if num_n < 1:
            self.remove_pin('IBN')
        elif num_n > 1:
            self.rename_pin('IBN', f'IBN<{num_n - 1}:0>')

        ### Array stages and wire inputs to outputs of the chain
        if num_stages > 1:
            conn_dict_list = []
            idx_n = 0
            idx_p = 0
            for i in range(num_stages):
                stage_params = stage_params_list[i]
                suffix_p = f'<{idx_p}>' if num_p > 1 else ''
                suffix_n = f'<{idx_n}>' if num_n > 1 else ''
                conn_dict = dict(VINP='VINP' if i==0 else f'VMIDP<{i-1}>',
                                 VINN='VINN' if i==0 else f'VMIDN<{i-1}>',
                                 VOUTN='VOUTN' if i==num_stages-1 else f'VMIDN<{i}>',
                                 VOUTP='VOUTP' if i==num_stages-1 else f'VMIDP<{i}>',
                                 VDD='VDD',
                                 VSS='VSS',
                                 IBP=f'IBP{suffix_p}',
                                 IBN=f'IBN{suffix_n}')
                if stage_params['in_type'] == 'p':
                    idx_p = idx_p + 1
                elif stage_params['in_type'] == 'n':
                    idx_n = idx_n + 1

                conn_dict_list.append(conn_dict)

            self.array_instance('XSTAGE',
                                [f'XSTAGE<{i}>' for i in range(num_stages)],
                                conn_dict_list)

            for i in range(num_stages):
                self.instances['XSTAGE'][i].design(**stage_params)
        else:
            self.instances['XSTAGE'].design(**(stage_params_list[0]))
        #
        # # Wire up biasing of components
        # idx_n = 0
        # idx_p = 0
        # for i in range(num_stages):
        #     stage_params = stage_params_list[i]
        #     if stage_params['in_type'] == 'p':
        #         suffix_p = f'<{idx_p}>' if num_p > 1 else ''
        #         self.reconnect_instance_terminal(f'XSTAGE<{i}>', 'IBP', f'IBP{suffix_p}')
        #         idx_p = idx_p + 1
        #     else:
        #         suffix_n = f'<{idx_n}>' if num_n > 1 else ''
        #         self.reconnect_instance_terminal(f'XSTAGE<{i}>', 'IBN', f'IBN{suffix_n}')
        #         idx_n = idx_n + 1
