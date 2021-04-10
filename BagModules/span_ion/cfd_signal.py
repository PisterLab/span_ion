# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__cfd_signal(Module):
    """Module for library span_ion cell cfd_signal.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'cfd_signal.yaml'))


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
            preamp_params = 'Preamplifier parameters',
            delay_params = 'Delay line parameters',
            peak_params = 'Peak detector parameters',
            atten_params = 'Attenuator parameters',
            rdac_params = 'RDAC parameters',
            comp_zcd_params = 'ZCD comparator parameters',
            comp_led_params = 'LED comparator parameters',
            nor_params = 'Parameters for the NOR that follows the comparators',
            oneshot_params = 'One-shot parameters'   
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
        preamp_params = params['preamp_params']
        delay_params = params['delay_params']
        peak_params = params['peak_params']
        atten_params = params['atten_params'] # TODO attenuator
        rdac_params = params['rdac_params']
        comp_zcd_params = params['comp_zcd_params']
        comp_led_params = params['comp_led_params']
        nor_params = params['nor_params']
        oneshot_params = params['oneshot_params']

        ####################
        ### Preamplifier ###
        ####################
        self.instances['XPREAMP'].design(sw_params=dict(), **preamp_params)
        
        ##################
        ### Delay Line ###
        ##################
        self.instances['XDELAY'].design(**delay_params)

        chain_rdac = len(delay_params['unit_params_list'])
        if chain_rdac > 1:
            suffix_delay = f'<{chain_rdac-1}:0>'
            self.reconnect_instance_terminal('XDELAY', f'VREF{suffix_delay}', f'VREF_DELAY{suffix_delay}')
            self.rename_pin('VREF_DELAY', f'VREF_DELAY{suffix_delay}')

        #####################
        ### Peak Detector ###
        #####################
        self.instances['XPEAK'].design(**peak_params)
        
        ##################
        ### Attenuator ###
        ##################

        #####################
        ### Resistive DAC ###
        #####################
        self.instances['XRDAC'].design(**rdac_params)

        bits_rdac = rdac_params['num_bits']
        suffix_rdac = f'<{bits_rdac-1:0}>' if bits_rdac > 1 else ''
        self.reconnect_instance_terminal('XRDAC', f'S{suffix_rdac}', f'SEL_DAC{suffix_rdac}')
        if bits_rdac > 1:
            self.rename_pin('SEL_DAC', f'SEL_DAC{suffix_rdac}')

        ######################
        ### ZCD Comparator ###
        ######################
        self.instances['XCOMP_ZCD'].design(inv_out=True, **comp_zcd_params)

        self.reconnect_instance_terminal('XCOMP_ZCD', 'OUTb', 'OUTb_ZCD')
        chain_zcd = len(comp_zcd_params['az_params_list'])
        if chain_zcd > 1:
            suffix_zcd = f'<{chain_zcd-1}:0>'
            self.reconnect_instance_terminal('XCOMP_ZCD', f'VOUTCM{suffix_zcd}', f'VOUTCM_ZCD{suffix_zcd}')
            self.rename_pin('VOUTCM_ZCD', f'VOUTCM_ZCD{suffix_zcd}')

        # TODO autozeroing pins
        
        ######################
        ### LED Comparator ###
        ######################
        self.instances['XCOMP_LED'].design(inv_out=True, **comp_led_params)

        self.reconnect_instance_terminal('XCOMP_LED', 'OUTb', 'OUTb_LED')
        chain_led = len(comp_led_params['az_params_list'])
        if chain_led > 1:
            suffix_led = f'<{chain_led-1}:0>'
            self.reconnect_instance_terminal('XCOMP_LED', f'VOUTCM{suffix_led}', f'VOUTCM_LED{suffix_led}')
            self.rename_pin('VOUTCM_LED', f'VOUTCM_LED{suffix_led}')

        # TODO autozeroing pins

        #################
        ### Large NOR ###
        #################
        self.instances['XMEGANOR'].design(num_in=2, **nor_params)

        self.reconnect_instance_terminal('XMEGANOR', 'in<1:0>', 'OUTb_ZCD,OUTb_LED')

        ################################
        ### One-Shot Pulse Generator ###
        ################################
        self.instances['XONESHOT'].design(**oneshot_params)