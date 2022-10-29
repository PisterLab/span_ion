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
        stage_params_list = params['stage_params_list']
        single_params = params['single_params']

        in_single = single_params['in_type']
        num_amps = len(stage_params_list)

        ### Design instances
        self.instances['XCHAIN'].design(stage_params_list=stage_params_list)
        self.instances['XSINGLE'].design(**single_params)

        ### Reconnect and rename pins
        # Chain amps' current and voltage biasing
        num_ibn = sum([s['amp_params']['in_type'] == 'n' and s['amp_params']['has_diode'] for s in stage_params_list])
        num_ibp = sum([s['amp_params']['in_type'] == 'p' and s['amp_params']['has_diode'] for s in stage_params_list])
        num_vbn = sum([s['amp_params']['in_type'] == 'n' and not s['amp_params']['has_diode'] for s in stage_params_list])
        num_vbp = sum([s['amp_params']['in_type'] == 'p' and not s['amp_params']['has_diode'] for s in stage_params_list])

        bias_map = dict(IBN_AMP=num_ibn,
                        IBP_AMP=num_ibp,
                        VBN_AMP=num_vbn,
                        VBP_AMP=num_vbp)

        # DAC enables
        num_ibp_trim = sum([bool(s['trim_p_params']) for s in stage_params_list])
        num_ibn_trim = sum([bool(s['trim_n_params']) for s in stage_params_list])
        bias_map.update(dict(IBN_TRIM=num_ibn_trim,
                             IBP_TRIM=num_ibp_trim,
                             PULLUPb_N=num_ibp_trim,
                             PULLUPb_P=num_ibp_trim,
                             PULLDOWN_P=num_ibn_trim,
                             PULLDOWN_N=num_ibn_trim))

        # Trim DAC control bits
        num_bb_up = sum([len(s['trim_p_params']['mirr_params']['seg_out_list']) for s in stage_params_list])
        num_b_down = sum([len(s['trim_n_params']['mirr_params']['seg_out_list']) for s in stage_params_list])
        bias_map.update(dict(B_DOWN=num_b_down,
                             Bb_UP=num_bb_up))

        # Rename, reconnect, remove
        for pin_base, num_base in bias_map.items():
            if num_base > 1:
                self.reconnect_instance_terminal('XCHAIN', f'{pin_base}<{num_base-1}:0>', f'{pin_base}<{num_base-1}:0>')
                self.rename_pin(pin_base, f'{pin_base}<{num_base-1}:0>')
            elif num_base < 1:
                self.remove_pin(pin_base)

        # Single-ended amp biasing
        if in_single == 'p':
            self.remove_pin('IBN_SINGLE')
        else:
            self.remove_pin('IBP_SINGLE')