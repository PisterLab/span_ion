# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_az2(Module):
    """Module for library span_ion cell comparator_fd_az2.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_az2.yaml'))


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
            inv_out='True to invert the output',
            az_params_list='List of comparator_fd_chain_az2 parameters',
            single_params='Differential in to single ended out parameters',
            constgm_params='Constant gm parameters',
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
        az_params_list = params['az_params_list']

        num_az_chunks = len(az_params_list)
        assert num_az_chunks > 0, f'Number of autozeroed stages ({num_az_chunks}) should be > 0'

        ### Designing and wiring up the instances of the autozeroed fully differential amps
        if num_az_chunks > 1:
            inst_list = []
            conn_dict_list = []

            voutcm_start = 0
            for i in range(num_az_chunks):
                # Getting indices of VOUTCM connection
                az_params = az_params_list[i]
                num_amps = len(az_params['stage_params_list'])
                voutcm_stop = voutcm_start + num_amps - 1
                suffix_voutcm = f'<{voutcm_stop}:{voutcm_start}>' if num_amps > 1 else f'<{voutcm_start}>'
                suffix_voutcm_pin = f'<{num_amps - 1}:0>' if num_amps > 1 else ''
                voutcm_start = voutcm_start + num_amps

                # Getting instances and their connections
                inst_list.append(f'XCHAIN_AZ<{i}>')
                conn_dict = {'VDD': 'VDD',
                             'VSS': 'VSS',
                             'VINP': 'VSAMPP' if i == 0 else f'VMIDP<{i - 1}>',
                             'VINN': 'VSAMPN' if i == 0 else f'VMIDN<{i - 1}>',
                             'VOUTP': 'VOUTP' if i == num_az_chunks - 1 else f'VMIDP<{i}>',
                             'VOUTN': 'VOUTN' if i == num_az_chunks - 1 else f'VMIDN<{i}>',
                             'VREFP': f'VREFP<{i}>' if i==0 else f'VMIDP<{i-1}>',
                             'VREFN': f'VREFN<{i}>' if i==0 else f'VMIDN<{i-1}>',
                             f'VOUTCM{suffix_voutcm_pin}': f'VOUTCM{suffix_voutcm}',
                             'PHI': f'PHI<{i}>',
                             'PHIb': f'PHI<{i}>',
                             'PHI_EARLY': f'PHI_EARLY',
                             'PHI_EARLYb': f'PHI_EARLYb' }
                conn_dict_list.append(conn_dict)

            self.array_instance('XCHAIN_AZ', inst_list, conn_dict_list)

            for i in range(num_az_chunks):
                self.instances['XCHAIN_AZ'][i].design(**az_params)

            suffix_voutcm = f'<{voutcm_start - 1}:0>'
            self.rename_pin('VOUTCM', f'VOUTCM{suffix_voutcm}')

        else:
            az_params = az_params_list[0]
            self.instances['XCHAIN_AZ'].design(**az_params)
            num_amps = len(az_params['stage_params_list'])
            if num_amps > 1:
                voutcm_pin = f'VOUTCM<{num_amps - 1}:0>'
                self.reconnect_instance_terminal('XCHAIN_AZ', voutcm_pin, voutcm_pin)
                self.rename_pin('VOUTCM', voutcm_pin)

        ### Designing the diff-to-single amp with biasing
        single_params = params['single_params']
        constgm_params = params['constgm_params']
        inv_out = params['inv_out']

        single_in = single_params['in_type']

        self.instances['XSINGLE'].design(**single_params)
        self.instances['XCONSTGM'].design(res_side=single_in, **constgm_params)

        vgtail_pin = 'VP' if single_in == 'p' else 'VN'
        self.reconnect_instance_terminal('XCONSTGM', vgtail_pin, 'VGTAIL')

        if inv_out:
            self.reconnect_instance_terminal('XSINGLE', 'VINP', 'VOUTN')
            self.reconnect_instance_terminal('XSINGLE', 'VINN', 'VOUTP')
            self.rename_pin('OUT', 'OUTb')

