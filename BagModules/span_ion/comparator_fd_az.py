# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_az(Module):
    """Module for library span_ion cell comparator_fd_az.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_az.yaml'))


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
            az_params_list = 'List of comparator_fd_chain_az parameters'
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

        if num_az_chunks > 1:
            inst_list = []
            conn_dict_list = []
            
            voutcm_start = 0
            for i in range(num_az_chunks):
                # Getting indices of VOUTCM connection
                az_params = az_params_list[i]
                num_amps = len(az_params['stage_params_list'])
                suffix_voutcm = f'<{voutcm_start+num_amps-1}:{voutcm_start}>' if num_amps > 1 else f'<{voutcm_start}>'
                voutcm_start = voutcm_start + num_amps

                # Getting instances and their connections
                inst_list.append(f'XCHAIN_AZ<{i}>')
                conn_dict = {'VDD' : 'VDD',
                             'VSS' : 'VSS',
                             'VINP' : 'VINP' if i==0 else f'VMID<{i-1}>',
                             'VINN' : 'VINN' if i==0 else f'VMID<{i-1}>',
                             'VOUTP' : 'VOUTP' if i==num_az_chunks-1 else f'VMID<{i}>',
                             'VOUTN' : 'VOUTN' if i==num_az_chunks-1 else f'VMID<{i}>',
                             'VINCM' : f'VINCM<{i}>',
                             'VOUTCM' : f'VOUTCM<{suffix_voutcm}>',
                             'PHI' : f'PHI<{i}>',
                             'PHIb' : f'PHIb<{i}>',
                             'PHI_EARLY' : f'PHI_EARLY<{i}>',
                             'PHI_EARLYb' : f'PHI_EARLYb<{i}>'}
                conn_dict_list.append(conn_dict)

            self.array_instance('XCHAIN_AZ', inst_list, conn_dict_list)

            for i in range(num_az_chunks):
                self.instances['XCHAIN_AZ'][i].design(**az_params)

            suffix_voutcm = f'<{voutcm_start-1}:0>'
            suffix_chunks = f'<{num_az_chunks-1}:0>'
            self.rename_pin('VOUTCM', f'VOUTCM{suffix_voutcm}')
            for p in ['PHI', 'PHIb', 'PHI_EARLY', 'PHI_EARLYb', 'VINCM']:
                self.rename_pin(p, f'{p}{suffix_chunks}')

        else:
            az_params = az_params_list[0]
            self.instances['XCHAIN_AZ'].design(**az_params)
            num_amps = len(az_params['stage_params_list'])
            if num_amps > 1:
                voutcm_pin = f'VOUTCM<{num_amps-1}:0>'
                self.reconnect_instance_terminal('XCHAIN_AZ', voutcm_pin, voutcm_pin)
                self.rename_pin('VOUTCM', voutcm_pin)