# -*- coding: utf-8 -*-

from typing import Dict, Mapping, Any

import os, sys
import pkg_resources

from bag.design.module import Module

# noinspection PyPep8Naming
class span_ion__zz_amp_folded_cascode(Module):
    """Module for library span_ion cell zz_amp_folded_cascode.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'zz_amp_folded_cascode.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str,Any]:
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            in_type = 'n or p for NMOS or PMOS input pair',
            diffpair_params = 'Diffpair parameters',
            cascode_params = 'cascode_conn parameters',
            diff_out = 'True for single-ended output, False for differential',
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

        # Design the amplifier
        self.instances['XAMP'].design(**params)

        # Modify load for a differential output if necessary
        diff_out = params['diff_out']
        if diff_out:
            self.array_instance('C_CLOAD', ['C_CLOADP', 'C_CLOADN'],
                                [dict(PLUS='VOUTP', MINUS='VSS'),
                                 dict(PLUS='VOUTN', MINUS='VSS')])

        # Determine which gate voltage sources aren't necessary
        cascode_params = params['cascode_params']
        n_stack = cascode_params['n_params']['stack']
        p_stack = cascode_params['p_params']['stack']
        n_drain_conn = cascode_params['n_drain_conn']
        p_drain_conn = cascode_params['p_drain_conn']

        vgn_inst_remove = [f'V_V{name}' for name in n_drain_conn if 'GN' in name]
        vgp_inst_remove = [f'V_V{name}' for name in p_drain_conn if 'GP' in name]
        vg_inst_remove = set(vgn_inst_remove + vgp_inst_remove)

        for vg_inst in vg_inst_remove:
            self.delete_instance(vg_inst)

        