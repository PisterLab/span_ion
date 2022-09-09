# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_trim(Module):
    """Module for library span_ion cell comparator_trim.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_trim.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            trim_params = "key:value p/n:{dac_offset parameters}. If n or p are missing, that side of trim is removed.",
            stage_params_list = 'List of fully differential stage parameters',
            single_params = 'Single-ended amplifier parameters',
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
        trim_params = params['trim_params']
        stage_params_lst = params['stage_params_list']
        single_params = params['single_params']

        single_type = single_params['in_type']
        num_fd = len(stage_params_lst)

        ### Design instances
        # Single-ended stage
        self.instances['XSINGLE'].design(**single_params)

        # String of fully differential stages
        # VOUTP/N connect to the final fully differential output
        # Offset trim connects to the output of the first fully differential stage
        # Fix pins along the way
        if num_fd > 1:
            conn_lst = []
            idx_n = 0
            idx_p = 0

            for i, stage_params in enumerate(stage_params_lst):
                conn_inp = 'VINP' if i == 0 else f'VMIDP<{i-1}>'
                conn_inn = 'VINN' if i == 0 else f'VMIDN<{i-1}>'
                conn_outp = 'VOUTP' if i == num_fd-1 else f'VMIDP<{i}>'
                conn_outn = 'VOUTN' if i == num_fd - 1 else f'VMIDN<{i}>'

                if stage_params['in_type'] == 'n':
                    conn_bias = f'IBN<{idx_n}>'
                    idx_n = idx_n + 1
                    conn_bias_pin = 'IBN'
                elif stage_params['in_type'] == 'p':
                    conn_bias = f'IBP<{idx_p}>'
                    idx_p = idx_p + 1
                    conn_bias_pin = 'IBP'
                else:
                    raise ValueError(f'Unrecognized in_type for stage {i}')

                conn_lst.append({"VINP" : conn_inp,
                                 "VINN" : conn_inn,
                                 "VOUTP" : conn_outp,
                                 "VOUTN" : conn_outn,
                                 conn_bias_pin : conn_bias,
                                 "VDD" : 'VDD',
                                 "VSS" : 'VSS'})
            self.array_instance('XSTAGE', [f"XSTAGE<{i}>" for i in range(num_fd)], conn_lst)
            for i, stage_params in enumerate(stage_params_lst):
                self.instances['XSTAGE'][i].design(**stage_params)
        else:
            self.instances['XSTAGE'].desing(**(stage_params_lst[0]))

        if single_type == 'n':
            suffix_single = '' if idx_n == 0 else f'<{idx_n}>'
            self.reconnect_instance_terminal('XSINGLE', 'IBN', f'IBN{suffix_single}')
            idx_n = idx_n + 1
        if single_type == 'p':
            suffix_single = '' if idx_p == 0 else f'<{idx_p}>'
            self.reconnect_instance_terminal('XSINGLE', 'IBP', f'IBP{suffix_single}')
            idx_p = idx_p + 1

        suffix_ibn = '' if idx_n < 2 else f'<{idx_n-1}:0>'
        suffix_ibp = '' if idx_p < 2 else f'<{idx_p - 1}:0>'
        if idx_n == 0:
            self.remove_pin('IBN<1:0>')
        else:
            self.rename_pin('IBN<1:0>', f'IBN{suffix_ibn}')

        if idx_p == 0:
            self.remove_pin('IBP<1:0>')
        else:
            self.rename_pin('IBP<1:0>', f'IBP{suffix_ibp}')


        # Offset trim correction
        suffix_trim = '' if num_fd == 1 else '<0>'
        base_trim = 'MID' if num_fd > 1 else 'OUT'
        trim_n_params = trim_params.get('n', False)
        trim_p_params = trim_params.get('p', False)

        assert bool(trim_n_params) or bool(trim_p_params), 'Must include trimming DAC info for NMOS, PMOS, or both'

        if trim_n_params:
            self.instances['XTRIMN'].design(**trim_n_params, in_type='n')
            self.reconnect_instance_terminal('XTRIMN', 'VOUTA', f'V{base_trim}N{suffix_trim}')
            self.reconnect_instance_terminal('XTRIMN', 'VOUTB', f'V{base_trim}P{suffix_trim}')

            num_bits_n = len(trim_n_params['mirr_params']['seg_out_list'])
            if num_bits_n > 1:
                self.rename_pin('BN', f'BN<{num_bits_n-1}:0>')
                self.reconnect_instance_terminal('XTRIMN', f'B<{num_bits_n-1}:0>', f'BN<{num_bits_n-1}:0>')
        else:
            self.delete_instance('XTRIMN')
            self.remove_pin('BN')
            self.remove_pin('IREFN')
            self.remove_pin('PULLDOWN_N')
            self.remove_pin('PULLDOWN_P')

        if trim_p_params:
            self.instances['XTRIMP'].design(**trim_p_params, in_type='p')
            self.reconnect_instance_terminal('XTRIMP', 'VOUTA', f'V{base_trim}N{suffix_trim}')
            self.reconnect_instance_terminal('XTRIMP', 'VOUTB', f'V{base_trim}P{suffix_trim}')
            self.reconnect_instance_terminal('XTRIMP', 'PULLAb', 'PULLUPb_N')
            self.reconnect_instance_terminal('XTRIMP', 'PULLBb', 'PULLUPb_P')

            num_bits_p = len(trim_p_params['mirr_params']['seg_out_list'])
            if num_bits_p > 1:
                self.rename_pin('BPb', f'BPb<{num_bits_n-1}:0>')
                self.reconnect_instance_terminal('XTRIMP', f'Bb<{num_bits_p - 1}:0>', f'BPb<{num_bits_p - 1}:0>')
        else:
            self.delete_instance('XTRIMP')
            self.remove_pin('BPb')
            self.remove_pin('IREFP')
            self.remove_pin('PULLUPb_N')
            self.remove_pin('PULLUPb_P')