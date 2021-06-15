# -*- coding: utf-8 -*-

from typing import Dict

import os, warnings
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__one_shot_nand_tmr(Module):
    """Module for library span_ion cell one_shot_nand_tmr.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'one_shot_nand_tmr.yaml'))


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
            num_bits='Number of tuning bits for the resistor',
            has_rst='True/False to include a reset switch with associated logic',
            inv_in_params='Input inverter parameters',
            vote_inv_in_params = '',
            nand_params='NAND parameters',
            vote_nand_params = '',
            # vote_filt_params = '',
            nor_params='reset NOR parameters',
            vote_nor_params = '',
            rst_params='reset switch parameters',
            inv_chain_params='Inverter chain parameters',
            vote_outb_params = '',
            res_params='RC resistor parameters',
            cap_params='RC cap parameters'
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
        num_bits = params['num_bits']
        has_rst = params['has_rst']
        inv_in_params = params['inv_in_params']
        vote_inv_in_params = params['vote_inv_in_params']
        nand_params = params['nand_params']
        vote_nand_params = params['vote_nand_params']
        # vote_filt_params = params['vote_filt_params']
        inv_chain_params = params['inv_chain_params']
        vote_outb_params = params['vote_outb_params']
        res_params = params['res_params']
        cap_params = params['cap_params']
        nor_params = params['nor_params']
        vote_nor_params = params['vote_nor_params']
        rst_params = params['rst_params']

        inv_chain_length = len(inv_chain_params['inv_param_list'])

        assert inv_chain_length >= 2, f'Length of inverter chain {inv_chain_length} must be >= 2'

        ### Design instances
        # Resistor
        res_groupings = [2 ** i for i in range(num_bits)]
        sw_params = res_params['sw_params']
        sw_params['mos_type'] = 'n'
        res_params_copy = res_params.copy()
        res_params_copy.update(dict(sw_params=sw_params))

        self.instances['XR<0>'].design(res_groupings=res_groupings, **res_params_copy)
        self.instances['XR<1>'].design(res_groupings=res_groupings, **res_params_copy)
        self.instances['XR<2>'].design(res_groupings=res_groupings, **res_params_copy)

        # Removing instances which aren't necessary
        if not has_rst:
            for inst in ['XVOTE_NOR', 'XRST<2:0>'] + [f'XNOR<{i}>' for i in range(3)]:
                self.delete_instance(inst)

        # Most gates
        self.instances['XINV_IN<2:0>'].design(**inv_in_params)
        self.instances['XNAND<0>'].design(num_in=2, **nand_params)
        self.instances['XNAND<1>'].design(num_in=2, **nand_params)
        self.instances['XNAND<2>'].design(num_in=2, **nand_params)
        self.instances['XINV_OUT<2:0>'].design(dual_output=True, **inv_chain_params)
        if has_rst:
            self.instances['XNOR<0>'].design(num_in=3, **nor_params)
            self.instances['XNOR<1>'].design(num_in=3, **nor_params)
            self.instances['XNOR<2>'].design(num_in=3, **nor_params)
            self.instances['XRST<2:0>'].design(mos_type='n', **rst_params)

        # Voters
        self.instances['XVOTE_IN'].design(**vote_inv_in_params)
        self.instances['XVOTE_NAND'].design(**vote_nand_params)
        # self.instances['XVOTE_FILT'].design(**vote_filt_params)
        self.instances['XVOTE_OUTB'].design(**vote_outb_params)
        if has_rst:
            self.instances['XVOTE_NOR'].design(**vote_nor_params)

        # Capacitors
        warnings.warn('(one_shot_nand) check cap values generated correctly')
        self.instances['XCAP<2:0>'].parameters = cap_params

        ### Reconnect gates as necessary
        for i in range(3):
            self.reconnect_instance_terminal(f'XNAND<{i}>', 'in<1:0>', f'inb_vote<{i}>,outb_vote<{i}>')
            if has_rst:
                self.reconnect_instance_terminal(f'XNOR<{i}>', 'in<2:0>', f'in<{i}>,in_gate_vote<{i}>,out<{i}>')

        ### Adjusting control pins
        if num_bits < 1:
            self.remove_pin('CTRLb')
        elif num_bits > 1:
            suffix_bits = f'<{num_bits-1}:0>'
            self.rename_pin('CTRLb', f'CTRLb{suffix_bits}')
            self.reconnect_instance_terminal('XR<0>', f'CTRLb{suffix_bits}', f'CTRLb{suffix_bits}')
            self.reconnect_instance_terminal('XR<1>', f'CTRLb{suffix_bits}', f'CTRLb{suffix_bits}')
            self.reconnect_instance_terminal('XR<2>', f'CTRLb{suffix_bits}', f'CTRLb{suffix_bits}')