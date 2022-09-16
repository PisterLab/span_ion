# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_chain_trim(Module):
    """Module for library span_ion cell comparator_fd_chain_trim.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_chain_trim.yaml'))


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
            stage_params_list = 'List of comparator_fd_stage_trim parameters, in order',
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

        # Keeping track of indices
        idx_ibn_trim = 0
        idx_ibp_trim = 0
        idx_ibn_amp = 0
        idx_ibp_amp = 0
        idx_bb_up = 0
        idx_b_down = 0

        num_bb_up = sum([len(s['trim_p_params']['mirr_params']['seg_out_list']) for s in stage_params_list])
        num_b_down = sum([len(s['trim_n_params']['mirr_params']['seg_out_list']) for s in stage_params_list])

        ### Array stages and wire 'em up
        if num_stages > 1:
            conn_dict_list = []
            inst_list = []

            for i in range(num_stages):
                # The connections for a single stage
                conn_dict = dict(VDD='VDD',
                                 VSS='VSS',
                                 VINP='VINP' if i==0 else f'VMIDP<{i-1}>',
                                 VINN='VINN' if i==0 else f'VMIDN<{i-1}>',
                                 VOUTP='VOUTP' if i==num_stages-1 else f'VMIDP<{i}>',
                                 VOUTN='VOUTN' if i==num_stages-1 else f'VMIDN<{i}>')

                inst_list.append(f'XSTAGE<{i}>')

                stage_params = stage_params_list[i]
                has_trim_n = bool(stage_params['trim_n_params'])
                has_trim_p = bool(stage_params['trim_p_params'])
                amp_type = stage_params['amp_params']['in_type']

                # Amp biasing current
                if amp_type == 'n':
                    pin_ib_amp = 'IBN_AMP'
                    idx_ib_amp = idx_ibn_amp
                    idx_ibn_amp = idx_ibn_amp + 1
                else:
                    pin_ib_amp = 'IBP_AMP'
                    idx_ib_amp = idx_ibp_amp
                    idx_ibp_amp = idx_ibp_amp + 1
                conn_ib_amp = f'{pin_ib_amp}<{idx_ib_amp}>'
                conn_dict[pin_ib_amp] = conn_ib_amp

                # N-side trim
                if has_trim_n:
                    for n in ('IBN_TRIM', 'PULLDOWN_N', 'PULLDOWN_P'):
                        conn_dict[n] = f'{n}<{idx_ibn_trim}>'
                    idx_ibn_trim = idx_ibn_trim + 1

                    num_down_bits = len(stage_params['trim_n_params']['mirr_params']['seg_out_list'])
                    suffix_b_pin = '' if num_down_bits < 2 else f'<{num_down_bits-1}:0>'
                    suffix_b_conn = '' if num_b_down==1 else f'<{idx_b_down}>' if num_down_bits==1 else \
                        f'<{idx_b_down+num_down_bits-1}:{idx_b_down}>'
                    conn_dict[f'B_DOWN{suffix_b_pin}'] = f'B_DOWN{suffix_b_conn}'
                    idx_b_down = idx_b_down + num_down_bits

                # P-side trim
                if has_trim_p:
                    for n in ('Bb_UP', 'IBP_TRIM', 'PULLUPb_P', 'PULLUPb_N'):
                        conn_dict[n] = f'{n}<{idx_ibp_trim}>'
                    idx_ibp_trim = idx_ibp_trim + 1

                    num_up_bits = len(stage_params['trim_p_params']['mirr_params']['seg_out_list'])
                    suffix_bb_pin = '' if num_up_bits < 2 else f'<{num_up_bits - 1}:0>'
                    suffix_bb_conn = '' if num_bb_up==1 else f'<{idx_bb_up}>' if num_up_bits == 1 else \
                        f'<{idx_bb_up + num_up_bits - 1}:{idx_bb_up}>'
                    conn_dict[f'Bb_UP{suffix_bb_pin}'] = f'Bb_UP{suffix_bb_conn}'
                    idx_bb_up = idx_bb_up + num_up_bits

                conn_dict_list.append(conn_dict)

            self.array_instance('XSTAGE',
                                [f'XSTAGE<{i}>' for i in range(num_stages)],
                                conn_dict_list)
            for i in range(num_stages):
                self.instances['XSTAGE'][i].design(**stage_params)
        else:
            stage_params = stage_params_list[0]
            self.instances['XSTAGE'].design(**stage_params)
            has_trim_n = bool(stage_params['trim_n_params'])
            has_trim_p = bool(stage_params['trim_p_params'])
            amp_type = stage_params['amp_params']['in_type']

            if amp_type == 'p':
                self.reconnect_instance_terminal('XSTAGE', 'IBP_AMP', 'IBP_AMP')
                idx_ibp_amp = idx_ibp_amp + 1
            else:
                idx_ibn_amp = idx_ibn_amp + 1

            if has_trim_n:
                idx_ibn_trim = idx_ibn_trim + 1

            if has_trim_p:
                idx_ibp_trim = idx_ibp_trim + 1

        ### Renaming and removing pins as necessary
        pin_idx_map = dict(IBP_AMP=idx_ibp_amp,
                           IBN_AMP=idx_ibn_amp,
                           IBP_TRIM=idx_ibp_trim,
                           IBN_TRIM=idx_ibn_trim,
                           PULLUPb_P=idx_ibp_trim,
                           PULLUPb_N=idx_ibp_trim,
                           PULLDOWN_P=idx_ibn_trim,
                           PULLDOWN_N=idx_ibn_trim,
                           B_DOWN=idx_b_down,
                           Bb_UP=idx_bb_up)
        for pin, idx in pin_idx_map.items():
            if idx < 1:
                self.remove_pin(pin)
            elif idx > 1:
                self.rename_pin(pin, f'{pin}<{idx-1}:0>')