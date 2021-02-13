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

        # Array stages and rewire as necessary
        if num_stages > 1:
            conn_dict_list = []
            for i in range(num_stages):
                conn_dict = dict(VINP='VINP' if i==0 else f'VMIDP<{i-1}>',
                                 VINN='VINN' if i==0 else f'VMIDN<{i-1}>',
                                 VOUTCM=f'VOUTCM<{i}>',
                                 VOUTN='VOUTN' if i==num_stages-1 else f'VMIDN<{i}>',
                                 VOUTP='VOUTP' if i==num_stages-1 else f'VMIDP<{i}>',
                                 VDD='VDD',
                                 VSS='VSS')
                conn_dict_list.append(conn_dict)

            self.array_instance('XSTAGE',
                                [f'XSTAGE<{i}>' for i in range(num_stages)],
                                conn_dict_list)

            self.rename_pin('VOUTCM', f'VOUTCM<{num_stages-1}:0>')

            for i in range(num_stages):
                self.instances['XSTAGE'][i].design(**(stage_params_list[i]))
        else:
            self.instances['XSTAGE'].design(**(stage_params_list[0]))