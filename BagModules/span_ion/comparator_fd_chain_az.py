# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_chain_az(Module):
    """Module for library span_ion cell comparator_fd_chain_az.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_chain_az.yaml'))


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
            az_params = 'comparator_az_fb parameters',
            comp_params_list = 'List of compensation block parameters',
            comp_conn_list = 'List of where to connect two ends of compensation',
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
        az_params = params['az_params']
        stage_params_list = params['stage_params_list']
        comp_params_list = params['comp_params_list']
        comp_conn_list = params['comp_conn_list']

        ### Design instances
        self.instances['XAZ'].design(**az_params)

        # Array stages and rewire as necessary
        num_stages = len(stage_params_list)
        if num_stages > 1:
            conn_dict_list = []
            for i in range(num_stages):
                conn_dict = dict(VINP='VAMPINP' if i==0 else f'VMIDP<{i-1}>',
                                 VINN='VAMPINN' if i==0 else f'VMIDN<{i-1}>',
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

        # Array compensation elements and wire up
        assert len(comp_params_list) == len(comp_conn_list), f'comp_params and comp_conn lists should be same length'
        num_comp = len(comp_params_list)
        if num_comp > 0:
            compp_inst = [f'XCOMPP<{i}>' for i in range(num_comp)]
            compp_conn = [dict(VIN=comp_conn_list[i]['VIN'].replace('N', 'P'),
                               VOUT=comp_conn_list[i]['VOUT'].replace('P', 'N'),) for i in range(num_comp)]
            compn_inst = [f'XCOMPN<{i}>' for i in range(num_comp)]
            compn_conn = [dict(VIN=comp_conn_list[i]['VIN'].replace('P', 'N'),
                               VOUT=comp_conn_list[i]['VOUT'].replace('N', 'P'),) for i in range(num_comp)]
            self.array_instance('XCOMPP', compp_inst, compp_conn)
            self.array_instance('XCOMPN', compn_inst, compn_conn)

            for i in range(num_comp):
                self.instances['XCOMPP'][i].design(**(comp_params_list[i]))
                self.instances['XCOMPN'][i].design(**(comp_params_list[i]))
        else:
            self.delete_instance('XCOMPP')
            self.delete_instance('XCOMPN')
            # for suffix in ('P', 'N'):
            #     opp_suffix = 'N' if suffix == 'P' else 'P'
            #     inst_name = f'XCOMP{suffix}'
            #     self.instances[inst_name].design(**(comp_params_list[0]))
            #     self.reconnect_instance_terminal(inst_name, 'VIN', f'VIN{suffix}')
            #     self.reconnect_instance_terminal(inst_name, 'VOUT', f'VOUT{opp_suffix}')

        ### Adjusting pins
        # Remove unnecessary pins
        comp_sw_types = [comp_params['sw_params']['mos_type'] for comp_params in comp_params_list]
        az_sw_type = az_params['mos_type']
        az_has_n = az_sw_type != 'p'
        az_has_p = az_sw_type != 'n'
        comp_has_n = 'n' in comp_sw_types or 'both' in comp_sw_types
        comp_has_p = 'p' in comp_sw_types or 'both' in comp_sw_types

        has_n = az_has_n or comp_has_n
        has_p = az_has_p or comp_has_p

        if not has_n:
            self.remove_pin('PHI')

        if not has_p:
            self.remove_pin('PHIb')

        # # Rename pins as necessary
        # num_stages = len(stage_params_list)
        # if num_stages > 1:
        #     voutcm_pin = f'VOUTCM<{num_stages-1}:0>'
        #     self.reconnect_instance_terminal('XSTAGE', voutcm_pin, voutcm_pin)
        #     self.rename_pin('VOUTCM', voutcm_pin)