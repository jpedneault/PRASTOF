# -------------------------Import-------------------------------------
# Load a local copy of the current ODYM branch:
import sys, os
import numpy as np
import pandas as pd

# Change the towards ODYM package.
# For more details on ODYM see DOI: 10.1111/jiec.12952
sys.path.append(r'C:\Users\julie\OneDrive - polymtl.ca\Phd_CIRAIG\4.Coeur\Codes\ODYM\ODYM-master\odym\modules')

import ODYM_Classes as msc  # import the ODYM class file
import ODYM_Functions as msf  # import the ODYM function file
import dynamic_stock_model as dsm  # import the dynamic stock model library

from scipy.stats import norm
from scipy.interpolate import make_interp_spline

import warnings
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)


# ----------------------------Class-----------------------------------

class Prastof:
    """
    PRASTOF (PRojection of Aluminium STOck and Flows) calculates aluminium alloys and alloying elements stock and flows
    up to 2100 with an sectorial approach and from the SSP framework and data.
    Projections calculation follows those main steps:
        1) Stock/capita per sector are calculated based on future service demand
        2) Scale to total stock based on population projections
        3) Inflows and outflows are then calculated using ODYM (Pauliuk et al;, 2019) DOI: 10.1111/jiec.12952
        4) Decomposition of the stock and flows per alloys and alloying element
    """

    # Initializer / Instance attributes
    def __init__(self, population, population_age, population_active, gdp, capacity, electricity, alu_content,
                 alloys_per_sector, elements_per_alloys, lifetime, BC_res_area, BC_com, CD_para, ME_para, EE_para,
                 PC_para, Trans_pkm, Trans_auto, Trans_auto_size, Trans_auto_type, Trans_tkm, Trans_freight, Trans_other):
        """Initialie all data needed for the dMFA

          Args:
         -----
            population: [df] Population according different region and SSP
            pop_act: [df] Share of the population working  according different region and SSP
            gdp: [df] GDP per capita  according different region and SSP
            capacity: [df] Electricity capacity per capita according different region and SSP and technology
            electricity: [df] Electricity consumption per capita according different region and SSP and technology
            alu_content: [df] Relative aluminium content according different product accprding 3 levels (low, medium, high)
            alloys_per_sector: [df] Share of alloys per different sector and products
            elements_per_alloys: [df] Alloying elements limits per alloys
            lifetime: [df] Average lifetimeof product
            BC_res_area: [df] Area projection for 2015, 2050,2060 and 2100  according to SSP and regions
            BC_com: [df] Parameter used to calculate area of commercial building
            CD_para: [df] Parameters used to calculate CD stock
            ME_para: [df] Parameters used to calculate ME stock
            EE_para: [df] Parameters used to calculate EE stock
            Trans_pkm: [df] Annual plm per capita according different region and SSP
            Trans_auto: [df] Vehicles parameter projection for 2015, 2050,2060 and 2100  according to SSP and regions
            Trans_auto_size: [df] Size of vehicles projection for 2015, 2050,2060 and 2100  according to SSP and regions
            Trans_auto_type: [df] Type of vehicles projection for 2015, 2050,2060 and 2100  according to SSP and regions
            Trans_tkm: [df] Annual tkm per capita according different region and SSP
            Trans_freight: [df] Freight parameter projection for 2015, 2050,2060 and 2100  according to SSP and regions
            Trans_other: [df] Parameter to calculate other transport stock
        """

        # Initial attributes
        self.population = population
        self.population_age = population_age
        self.gdp = gdp
        self.capacity = capacity
        self.electricity = electricity
        self.alu_content = alu_content
        self.alloys_per_sector = alloys_per_sector
        self.elements_per_alloys = elements_per_alloys
        self.lifetime = lifetime

        # Sector spectific attributes
        self.BC_res_area = BC_res_area
        self.BC_com = BC_com
        self.CD_para = CD_para
        self.ME_para = ME_para
        self.EE_para = EE_para
        self.PC_para = PC_para
        self.Trans_pkm = Trans_pkm
        self.Trans_auto = Trans_auto
        self.Trans_auto_size = Trans_auto_size
        self.Trans_auto_type = Trans_auto_type
        self.Trans_tkm = Trans_tkm
        self.Trans_freight = Trans_freight
        self.Trans_other = Trans_other

        # To calculate
        #Active populaton
        self.population_active = population_active
        # Building and construction
        self.BC_com_area = pd.DataFrame()
        self.s_BC_cap = pd.DataFrame()
        self.s_BC = pd.DataFrame()
        self.inf_BC = pd.DataFrame()
        self.out_BC = pd.DataFrame()
        # Transport
        self.Trans_veh = pd.DataFrame()
        self.s_Trans_cap = pd.DataFrame()
        self.s_Trans = pd.DataFrame()
        self.inf_Trans = pd.DataFrame()
        self.out_Trans = pd.DataFrame()
        # Machinery and equipment
        self.s_ME_cap = pd.DataFrame()
        self.s_ME = pd.DataFrame()
        self.inf_BC = pd.DataFrame()
        self.out_ME = pd.DataFrame()
        # Consumer durable
        self.s_CD_cap = pd.DataFrame()
        self.s_CD = pd.DataFrame()
        self.int_CD = pd.DataFrame()
        self.out_CD = pd.DataFrame()
        # Electricity engineering
        self.s_EE_cap = pd.DataFrame()
        self.s_EE = pd.DataFrame()
        self.s_EE_dist_cap = pd.DataFrame()
        self.s_EE_gen_cap = pd.DataFrame()
        self.inf_EE = pd.DataFrame()
        self.out_EE = pd.DataFrame()
        # Packaging and cans
        self.s_PC_cap = pd.DataFrame()
        self.s_PC = pd.DataFrame()
        self.inf_PC = pd.DataFrame()
        self.out_PC = pd.DataFrame()

        # Overall
        self.stock_cap = pd.DataFrame()
        self.stock = pd.DataFrame()
        self.inflow = pd.DataFrame()
        self.outflow = pd.DataFrame()

    @classmethod
    def from_template(cls, template_name):
        """
        Create the class based on all input data in a excel sheet
        Args:
        -----
        template_name : [string] name of the excel sheet with all input data
        """

        # Read excel

        # Population [cap]
        population = pd.read_excel(template_name, sheet_name='SSP_pop', index_col=[0, 1])
        population = projection(population, 1980)

        population_active = pd.DataFrame()
        # Population active [%]
        population_age = pd.read_excel(template_name, sheet_name='SSP_pop_age', index_col=[0, 1,2])

        for ssp in list(dict.fromkeys(population.index.get_level_values(level=0))):
            for reg in list(dict.fromkeys(population.index.get_level_values(level=1))):
                y = population_age.loc[ssp].loc[reg]
                pop_tot = y.sum()
                pop_act = y.loc[
                    ['Female_Aged20_24', 'Female_Aged25_29', 'Female_Aged30_34', 'Female_Aged35_39',
                     'Female_Aged40_44','Female_Aged45_49', 'Female_Aged50_54', 'Female_Aged55_59', 'Female_Aged60_64',
                     'Female_Aged65_69', 'Male_Aged20_24', 'Male_Aged25_29', 'Male_Aged30_34',
                     'Male_Aged35_39', 'Male_Aged40_44', 'Male_Aged45_49', 'Male_Aged50_54', 'Male_Aged55_59',
                     'Male_Aged60_64', 'Male_Aged65_69']].sum()
                active_proportion = pd.DataFrame(pop_act / pop_tot, columns=[reg]).T
                active_proportion = pd.concat([active_proportion], keys=[ssp])
                population_active = population_active.append(active_proportion)
        population_active = projection(population_active, 2015)

        # GDP [PPP/cap]
        gdp = pd.read_excel(template_name, sheet_name='SSP_GDP', index_col=[0, 1])
        gdp = projection(gdp, 1980).astype(float)

        # Electricity capacity [kW/cap]
        capacity = pd.read_excel(template_name, sheet_name='SSP_elec_capacity', index_col=[0, 1, 2])
        capacity = projection(capacity, 2015)

        # Electricity consumption [kWh/cap/y]
        electricity = pd.read_excel(template_name, sheet_name='SSP_elec', index_col=[0, 1, 2])
        electricity = projection(electricity, 2015)

        # Aluminium content [aluminium level (low, medium, high)]
        alu_content = pd.read_excel(template_name, sheet_name='Alu_content', index_col=[0, 1, 2]).drop(axis=1,
                                                                                                       columns='Reference')

        # Market share of different alloys per sector [%]
        alloys_per_sector = pd.read_excel(template_name, sheet_name='Alloys_sector', index_col=[0, 1, 2])

        # Alloying elements in alloys [%]
        elements_per_alloys = pd.read_excel(template_name, sheet_name='Element_alloys', index_col=[0]).drop(axis=1,
                                                                    columns='Reference').drop(axis=1, columns='Note')

        # Lifetime
        lifetime = pd.read_excel(template_name, sheet_name='Lifetime', index_col=[0, 1, 2, 3]).drop(axis=1,
                                                                                                    columns='Reference')

        # BC_res_area
        BC_res_area = pd.read_excel(template_name, sheet_name='BC_res_m2', index_col=[0, 1]).drop(axis=1, columns='Reference')
        BC_res_area = projection(BC_res_area, 2015)

        # BC_com
        BC_com = pd.read_excel(template_name, sheet_name='BC_com_para', index_col=[0])

        # ME_parameter
        ME_para = pd.read_excel(template_name, sheet_name='ME_para', index_col=[0])

        # CD_parament
        CD_para = pd.read_excel(template_name, sheet_name='CD_para', index_col=[0])

        # EE_Parameter
        EE_para = pd.read_excel(template_name, sheet_name='EE_dist_para', index_col=[0, 1])

        # PC_parameter
        PC_para = pd.read_excel(template_name, sheet_name='PC_para', index_col=[0,1])

        # Trans_pkm
        Trans_pkm = pd.read_excel(template_name, sheet_name='SSP_trans_pkm', index_col=[0, 1])
        Trans_pkm = projection(Trans_pkm, 2015)

        # Trans_auto
        Trans_auto = pd.read_excel(template_name, sheet_name='Trans_auto_veh', index_col=[0, 1, 2])
        Trans_auto = projection(Trans_auto, 2015)

        # Trans_auto_size
        Trans_auto_size = pd.read_excel(template_name, sheet_name='Trans_auto_size', index_col=[0, 1, 2])
        Trans_auto_size = projection(Trans_auto_size, 2015)

        # Trans_auto_type
        Trans_auto_type = pd.read_excel(template_name, sheet_name='Trans_auto_type', index_col=[0, 1, 2])
        Trans_auto_type = projection(Trans_auto_type, 2015)

        # Trans_freight_tkm
        Trans_tkm = pd.read_excel(template_name, sheet_name='SSP_trans_tkm', index_col=[0, 1])
        Trans_tkm = projection(Trans_tkm, 2015)

        # Trans_freight_para
        Trans_freight = pd.read_excel(template_name, sheet_name='Trans_freight_para', index_col=[0])

        # Trans_other
        Trans_other = pd.read_excel(template_name, sheet_name='Trans_other_para', index_col=[0])

        # create object
        dMFA = cls(population, population_age, population_active, gdp, capacity, electricity,alu_content,
                   alloys_per_sector, elements_per_alloys, lifetime, BC_res_area, BC_com, CD_para, ME_para, EE_para,
                   PC_para, Trans_pkm, Trans_auto, Trans_auto_size, Trans_auto_type, Trans_tkm, Trans_freight, Trans_other)
        return dMFA

    def solve(self):
        """ Solve all methods to calculate stock and flows of different sectors and concat all results into df.
         """
        # Calculate all sectors
        self._calc_BC()
        print('BC: done!')
        self._calc_Trans()
        print('Trans: done!')
        self._calc_EE()
        print('EE: done!')
        self._calc_ME()
        print('ME: done!')
        self._calc_CD()
        print('CD: done!')
        self._calc_PC()
        print('PC: done!')

        # Concat
        self._concat_sector()

    def _concat_sector(self):
        """ Concat and stock into df, different stock per cap, total stock, inflows and outflows per sector"""
        # Stock
        self.stock_cap = pd.concat([self.s_BC_cap, self.s_Trans_cap, self.s_EE_cap, self.s_ME_cap, self.s_CD_cap, self.s_PC_cap])
        self.stock = pd.concat([self.s_BC, self.s_Trans, self.s_EE, self.s_ME, self.s_CD, self.s_PC])
        # Inflow
        self.inflow = pd.concat([self.inf_BC, self.inf_Trans, self.inf_EE, self.inf_ME, self.inf_CD, self.inf_PC])
        # Outflow
        self.outflow = pd.concat([self.out_BC, self.out_Trans, self.out_EE, self.out_ME, self.out_CD, self.out_PC])

    def _calc_stock_BC_cap(self):
        """ Calculate the stock per capita related to "Building and construction" sector.
        The projections of stock/capita are divided into residential building and commercial building.
        Stock related to residentail building are calculated according projections of area/capita and aluminium intensity.
        Stock related to commercial building are calculated according the projection of area per service in employee sector.
        The proportion of employee n service sector is projected according to GDP evolution of countries
         """
        # Product 1 - Residential
        # Stock per capita
        BC_res_alu = self.alu_content.loc['BC', 'BC', 'Residential']

        # Aluminium stock in residential BC [kg Al / cap]
        s_BC_res = pd.DataFrame(np.kron(self.BC_res_area, BC_res_alu), index=self.BC_res_area.index,
                                columns=pd.MultiIndex.from_product([self.BC_res_area.columns, BC_res_alu.index])).stack(
            level=1)
        s_BC_res = pd.concat([s_BC_res], keys=['BC']).reorder_levels([1, 2, 3, 0])
        s_BC_res = pd.concat([s_BC_res], keys=['Residential']).reorder_levels([1, 2, 3, 4, 0])

        # Product 2 - Commercial
        # Parameters needed projections
        a_com_max = self.BC_com.loc['a_max']
        gamma = self.BC_com.loc['gamma']
        theta = self.BC_com.loc['theta']
        a = self.BC_com.loc['a']
        b = self.BC_com.loc['b']

        # Aluminium content in residential BC [kg / m^2]
        BC_com_alu = self.alu_content.loc['BC', 'BC', 'Commercial']

        # Area projection in commercial BC [m^2/employee in service sector]
        com_area = (1 / (1 + np.exp(self.gdp.loc(axis=1)[2015:2100].mul(theta, axis=0, level=1)).mul(gamma, axis=0, level=1))).mul(a_com_max,
                                                                                                            axis=0, level=1)
        # Proportion of service employees [%]
        com_y = np.log(self.gdp.loc(axis=1)[2015:2100]).mul(a, axis=0, level=1).add(b, axis=0, level=1)
        # Area projection in commercial BC [m^2/cap]
        self.BC_com_area = com_area * com_y * self.population_active

        # Aluminium stock in commercial BC [kg Al / cap]
        s_BC_com = pd.DataFrame(np.kron(self.BC_com_area, BC_com_alu), index=com_area.index,
                                columns=pd.MultiIndex.from_product([self.BC_com_area.columns, BC_com_alu.index])).stack(level=1)
        s_BC_com = pd.concat([s_BC_com], keys=['BC']).reorder_levels([1, 2, 3, 0])
        s_BC_com = pd.concat([s_BC_com], keys=['Commercial']).reorder_levels([1, 2, 3, 4, 0])

        # Concat different product
        self.s_BC_cap = pd.concat([s_BC_res, s_BC_com])
        self.s_BC_cap = pd.concat([self.s_BC_cap], keys=['BC']).reorder_levels([1, 2, 3, 0, 4, 5])

    def _calc_BC(self):
        """ Calculate the inflow, outflows and stock projection based on stock for the "Building and construction" sector
         """
        # Calculate stock BC per capita
        self._calc_stock_BC_cap()

        # Calculate total stock - BC
        self.s_BC = stock_total(self.s_BC_cap, self.population.loc(axis=1)[2015:2100])
        self.s_BC = self.s_BC.sort_index(level=[0, 1, 2])

        # Calculate inflow, outflow and stock - BC
        self.s_BC, self.inf_BC, self.out_BC = calculate_dMFA_sd(self.s_BC, self.lifetime)

        # Calculate global average per capita - BC
        self.s_BC_cap = calc_glo(self.s_BC_cap, self.population.loc(axis=1)[2015:2100])

        #Decompose into alloys and elements
        BC_alloys = self.alloys_per_sector.loc['BC', 'BC']

        self.s_BC_cap = alloys(self.s_BC_cap, BC_alloys)
        self.s_BC_cap = elements(self.s_BC_cap, self.elements_per_alloys)

        self.s_BC = alloys(self.s_BC, BC_alloys)
        self.s_BC = elements(self.s_BC, self.elements_per_alloys)

        self.inf_BC = alloys(self.inf_BC, BC_alloys)
        self.inf_BC = elements(self.inf_BC, self.elements_per_alloys)

        self.out_BC = alloys(self.out_BC, BC_alloys)
        self.out_BC = elements(self.out_BC, self.elements_per_alloys)

    def _calc_stock_Trans_cap(self):
        """ Calculate the stock per capita related to "Transport" sector.
        The projections of stock/capita are divided into automotive, freigth transport and others
         """
        # Product 1 - Automotive

        # Stock per capita
        Trans_auto_alu = self.alu_content.loc['Trans', 'Auto']

        # Number of car per cap
        self.Trans_veh = self.Trans_pkm / (self.Trans_auto.loc[:, :, 'VKM'] * self.Trans_auto.loc[:, :, 'OR'])

        # Index
        ssp = list(dict.fromkeys(self.Trans_veh.index.get_level_values(level=0)))
        reg = list(dict.fromkeys(self.Trans_veh.index.get_level_values(level=1)))
        typ = list(dict.fromkeys(self.Trans_auto_type.index.get_level_values(level=2)))
        siz = list(dict.fromkeys(self.Trans_auto_size.index.get_level_values(level=2)))

        # Caraterisation of car per type
        Trans_auto_t = pd.DataFrame(index=pd.MultiIndex.from_product([ssp, reg, typ]), columns=self.Trans_veh.columns)
        for ix in self.Trans_veh.index:
            Trans_auto_t.loc[ix] = self.Trans_auto_type.loc[ix].mul(self.Trans_veh.loc[ix]).values

        # Caraterisation of car per size
        size = pd.DataFrame()
        for i in range(0, len(typ)):
            size = size.append(self.Trans_auto_size)
        size = pd.DataFrame(size.values, index=pd.MultiIndex.from_product([typ, ssp, reg, siz]),
                            columns=size.columns).reorder_levels([1, 2, 0, 3])
        Trans_auto_t_s = pd.DataFrame(index=pd.MultiIndex.from_product([ssp, reg, typ, siz]), columns=self.Trans_veh.columns)

        for ix in Trans_auto_t.index:
            Trans_auto_t_s.loc[ix] = size.loc[ix].mul(Trans_auto_t.loc[ix]).values

        # Change index to combine type and size into one same index level
        muix = Trans_auto_t_s.index
        type_size = []
        for x in muix:
            z = x[2] + ' / ' + x[3]
            type_size.append(z)

        type_size = list(dict.fromkeys(type_size))
        muix2 = pd.MultiIndex.from_product([ssp, reg, type_size])
        Trans_auto_t_s.index = muix2

        # Aluminium stock in automotive
        s_Trans_auto = pd.DataFrame(index=Trans_auto_t_s.index,
                                    columns=pd.MultiIndex.from_product(
                                        (Trans_auto_t_s.columns, Trans_auto_alu.columns)))
        for s in ssp:
            for r in reg:
                for ts in type_size:
                    s_Trans_auto.loc[s, r, ts] = np.kron(Trans_auto_t_s.loc[s, r, ts], Trans_auto_alu.loc[ts])
        s_Trans_auto = s_Trans_auto.stack(level=1)
        s_Trans_auto = pd.concat([s_Trans_auto], keys=['Auto']).reorder_levels([1, 2, 4, 0, 3])

        # Product 2 - Freight
        # Read parameters
        d_freight = self.Trans_freight.loc['Market share']
        Trans_av_tkm_annual = self.Trans_freight.loc['tkm / year']
        Trans_freight_alu = self.alu_content.loc['Trans'].loc['Freight']
        mode = list(Trans_freight_alu.index)
        Trans_freight_a = self.alloys_per_sector.loc['Trans'].loc['Freight']

        # tkm per mode of transport
        Trans_tkm_m = pd.DataFrame(np.kron(self.Trans_tkm, d_freight), index=self.Trans_tkm.index,
                                   columns=pd.MultiIndex.from_product([self.Trans_tkm.columns, d_freight.index])).stack(
            level=1)

        # Number of vehicle needed to fulfill trasport freight needs
        Trans_tkm_m_v = Trans_tkm_m.div(Trans_av_tkm_annual, axis=0, level=2)

        # List of SSP and regions
        ssp = list(dict.fromkeys(self.Trans_tkm.index.get_level_values(level=0)))
        reg = list(dict.fromkeys(self.Trans_tkm.index.get_level_values(level=1)))

        # Stock of aluminium for freight sub sector
        s_Trans_freight = pd.DataFrame(index=Trans_tkm_m_v.index, columns=pd.MultiIndex.from_product(
            (Trans_tkm_m_v.columns, Trans_freight_alu.columns)))
        for s in ssp:
            for r in reg:
                for m in mode:
                    s_Trans_freight.loc[s, r, m] = np.kron(Trans_tkm_m_v.loc[s, r, m], Trans_freight_alu.loc[m])
        s_Trans_freight = s_Trans_freight.stack(level=1)
        s_Trans_freight = pd.concat([s_Trans_freight], keys=['Freight']).reorder_levels([1, 2, 4, 0, 3])

        # Product3 - Other

        # Read parameters
        s_Trans_o_max = self.Trans_other.loc['s_max']
        alpha_Trans_o = self.Trans_other.loc['alpha']
        beta_Trans_o = self.Trans_other.loc['beta']
        Trans_o_alloys = self.alloys_per_sector.loc['Trans', 'Trans']

        # Stock projection according to all aluminium levels
        s_Trans_o_low = s_Trans_o_max['Low'] * np.exp(
            -alpha_Trans_o['Low'] * np.exp(-beta_Trans_o['Low'] * self.gdp.loc(axis=1)[2015:2100]))
        s_Trans_o_low = pd.concat([s_Trans_o_low], keys=['Low'])
        s_Trans_o_med = s_Trans_o_max['Medium'] * np.exp(
            -alpha_Trans_o['Medium'] * np.exp(-beta_Trans_o['Medium'] * self.gdp.loc(axis=1)[2015:2100]))
        s_Trans_o_med = pd.concat([s_Trans_o_med], keys=['Medium'])
        s_Trans_o_high = s_Trans_o_max['High'] * np.exp(
            -alpha_Trans_o['High'] * np.exp(-beta_Trans_o['High'] * self.gdp.loc(axis=1)[2015:2100]))
        s_Trans_o_high = pd.concat([s_Trans_o_high], keys=['High'])
        # Concat all levels
        s_Trans_o = pd.concat([s_Trans_o_low, s_Trans_o_med, s_Trans_o_high])
        s_Trans_o = pd.concat([s_Trans_o], keys=['Trans'])
        s_Trans_o = pd.concat([s_Trans_o], keys=['Other']).reorder_levels([3, 4, 2, 1, 0])

        # Concat different product
        self.s_Trans_cap = pd.concat([s_Trans_auto, s_Trans_freight, s_Trans_o])
        self.s_Trans_cap = pd.concat([self.s_Trans_cap], keys=['Trans']).reorder_levels([1, 2, 3, 0, 4, 5])

    def _calc_Trans(self):

        # Calculate stock trans per capita
        self._calc_stock_Trans_cap()
        # Calculate total stock - trans
        self.s_Trans = stock_total(self.s_Trans_cap, self.population.loc(axis=1)[2015:2100])
        self.s_Trans = self.s_Trans.sort_index(level=[0, 1, 2])

        # Calculate inflow, outflow and stock - Trans
        self.s_Trans, self.inf_Trans, self.out_Trans = calculate_dMFA_sd(self.s_Trans, self.lifetime)

        # Calculate global average per capita - trans
        self.s_Trans_cap = calc_glo(self.s_Trans_cap, self.population.loc(axis=1)[2015:2100])

        # Decompose into alloys and elements
        s_Trans_cap = pd.DataFrame()
        for ss in list(dict.fromkeys(self.s_Trans_cap.index.get_level_values(4))):
            df_ss = self.s_Trans_cap.loc[:, :, :, 'Trans', ss, :]
            Trans_alloys_ss = self.alloys_per_sector.loc['Trans', ss]
            x = alloys(df_ss, Trans_alloys_ss)
            x = pd.concat([pd.concat([x], keys=[ss])], keys=['Trans']).reorder_levels([2, 3, 4, 0, 1, 5, 6])
            s_Trans_cap = s_Trans_cap.append(x)
        self.s_Trans_cap = elements(s_Trans_cap, self.elements_per_alloys)

        s_Trans = pd.DataFrame()
        for ss in list(dict.fromkeys(self.s_Trans.index.get_level_values(4))):
            df_ss = self.s_Trans.loc[:, :, :, 'Trans', ss, :]
            Trans_alloys_ss = self.alloys_per_sector.loc['Trans', ss]
            x = alloys(df_ss, Trans_alloys_ss)
            x = pd.concat([pd.concat([x], keys=[ss])], keys=['Trans']).reorder_levels([2, 3, 4, 0, 1, 5, 6])
            s_Trans = s_Trans.append(x)
        self.s_Trans = elements(s_Trans, self.elements_per_alloys)

        inf_Trans = pd.DataFrame()
        for ss in list(dict.fromkeys(self.inf_Trans.index.get_level_values(4))):
            df_ss = self.inf_Trans.loc[:, :, :, 'Trans', ss, :]
            Trans_alloys_ss = self.alloys_per_sector.loc['Trans', ss]
            x = alloys(df_ss, Trans_alloys_ss)
            x = pd.concat([pd.concat([x], keys=[ss])], keys=['Trans']).reorder_levels([2, 3, 4, 0, 1, 5, 6])
            inf_Trans = inf_Trans.append(x)
        self.inf_Trans = elements(inf_Trans, self.elements_per_alloys)

        out_Trans = pd.DataFrame()
        for ss in list(dict.fromkeys(self.out_Trans.index.get_level_values(4))):
            df_ss = self.out_Trans.loc[:, :, :, 'Trans', ss, :]
            Trans_alloys_ss = self.alloys_per_sector.loc['Trans', ss]
            x = alloys(df_ss, Trans_alloys_ss)
            x = pd.concat([pd.concat([x], keys=[ss])], keys=['Trans']).reorder_levels([2, 3, 4, 0, 1, 5, 6])
            out_Trans = out_Trans.append(x)
        self.out_Trans = elements(out_Trans, self.elements_per_alloys)

    def _calc_stock_EE_cap(self):
        """Calculate the stock per capita related to "Electrical engineering" sector.
        The projections of stock/capita are divided into electricity generation and electricity distribution
        Stocks projection are calculated from SSP's electricity projections
         """

        # Read alu content parameter
        EE_alu = self.alu_content.loc['EE']

        # Product 1 - Electricity generation
        # Read parameter
        EE_gen_alu = EE_alu.loc['Generation']

        # Calculate the stock according to the electrical capacity projection
        s_EE_gen_low = pd.concat([(self.capacity.mul(EE_gen_alu['Low'], axis=0, level=2))], keys=['Low'])
        s_EE_gen_med = pd.concat([(self.capacity.mul(EE_gen_alu['Medium'], axis=0, level=2))], keys=['Medium'])
        s_EE_gen_high = pd.concat([(self.capacity.mul(EE_gen_alu['High'], axis=0, level=2))], keys=['High'])
        s_EE_gen = pd.concat([s_EE_gen_low, s_EE_gen_med, s_EE_gen_high]).reorder_levels([1, 2, 0, 3])
        s_EE_gen = pd.concat([s_EE_gen], keys=['Generation']).reorder_levels([1, 2, 3, 0, 4])


        # Product 2 - Distribution
        # Read parameters
        EE_dist_alu = EE_alu.loc['Distribution']
        EE_dist_para = self.EE_para.loc['dist']

        # Calcualte the total electricity consumption per region and per SSP
        elec_sum = self.electricity.sum(axis=0, level=[0, 1])

        # Calculate the stock of aluminium intensity per kWh
        al_int_kWh = EE_dist_alu.mul((EE_dist_para['km/kWh'] * EE_dist_para['lifetime']), axis=0)

        # Calculate the stock per capita for different levels
        s_EE_dist_low = pd.DataFrame(np.kron(elec_sum, al_int_kWh['Low']), index=elec_sum.index,
                                     columns=pd.MultiIndex.from_product(
                                         [elec_sum.columns, list(al_int_kWh['Low'].index)])).stack(level=1)
        s_EE_dist_low = pd.concat([s_EE_dist_low], keys=['Low']).reorder_levels([1, 2, 0, 3])

        s_EE_dist_med = pd.DataFrame(np.kron(elec_sum, al_int_kWh['Medium']), index=elec_sum.index,
                                     columns=pd.MultiIndex.from_product(
                                         [elec_sum.columns, list(al_int_kWh['Medium'].index)])).stack(level=1)
        s_EE_dist_med = pd.concat([s_EE_dist_med], keys=['Medium']).reorder_levels([1, 2, 0, 3])

        s_EE_dist_high = pd.DataFrame(np.kron(elec_sum, al_int_kWh['High']), index=elec_sum.index,
                                      columns=pd.MultiIndex.from_product(
                                          [elec_sum.columns, list(al_int_kWh['High'].index)])).stack(level=1)
        s_EE_dist_high = pd.concat([s_EE_dist_high], keys=['High']).reorder_levels([1, 2, 0, 3])

        s_EE_dist = pd.concat([s_EE_dist_low, s_EE_dist_med, s_EE_dist_high])
        s_EE_dist = pd.concat([s_EE_dist], keys=['Distribution']).reorder_levels([1, 2, 3, 0, 4])

        # Concat different product
        self.s_EE_cap = pd.concat([s_EE_gen, s_EE_dist])
        self.s_EE_cap = pd.concat([self.s_EE_cap], keys=['EE']).reorder_levels([1, 2, 3, 0, 4, 5])

    def _calc_EE(self):

        # Calculate stock EE per capita
        self._calc_stock_EE_cap()
        # Calculate total stock - EE
        self.s_EE = stock_total(self.s_EE_cap, self.population.loc(axis=1)[2015:2100])
        self.s_EE = self.s_EE.sort_index(level=[0, 1, 2])

        # Calculate inflow, outflow and stock - EE
        self.s_EE, self.inf_EE, self.out_EE = calculate_dMFA_sd(self.s_EE, self.lifetime)

        # Calculate global average per capita - EE
        self.s_EE_cap = calc_glo(self.s_EE_cap, self.population.loc(axis=1)[2015:2100])

        # Decompose into alloys and elements

        s_EE_cap = pd.DataFrame()
        for ss in list(dict.fromkeys(self.s_EE_cap.index.get_level_values(4))):
            df_ss = self.s_EE_cap.loc[:, :, :, 'EE', ss, :]
            EE_alloys_ss = self.alloys_per_sector.loc['EE', ss]
            x = alloys(df_ss, EE_alloys_ss)
            x = pd.concat([pd.concat([x], keys=[ss])], keys=['EE']).reorder_levels([2, 3, 4, 0, 1, 5, 6])
            s_EE_cap = s_EE_cap.append(x)
        self.s_EE_cap = elements(s_EE_cap, self.elements_per_alloys)

        s_EE = pd.DataFrame()
        for ss in list(dict.fromkeys(self.s_EE.index.get_level_values(4))):
            df_ss = self.s_EE.loc[:, :, :, 'EE', ss, :]
            EE_alloys_ss = self.alloys_per_sector.loc['EE', ss]
            x = alloys(df_ss, EE_alloys_ss)
            x = pd.concat([pd.concat([x], keys=[ss])], keys=['EE']).reorder_levels([2, 3, 4, 0, 1, 5, 6])
            s_EE = s_EE.append(x)
        self.s_EE = elements(s_EE, self.elements_per_alloys)

        inf_EE = pd.DataFrame()
        for ss in list(dict.fromkeys(self.inf_EE.index.get_level_values(4))):
            df_ss = self.inf_EE.loc[:, :, :, 'EE', ss, :]
            EE_alloys_ss = self.alloys_per_sector.loc['EE', ss]
            x = alloys(df_ss, EE_alloys_ss)
            x = pd.concat([pd.concat([x], keys=[ss])], keys=['EE']).reorder_levels([2, 3, 4, 0, 1, 5, 6])
            inf_EE = inf_EE.append(x)
        self.inf_EE = elements(inf_EE, self.elements_per_alloys)

        out_EE = pd.DataFrame()
        for ss in list(dict.fromkeys(self.out_EE.index.get_level_values(4))):
            df_ss = self.out_EE.loc[:, :, :, 'EE', ss, :]
            EE_alloys_ss = self.alloys_per_sector.loc['EE', ss]
            x = alloys(df_ss, EE_alloys_ss)
            x = pd.concat([pd.concat([x], keys=[ss])], keys=['EE']).reorder_levels([2, 3, 4, 0, 1, 5, 6])
            out_EE = out_EE.append(x)
        self.out_EE = elements(out_EE, self.elements_per_alloys)

    def _calc_stock_ME_cap(self):
        """ Calculate the stock per capita related to Machinery and equipement sector.
        The projections of stock/capita are based on a Gompertz function.
         """

        # Read parameters
        s_ME_max = self.ME_para.loc['s_max']
        alpha_ME = self.ME_para.loc['alpha']
        beta_ME = self.ME_para.loc['beta']

        # Calculate the projection based on Gompertz function for different aluminium level
        s_ME_low = s_ME_max['Low'] * np.exp(-alpha_ME['Low'] * np.exp(-beta_ME['Low'] * self.gdp.loc(axis=1)[2015:2100]))
        s_ME_low = pd.concat([s_ME_low], keys=['Low'])
        s_ME_med = s_ME_max['Medium'] * np.exp(-alpha_ME['Medium'] * np.exp(-beta_ME['Medium'] * self.gdp.loc(axis=1)[2015:2100]))
        s_ME_med = pd.concat([s_ME_med], keys=['Medium'])
        s_ME_high = s_ME_max['High'] * np.exp(-alpha_ME['High'] * np.exp(-beta_ME['High'] * self.gdp.loc(axis=1)[2015:2100]))
        s_ME_high = pd.concat([s_ME_high], keys=['High'])

        # Concat three levels into a one dataframe
        s_ME = pd.concat([s_ME_low, s_ME_med, s_ME_high]).reorder_levels([1, 2, 0])
        s_ME = pd.concat([s_ME], keys=['ME']).reorder_levels([1, 2, 3, 0])

        # Stock per capita
        self.s_ME_cap = pd.concat([s_ME], keys=['ME']).reorder_levels([1, 2, 3, 0, 4])
        self.s_ME_cap = pd.concat([self.s_ME_cap], keys=['ME']).reorder_levels([1, 2, 3, 4, 0, 5])

    def _calc_ME(self):
        """ Calculate the inflow, outflows and stock projection based on stock for the "Machinery and equipment" sector
         """
        # Calculate stock ME per capita
        self._calc_stock_ME_cap()

        # Calculate total stock - ME
        self.s_ME = stock_total(self.s_ME_cap, self.population.loc(axis=1)[2015:2100])
        self.s_ME = self.s_ME.sort_index(level=[0, 1,2])

        # Calculate inflow, outflow and stock
        self.s_ME, self.inf_ME, self.out_ME = calculate_dMFA_sd(self.s_ME, self.lifetime)

        # Calculate global average per capita - ME
        self.s_ME_cap = calc_glo(self.s_ME_cap, self.population.loc(axis=1)[2015:2100])

        # Decompose into alloys and elements
        ME_alloys = self.alloys_per_sector.loc['ME', 'ME']

        self.s_ME_cap = alloys(self.s_ME_cap, ME_alloys)
        self.s_ME_cap = elements(self.s_ME_cap, self.elements_per_alloys)

        self.s_ME = alloys(self.s_ME, ME_alloys)
        self.s_ME = elements(self.s_ME, self.elements_per_alloys)

        self.inf_ME = alloys(self.inf_ME, ME_alloys)
        self.inf_ME = elements(self.inf_ME, self.elements_per_alloys)

        self.out_ME = alloys(self.out_ME, ME_alloys)
        self.out_ME = elements(self.out_ME, self.elements_per_alloys)

    def _calc_stock_CD_cap(self):
        """ Calculate the stock per capita related to "consumer durable" sector.
        The projections of stock/capita are based on a Gompertz function.
         """

        # Read parameters
        s_CD_max = self.CD_para.loc['s_max']
        alpha_CD = self.CD_para.loc['alpha']
        beta_CD = self.CD_para.loc['beta']

        # Calculate the projection based on Gompertz function for different aluminium level
        s_CD_low = s_CD_max['Low'] * np.exp(-alpha_CD['Low'] * np.exp(-beta_CD['Low'] * self.gdp.loc(axis=1)[2015:2100]))
        s_CD_low = pd.concat([s_CD_low], keys=['Low'])
        s_CD_med = s_CD_max['Medium'] * np.exp(-alpha_CD['Medium'] * np.exp(-beta_CD['Medium'] * self.gdp.loc(axis=1)[2015:2100]))
        s_CD_med = pd.concat([s_CD_med], keys=['Medium'])
        s_CD_high = s_CD_max['High'] * np.exp(-alpha_CD['High'] * np.exp(-beta_CD['High'] * self.gdp.loc(axis=1)[2015:2100]))
        s_CD_high = pd.concat([s_CD_high], keys=['High'])

        s_CD = pd.concat([s_CD_low, s_CD_med, s_CD_high]).reorder_levels([1, 2, 0]).sort_index(level=[0, 1])
        s_CD = pd.concat([s_CD], keys=['CD']).reorder_levels([1, 2, 3, 0])

        # Stock per capita
        self.s_CD_cap = pd.concat([s_CD], keys=['CD']).reorder_levels([1, 2, 3, 0, 4])
        self.s_CD_cap = pd.concat([self.s_CD_cap], keys=['CD']).reorder_levels([1, 2, 3, 4, 0, 5])

        # Stock total
        self.s_CD = stock_total(self.s_CD_cap, self.population.loc(axis=1)[2015:2100])

    def _calc_CD(self):
        """ Calculate the inflow, outflows and stock projection based on stock for the "consumer durable" sector
         """
        # Calculate stock CD per capita
        self._calc_stock_CD_cap()
        # Calculate total stock - CD
        self.s_CD = stock_total(self.s_CD_cap, self.population.loc(axis=1)[2015:2100])
        # Calculate inflow, outflow and stock - CD
        self.s_CD, self.inf_CD, self.out_CD = calculate_dMFA_sd(self.s_CD, self.lifetime)

        # Calculate global average per capita - CD
        self.s_CD_cap = calc_glo(self.s_CD_cap, self.population.loc(axis=1)[2015:2100])

        # Decompose into alloys and elements
        CD_alloys = self.alloys_per_sector.loc['CD', 'CD']

        self.s_CD_cap = alloys(self.s_CD_cap, CD_alloys)
        self.s_CD_cap = elements(self.s_CD_cap, self.elements_per_alloys)

        self.s_CD = alloys(self.s_CD, CD_alloys)
        self.s_CD = elements(self.s_CD, self.elements_per_alloys)

        self.inf_CD = alloys(self.inf_CD, CD_alloys)
        self.inf_CD = elements(self.inf_CD, self.elements_per_alloys)

        self.out_CD = alloys(self.out_CD, CD_alloys)
        self.out_CD = elements(self.out_CD, self.elements_per_alloys)

    def _calc_inf_PC(self):
        """ Calculate the inflow per capita for the Packaging and cans (PC) sector.
        The sector is split into 2 sub sectors: cans and other packaging
        The projections of inflow/capita are based on a Gompertz function.
         """
        #Cans
        inf_PC_max_cans = self.PC_para.loc['Cans','inf_max']
        alpha_PC_cans = self.PC_para.loc['Cans','alpha']
        beta_PC_cans = self.PC_para.loc['Cans','beta']

        inf_PC_low_cans = inf_PC_max_cans['Low'] * np.exp(-alpha_PC_cans['Low'] * np.exp(-beta_PC_cans['Low'] * self.gdp))
        inf_PC_med_cans = inf_PC_max_cans['Medium'] * np.exp(-alpha_PC_cans['Medium'] * np.exp(-beta_PC_cans['Medium'] * self.gdp))
        inf_PC_high_cans = inf_PC_max_cans['High'] * np.exp(-alpha_PC_cans['High'] * np.exp(-beta_PC_cans['High'] * self.gdp))

        inf_PC_low_cans = pd.concat([inf_PC_low_cans], keys=['Low'])
        inf_PC_med_cans = pd.concat([inf_PC_med_cans], keys=['Medium'])
        inf_PC_high_cans = pd.concat([inf_PC_high_cans], keys=['High'])
        inf_PC_cans = pd.concat([inf_PC_low_cans, inf_PC_med_cans, inf_PC_high_cans]).reorder_levels([1, 2, 0]).sort_index(level=[0, 1])
        inf_PC_cans = pd.concat([inf_PC_cans], keys=['Cans']).reorder_levels([1, 2, 3, 0])
        inf_PC_cans = pd.concat([inf_PC_cans], keys=['Cans']).reorder_levels([1, 2, 3, 0, 4])
        #Other
        inf_PC_max_oth = self.PC_para.loc['Other','inf_max']
        alpha_PC_oth = self.PC_para.loc['Other','alpha']
        beta_PC_oth = self.PC_para.loc['Other','beta']

        inf_PC_low_oth = inf_PC_max_oth['Low'] * np.exp(-alpha_PC_oth['Low'] * np.exp(-beta_PC_oth['Low'] * self.gdp))
        inf_PC_med_oth = inf_PC_max_oth['Medium'] * np.exp(-alpha_PC_oth['Medium'] * np.exp(-beta_PC_oth['Medium'] * self.gdp))
        inf_PC_high_oth = inf_PC_max_oth['High'] * np.exp(-alpha_PC_oth['High'] * np.exp(-beta_PC_oth['High'] * self.gdp))

        inf_PC_low_oth = pd.concat([inf_PC_low_oth], keys=['Low'])
        inf_PC_med_oth = pd.concat([inf_PC_med_oth], keys=['Medium'])
        inf_PC_high_oth = pd.concat([inf_PC_high_oth], keys=['High'])
        inf_PC_oth = pd.concat([inf_PC_low_oth, inf_PC_med_oth, inf_PC_high_oth]).reorder_levels([1, 2, 0]).sort_index(level=[0, 1])
        inf_PC_oth = pd.concat([inf_PC_oth], keys=['Other']).reorder_levels([1, 2, 3, 0])
        inf_PC_oth = pd.concat([inf_PC_oth], keys=['Other']).reorder_levels([1, 2, 3, 0, 4])
        # Inflow per capita
        self.inf_PC_cap = pd.concat([inf_PC_cans, inf_PC_oth])
        self.inf_PC_cap = pd.concat([self.inf_PC_cap], keys=['PC']).reorder_levels([1, 2, 3, 0, 4, 5])

    def _calc_PC(self):
        """ Calculate the inflow, outflows and stock projection based on inflows for the "packaging and cans" sector"""

        # --- PC ---
        # Calculate inflow PC per capita
        self._calc_inf_PC()

        # Calculate inflow total

        self.inf_PC = stock_total(self.inf_PC_cap, self.population)

        self.inf_PC_cap = self.inf_PC_cap.loc(axis=1)[2015:2100]

        # Calculate stock dynamic cans
        self.s_PC, self.out_PC = calculate_dMFA_id(self.inf_PC, self.lifetime)

        # Stock capita
        PC_stock = self.s_PC.sum(level=[0, 1, 2, 3, 4, 5])
        self.s_PC_cap = pd.DataFrame()
        for ssp in list(dict.fromkeys(self.population.index.get_level_values(0))):
            s_PC_cap_temp = PC_stock.loc[ssp].div(self.population.loc[ssp], axis=0, level=0)*1000
            s_PC_cap_temp = pd.concat([s_PC_cap_temp], keys=[ssp])
            self.s_PC_cap = self.s_PC_cap.append(s_PC_cap_temp)

        # Calculate GLO average
        self.s_PC_cap = calc_glo(self.s_PC_cap, self.population)



        # Decompose into alloys and elements
        PC_alloys = self.alloys_per_sector.loc['PC']

        self.s_PC_cap = alloys(self.s_PC_cap, PC_alloys)
        self.s_PC_cap = elements(self.s_PC_cap, self.elements_per_alloys)

        self.s_PC = alloys(self.s_PC, PC_alloys)
        self.s_PC = elements(self.s_PC, self.elements_per_alloys)

        self.inf_PC = self.inf_PC.loc(axis=1)[2015:2100]
        self.inf_PC = alloys(self.inf_PC, PC_alloys)
        self.inf_PC = elements(self.inf_PC, self.elements_per_alloys)

        self.out_PC = alloys(self.out_PC, PC_alloys)
        self.out_PC = elements(self.out_PC, self.elements_per_alloys)

def calculate_dMFA_sd(stock, lifetime):
    '''Calculate the dMFA with a stock-driven approach building according to a stock evolution and the lifetime of
    products ODYM'''
    
    # Create empty dataframe
    stock_sector = pd.DataFrame()
    inflow_sector = pd.DataFrame()
    outflow_sector = pd.DataFrame()

    # Calculate for every sector and sub-sector
    for sector in list(dict.fromkeys(stock.index.get_level_values(3))):
        for sub_sector in list(dict.fromkeys(stock.index.get_level_values(4))):

            # Calculate stock, inflow and outflow with ODYM
            stock_ODYM, inflow_ODYM, outflow_ODYM = dMFA_ODYM_sd(stock, lifetime, sector, sub_sector, 115)

            # Add index for stock df
            stock_ODYM = pd.concat([stock_ODYM], keys=[sub_sector])
            stock_ODYM = pd.concat([stock_ODYM], keys=[sector]).reorder_levels([2, 3, 4, 0, 1, 5])
            stock_sector = stock_sector.append(stock_ODYM)

            # Add index for inflow df
            inflow_ODYM = pd.concat([inflow_ODYM], keys=[sub_sector])
            inflow_ODYM = pd.concat([inflow_ODYM], keys=[sector]).reorder_levels([2, 3, 4, 0, 1, 5])
            inflow_sector = inflow_sector.append(inflow_ODYM)

            # Add index for outflow df
            outflow_ODYM = pd.concat([outflow_ODYM], keys=[sub_sector])
            outflow_ODYM = pd.concat([outflow_ODYM], keys=[sector]).reorder_levels([2, 3, 4, 0, 1, 5])
            outflow_sector = outflow_sector.append(outflow_ODYM)

    return (stock_sector, inflow_sector, outflow_sector)

def calculate_dMFA_id(inflow, lifetime):
    '''Calculate the dMFA with a inflow-driven approach building according to an inflow evolution and the lifetime of
    products ODYM'''
    # Create empty dataframe
    stock_sector = pd.DataFrame()
    inflow_sector = pd.DataFrame()
    outflow_sector = pd.DataFrame()

    # Calculate for every sector and sub-sector
    for sector in list(dict.fromkeys(inflow.index.get_level_values(3))):
        for sub_sector in list(dict.fromkeys(inflow.index.get_level_values(4))):

            # Calculate stock, inflow and outflow with ODYM
            stock_ODYM, outflow_ODYM = dMFA_ODYM_id(inflow, lifetime, sector, sub_sector)

            # Add index for stock df
            stock_ODYM = pd.concat([stock_ODYM], keys=[sub_sector])
            stock_ODYM = pd.concat([stock_ODYM], keys=[sector]).reorder_levels([2, 3, 4, 0, 1, 5])
            stock_sector = stock_sector.append(stock_ODYM)

            # Add index for outflow df
            outflow_ODYM = pd.concat([outflow_ODYM], keys=[sub_sector])
            outflow_ODYM = pd.concat([outflow_ODYM], keys=[sector]).reorder_levels([2, 3, 4, 0, 1, 5])
            outflow_sector = outflow_sector.append(outflow_ODYM)

    return (stock_sector, outflow_sector)

def dMFA_ODYM_sd(stock, lifetime, sector, sub_sector, switchtime):
    ''' Calculate dMFA with a stock driven approach using ODYM framework
    '''

    stock = stock.loc[:, :, :, sector, sub_sector]
    lifetime = lifetime.loc[:, sector, sub_sector, :]

    ##Define MFA system
    ModelClassification = {}  # Create dictionary of model classifications

    MyScenario = list(dict.fromkeys(stock.index.get_level_values(0)))
    ModelClassification['Scenario'] = msc.Classification(Name='Scenario', Dimension='Scenario', ID=1, Items=MyScenario)

    MyYears = list(np.arange(1900, 2015, 1)) + list(stock.columns)
    ModelClassification['Time'] = msc.Classification(Name='Time', Dimension='Time', ID=2,
                                                     Items=MyYears)
    # Classification for time labelled 'Time' must always be present,
    #  with Items containing a list of odered integers representing years, months, or other discrete time intervals

    ModelClassification['Cohort'] = msc.Classification(Name='Age-cohort', Dimension='Time', ID=3, Items=MyYears)
    # Classification for cohort is used to track age-cohorts in the stock.

    MyRegions = list(dict.fromkeys(stock.index.get_level_values(1)))
    ModelClassification['Region'] = msc.Classification(Name='Region', Dimension='Region', ID=4, Items=MyRegions)
    # Classification for regions is chosen to include the regions that are in the scope of this analysis.

    MyLevels = list(dict.fromkeys(stock.index.get_level_values(2)))
    ModelClassification['Level'] = msc.Classification(Name='Level', Dimension='Level', ID=5, Items=MyLevels)
    # Classification for level represent 3 levels of aluminium content

    MyProducts = list(dict.fromkeys(stock.index.get_level_values(3)))
    ModelClassification['Product'] = msc.Classification(Name='Product', Dimension='Product', ID=6, Items=MyProducts)
    # Classification for product is chosen to include the products that are in the scope of this analysis.

    MyElements = ['Aluminium']
    ModelClassification['Element'] = msc.Classification(Name='Elements', Dimension='Elements', ID=7, Items=MyElements)
    # Classification for elements labelled 'Element' must always be present,
    #  with Items containing a list of the symbols of the elements covered.

    # Get model time start, end, and duration:
    Model_Time_Start = int(min(ModelClassification['Time'].Items))
    Model_Time_End = int(max(ModelClassification['Time'].Items))
    Model_Duration = (Model_Time_End - Model_Time_Start)

    # That dictionary of classifications enteres the index table defined for the system.
    # The indext table lists all aspects needed and assigns a classification and index letter to each aspect.

    IndexTable = pd.DataFrame(
        {'Aspect': ['Scenario', 'Time', 'Age-cohort', 'Region', 'Level', 'Product', 'Element'],
         # 'Time' and 'Element' must be present!
         'Description': ['Model aspect "Scenario"', 'Model aspect "time"', 'Model aspect "age-cohort"',
                         'Model aspect "Region where flow occurs"', 'Model aspect "Level of al content"',
                         'Model aspect "Product"', 'Model aspect "Element"'],
         'Dimension': ['Scenario', 'Time', 'Time', 'Region', 'Level', 'Product', 'Elements'],
         # 'Time' and 'Element' are also dimensions
         'Classification': [ModelClassification[Aspect] for Aspect in
                            ['Scenario', 'Time', 'Cohort', 'Region', 'Level', 'Product','Element']],
         'IndexLetter': ['s', 't', 'c', 'r', 'l', 'p', 'e']})  # Unique one letter (upper or lower case) indices to be used later for calculations.

    IndexTable.set_index('Aspect',
                         inplace=True)  # Default indexing of IndexTable, other indices are produced on the fly

    # We can now define our MFA system:

    Dyn_MFA_System = msc.MFAsystem(Name='AluminiumStockDynamic',
                                   Geogr_Scope='5SelectedRegions',
                                   Unit='Mt',
                                   ProcessList=[],
                                   FlowDict={},
                                   StockDict={},
                                   ParameterDict={},
                                   Time_Start=Model_Time_Start,
                                   Time_End=Model_Time_End,
                                   IndexTable=IndexTable,
                                   Elements=IndexTable.loc['Element'].Classification.Items)  # Initialize MFA system

    IndexTable
    ## 1.2 Inserting data into the MFA system

    # Define process list
    Dyn_MFA_System.ProcessList = []  # Start with empty process list, only process numbers (IDs) and names are needed.
    Dyn_MFA_System.ProcessList.append(msc.Process(Name='Outside', ID=0))
    Dyn_MFA_System.ProcessList.append(msc.Process(Name='Use phase', ID=1))

    shape = [len(MyScenario), len(MyRegions), len(MyLevels), len(MyProducts), len(MyElements), len(MyYears)]
    stock_array = stock.reindex(columns=MyYears).fillna(0).values.reshape(shape)

    shape = (len(MyScenario), len(MyProducts), len(MyRegions))
    lifetime_array = lifetime.values.reshape(shape)

    # Define the parameter values for the inflow parameter:
    ParameterDict = {}

    ParameterDict['Stock'] = msc.Parameter(Name='stock aluminium', ID=1, P_Res=1,
                                           MetaData=None, Indices='s,r,l,p,e,t',
                                           Values=stock_array, Unit='Mt')

    ParameterDict['tau'] = msc.Parameter(Name='mean product lifetime', ID=2, P_Res=1,
                                         MetaData=None, Indices='s,p,r',
                                         Values=lifetime_array, Unit='yr')

    ParameterDict['sigma'] = msc.Parameter(Name='stddev of mean product lifetime', ID=3, P_Res=1,
                                           MetaData=None, Indices='s,p,r',
                                           Values=lifetime_array * .3, Unit='yr')

    # Assign parameter dictionary to MFA system:
    Dyn_MFA_System.ParameterDict = ParameterDict

    # Define the flows of the system, and initialise their values:
    Dyn_MFA_System.FlowDict['F_0_1'] = msc.Flow(Name='final consumption', P_Start=0, P_End=1,
                                                Indices='s,r,l,p,e,t', Values=None)
    Dyn_MFA_System.FlowDict['F_1_0'] = msc.Flow(Name='Eol products', P_Start=1, P_End=0,
                                                Indices='s,r,l,p,e,c,t', Values=None)
    Dyn_MFA_System.StockDict['S_1'] = msc.Stock(Name='steel stock', P_Res=1, Type=0,
                                                Indices='s,r,l,p,e,c,t', Values=None)
    Dyn_MFA_System.StockDict['dS_1'] = msc.Stock(Name='steel stock change', P_Res=1, Type=1,
                                                 Indices='s,r,l,p,e,t', Values=None)
    Dyn_MFA_System.Initialize_FlowValues()  # Assign empty arrays to flows according to dimensions.
    Dyn_MFA_System.Initialize_StockValues()  # Assign empty arrays to flows according to dimensions.

    # Check whether flow value arrays match their indices, etc. See method documentation.
    Dyn_MFA_System.Consistency_Check()

    # 1.3 Programming a solution for the dMFA

    # Programming solution

    for s in np.arange(0, len(MyScenario)):
        for r in np.arange(0, len(MyRegions)):
            for l in np.arange(0, len(MyLevels)):
                for p in np.arange(0, len(MyProducts)):
                    for e in np.arange(0, len(MyElements)):

                        # Calculate initial stock
                        range = np.arange(0, switchtime, 1)
                        mean = lifetime_array[1,p,r] # Usine the lifetime from SSP2 to calculate initial stock
                        stdv = mean * 0.3

                        h = 1 - norm.cdf(range, loc=mean, scale=stdv)
                        q = h / h.sum()
                        distribution = pd.Series(q, index=range)

                        # rescale to size of desired total stock of 8 units
                        distribution = distribution * Dyn_MFA_System.ParameterDict['Stock'].Values[s, r, l, p, e, switchtime]

                        # reverse order: older first
                        initial_stock = distribution.iloc[::-1].values

                        DSM_Flow = dsm.DynamicStockModel(t=np.array(MyYears),
                                                         s=Dyn_MFA_System.ParameterDict['Stock'].Values[s, r, l, p, e, :],
                                                         lt={'Type': 'Normal',
                                                             'Mean': [Dyn_MFA_System.ParameterDict['tau'].Values[s, p, r]],
                                                             'StdDev': [Dyn_MFA_System.ParameterDict['sigma'].Values[s, p, r]]})

                        DSM_Flow.dimension_check()
                        s_c, o_c, i = DSM_Flow.compute_stock_driven_model_initialstock(initial_stock, switchtime+1)

                        Dyn_MFA_System.StockDict['S_1'].Values[s, r, l, p, e, :, :] = s_c
                        Dyn_MFA_System.FlowDict['F_1_0'].Values[s, r, l, p, e, :, :] = o_c
                        Dyn_MFA_System.FlowDict['F_0_1'].Values[s, r, l, p, e, :] = i
    # 1.4 Mass balance check
    Bal = Dyn_MFA_System.MassBalance()
    # print(Bal.shape)  # dimensions of balance are: time step x process x chemical element
    # print(np.abs(Bal).sum(axis=0))  # reports the sum of all absolute balancing errors by process.

    # 1.5 Transforming array into df
    arr = Dyn_MFA_System.StockDict['S_1'].Values
    arr_reshaped = np.reshape(arr, (int((np.prod(list(arr.shape)) / arr.shape[-1])), arr.shape[-1]))
    stock = pd.DataFrame(arr_reshaped, index=pd.MultiIndex.from_product([MyScenario, MyRegions, MyLevels, MyProducts, MyYears]),
                         columns=MyYears)
    stock = stock.sum(axis=1).unstack(level=4).loc(axis=1)[2015:2100]

    arr = Dyn_MFA_System.FlowDict['F_0_1'].Values
    arr_reshaped = np.reshape(arr, (int((np.prod(list(arr.shape)) / arr.shape[-1])), arr.shape[-1]))
    inflow = pd.DataFrame(arr_reshaped, index=pd.MultiIndex.from_product(
        [MyScenario, MyRegions, MyLevels, MyProducts]), columns=MyYears)
    inflow = inflow.loc(axis=1)[2015:2100]

    arr = Dyn_MFA_System.FlowDict['F_1_0'].Values
    arr_reshaped = np.reshape(arr, (int((np.prod(list(arr.shape)) / arr.shape[-1])), arr.shape[-1]))
    outflow = pd.DataFrame(arr_reshaped, index=pd.MultiIndex.from_product([MyScenario, MyRegions, MyLevels, MyProducts, MyYears]),
                         columns=MyYears)
    outflow = outflow.sum(axis=1).unstack(level=4).loc(axis=1)[2015:2100]
    return stock, inflow, outflow

def dMFA_ODYM_id(inflow, lifetime, sector, sub_sector):
    ''' Calculate dMFA with a inflow driven approach using ODYM framework
    '''

    inflow = inflow.loc[:, :, :, sector, sub_sector]
    lifetime = lifetime.loc[:, sector, sub_sector, :]
    ##Define MFA system
    ModelClassification = {}  # Create dictionary of model classifications

    MyScenario = list(dict.fromkeys(inflow.index.get_level_values(0)))
    ModelClassification['Scenario'] = msc.Classification(Name='Scenario', Dimension='Scenario', ID=1, Items=MyScenario)

    MyYears = list(np.arange(1900, inflow.columns[0], 1)) + list(inflow.columns)
    ModelClassification['Time'] = msc.Classification(Name='Time', Dimension='Time', ID=2, Items=MyYears)
    # Classification for time labelled 'Time' must always be present,
    #  with Items containing a list of odered integers representing years, months, or other discrete time intervals

    ModelClassification['Cohort'] = msc.Classification(Name='Age-cohort', Dimension='Time', ID=3, Items=MyYears)
    # Classification for cohort is used to track age-cohorts in the inflow.

    MyRegions = list(dict.fromkeys(inflow.index.get_level_values(1)))
    ModelClassification['Region'] = msc.Classification(Name='Region', Dimension='Region', ID=4, Items=MyRegions)
    # Classification for regions is chosen to include the regions that are in the scope of this analysis.

    MyLevels = list(dict.fromkeys(inflow.index.get_level_values(2)))
    ModelClassification['Level'] = msc.Classification(Name='Level', Dimension='Level', ID=5, Items=MyLevels)
    # Classification for level represent 3 levels of aluminium content

    MyProducts = list(dict.fromkeys(inflow.index.get_level_values(3)))
    ModelClassification['Product'] = msc.Classification(Name='Product', Dimension='Product', ID=6, Items=MyProducts)
    # Classification for product is chosen to include the products that are in the scope of this analysis.

    MyElements = ['Aluminium']
    ModelClassification['Element'] = msc.Classification(Name='Elements', Dimension='Elements', ID=7, Items=MyElements)
    # Classification for elements labelled 'Element' must always be present,
    #  with Items containing a list of the symbols of the elements covered.

    # Get model time start, end, and duration:
    Model_Time_Start = int(min(ModelClassification['Time'].Items))
    Model_Time_End = int(max(ModelClassification['Time'].Items))
    Model_Duration = (Model_Time_End - Model_Time_Start)

    # That dictionary of classifications enteres the index table defined for the system.
    # The indext table lists all aspects needed and assigns a classification and index letter to each aspect.

    IndexTable = pd.DataFrame(
        {'Aspect': ['Scenario', 'Time', 'Age-cohort', 'Region', 'Level', 'Product', 'Element'],
         # 'Time' and 'Element' must be present!
         'Description': ['Model aspect "Scenario"', 'Model aspect "time"', 'Model aspect "age-cohort"',
                         'Model aspect "Region where flow occurs"', 'Model aspect "Level of al content"',
                         'Model aspect "Product"', 'Model aspect "Element"'],
         'Dimension': ['Scenario', 'Time', 'Time', 'Region', 'Level', 'Product', 'Elements'],
         # 'Time' and 'Element' are also dimensions
         'Classification': [ModelClassification[Aspect] for Aspect in
                            ['Scenario', 'Time', 'Cohort', 'Region', 'Level', 'Product', 'Element']],
         'IndexLetter': ['s', 't', 'c', 'r', 'l', 'p', 'e']})  # Unique one letter (upper or lower case) indices to be used later for calculations.

    IndexTable.set_index('Aspect', inplace=True)  # Default indexing of IndexTable, other indices are produced on the fly

    # We can now define our MFA system:

    Dyn_MFA_System = msc.MFAsystem(Name='AluminiuminflowDynamic',
                                   Geogr_Scope='5SelectedRegions',
                                   Unit='Mt',
                                   ProcessList=[],
                                   FlowDict={},
                                   StockDict={},
                                   ParameterDict={},
                                   Time_Start=Model_Time_Start,
                                   Time_End=Model_Time_End,
                                   IndexTable=IndexTable,
                                   Elements=IndexTable.loc['Element'].Classification.Items)  # Initialize MFA system

    IndexTable

    ## 1.2 Inserting data into the MFA system

    # Define process list
    Dyn_MFA_System.ProcessList = []  # Start with empty process list, only process numbers (IDs) and names are needed.
    Dyn_MFA_System.ProcessList.append(msc.Process(Name='Outside', ID=0))
    Dyn_MFA_System.ProcessList.append(msc.Process(Name='Use phase', ID=1))

    shape = [len(MyScenario), len(MyRegions), len(MyLevels), len(MyProducts), len(MyElements), len(MyYears)]
    inflow_array = inflow.reindex(columns=MyYears).fillna(0).values.reshape(shape)

    shape = (len(MyScenario), len(MyProducts), len(MyRegions))
    lifetime_array = lifetime.values.reshape(shape)

    # Define the parameter values for the inflow parameter:
    ParameterDict = {}

    ParameterDict['Inflow'] = msc.Parameter(Name='stock aluminium', ID=1, P_Res=1,
                                            MetaData=None, Indices='s,r,l,p,e,t', Values=inflow_array, Unit='Mt')

    ParameterDict['tau'] = msc.Parameter(Name='mean product lifetime', ID=2, P_Res=1,
                                         MetaData=None, Indices='s,p,r', Values=lifetime_array, Unit='yr')

    ParameterDict['sigma'] = msc.Parameter(Name='stddev of mean product lifetime', ID=3, P_Res=1,
                                           MetaData=None, Indices='s,p,r', Values=lifetime_array * .3, Unit='yr')

    # Assign parameter dictionary to MFA system:
    Dyn_MFA_System.ParameterDict = ParameterDict

    # Define the flows of the system, and initialise their values:
    Dyn_MFA_System.FlowDict['F_0_1'] = msc.Flow(Name='final consumption', P_Start=0, P_End=1,
                                                Indices='s,r,l,p,e,t', Values=None)
    Dyn_MFA_System.FlowDict['F_1_0'] = msc.Flow(Name='Eol products', P_Start=1, P_End=0,
                                                Indices='s,r,l,p,e,c,t', Values=None)
    Dyn_MFA_System.StockDict['S_1'] = msc.Stock(Name='steel stock', P_Res=1, Type=0,
                                                Indices='s,r,l,p,e,c,t', Values=None)
    Dyn_MFA_System.StockDict['dS_1'] = msc.Stock(Name='steel stock change', P_Res=1, Type=1,
                                                 Indices='s,r,l,p,e,t', Values=None)
    Dyn_MFA_System.Initialize_FlowValues()  # Assign empty arrays to flows according to dimensions.
    Dyn_MFA_System.Initialize_StockValues()  # Assign empty arrays to flows according to dimensions.

    # Check whether flow value arrays match their indices, etc. See method documentation.
    Dyn_MFA_System.Consistency_Check()

    # 1.3 Programming a solution for the dMFA

    for s in np.arange(0, len(MyScenario)):
        for r in np.arange(0, len(MyRegions)):
            for l in np.arange(0, len(MyLevels)):
                for p in np.arange(0, len(MyProducts)):
                    for e in np.arange(0, len(MyElements)):
                        DSM_Inflow = dsm.DynamicStockModel(t=np.array(MyYears),
                                                           i=Dyn_MFA_System.ParameterDict['Inflow'].Values[s, r, l, p, e, :],
                                                           lt={'Type': 'Normal', 'Mean': [Dyn_MFA_System.ParameterDict['tau'].Values[s, p, r]],
                                                               'StdDev': [Dyn_MFA_System.ParameterDict['sigma'].Values[s, p, r]]})

                        s_c = DSM_Inflow.compute_s_c_inflow_driven()
                        o_c = DSM_Inflow.compute_o_c_from_s_c()

                        Dyn_MFA_System.StockDict['S_1'].Values[s, r, l, p, e, :, :] = s_c
                        Dyn_MFA_System.FlowDict['F_1_0'].Values[s, r, l, p, e, :, :] = o_c

    # 1.4 Mass balance check
    Bal = Dyn_MFA_System.MassBalance()
    #print(Bal.shape)  # dimensions of balance are: time step x process x chemical element
    #print(np.abs(Bal).sum(axis=0))  # reports the sum of all absolute balancing errors by process.

    # 1.5 Transforming array into df

    arr = Dyn_MFA_System.StockDict['S_1'].Values
    arr_reshaped = np.reshape(arr, (int((np.prod(list(arr.shape)) / arr.shape[-1])), arr.shape[-1]))

    stock = pd.DataFrame(arr_reshaped, index=pd.MultiIndex.from_product([MyScenario, MyRegions, MyLevels, MyProducts, MyYears]),
                         columns=MyYears).loc(axis=1)[2015:2100]
    stock = stock.sum(axis=1).unstack(level=4).loc(axis=1)[2015:2100]

    arr = Dyn_MFA_System.FlowDict['F_0_1'].Values
    arr_reshaped = np.reshape(arr, (int((np.prod(list(arr.shape)) / arr.shape[-1])), arr.shape[-1]))
    inflow = pd.DataFrame(arr_reshaped, index=pd.MultiIndex.from_product([MyScenario, MyRegions, MyLevels, MyProducts]), columns=MyYears)

    arr = Dyn_MFA_System.FlowDict['F_1_0'].Values
    arr_reshaped = np.reshape(arr, (int((np.prod(list(arr.shape)) / arr.shape[-1])), arr.shape[-1]))
    outflow = pd.DataFrame(arr_reshaped, index=pd.MultiIndex.from_product([MyScenario, MyRegions, MyLevels, MyProducts, MyYears]),columns=MyYears)

    outflow = outflow.sum(axis=1).unstack(level=4).loc(axis=1)[2015:2100]

    return (stock, outflow)

def projection(dataframe, year_0):
    ''' Spline projection of data form 2015 to 2100
    '''
    # years to base the extrapolation
    x = list(dataframe.columns)
    # years to extrapolate
    x_all = np.arange(year_0, 2101, 1)

    # Empty df with new dimension, index and columns
    dataframe_plus = pd.DataFrame(index=dataframe.index, columns=x_all)

    # For everyline, find the appropriate parameter for extrapolation and extrapolate
    for ix in dataframe.index:
        b = make_interp_spline(x, dataframe.loc[ix, :].values, bc_type=([(2, 0)], [(1, 0)]))
        dataframe_plus.loc[ix, :] = b(x_all)

    return dataframe_plus

def alloys(stock, d_alloys):
    ''' Decompose into aluminum alloys
    '''
    # Create an empty df with right direction integrating alloys dimension
    alloys = pd.DataFrame(index=stock.index, columns=pd.MultiIndex.from_product([stock.columns, d_alloys.columns]))
    # Product aluminium stock with market share of different alloys
    for ix in stock.index:
        alloys.loc[ix] = np.outer(stock.loc[ix], d_alloys.loc[ix[-1]]).ravel()
    alloys = alloys.stack(level=1)
    return (alloys)

def elements(stock_a, elements_alloys):
    ''' Decompose into alloying elements
    '''
    # Create an empty df with rigth direction integrating an element dimension
    elements = pd.DataFrame(index=stock_a.index,
                            columns=pd.MultiIndex.from_product([stock_a.columns, elements_alloys.columns]))
    # Produt of alloys stock with different alloying element by alloys
    for ix in stock_a.index:
        elements.loc[ix] = np.outer(stock_a.loc[ix], elements_alloys.loc[ix[-1]]).ravel()
    elements = elements.stack(level=1)
    return (elements)

def stock_total(stock, population):
    ''' Calculate the total stock from the population projections
    '''
    stock_total = pd.DataFrame()

    # For every ssp, multiply the stock by the population
    for ssp in list(dict.fromkeys(population.index.get_level_values(0))):
        stock_total_temp = stock.loc[ssp].mul(population.loc[ssp], axis=0, level=0)
        stock_total_temp = pd.concat([stock_total_temp], keys=[ssp])
        stock_total = pd.concat([stock_total, stock_total_temp])

    #Change kg per MT
    stock_total = stock_total/1000
    return (stock_total)

def calc_glo(df, population):
    ''' Calculate global average based on poupulaton per region
    '''
    df_keys = pd.DataFrame()
    for SSP in list(dict.fromkeys(population.index.get_level_values(0))):
        population_share = population.div(population.sum(level=0), level=0)
        df_new = df.loc[SSP].mul(population_share.loc[SSP], level=0).sum(level=[1, 2, 3, 4])
        df_keys = pd.concat([df_keys, pd.concat([pd.concat([df_new], keys=['GLO'])], keys=[SSP])])

    df_with_glo = pd.concat([df, df_keys]).sort_index()
    return (df_with_glo)

